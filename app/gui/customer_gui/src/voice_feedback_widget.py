"""
음성 인식 시각적 피드백 위젯 — 음성만으로 주문 (버튼 없음, 웨이크업 진입)
SR-03b: 음성 주문. 서비스 진입 = 웨이크업 워드, 테이블만 드롭다운.
"""
import sys
import os
import io
import wave
import time
import math
from typing import Optional

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QApplication,
    QComboBox,
    QMainWindow,
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QPainter, QColor, QPen

# 프로젝트 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import VoiceRecognitionState, Config

# Voice API 클라이언트 (실행 디렉터리가 src일 때 동일 디렉터리에서 로드)
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
try:
    from voice_api_client import agent_voice, stt, order_turn, tts_json
except ImportError:
    agent_voice = stt = order_turn = tts_json = None

# 녹음 청크 길이(초)
RECORD_CHUNK_DURATION = 4
SAMPLE_RATE = 16000
# STT 결과가 이 길이 미만이면 order_turn 호출 안 함 (노이즈/피드백 방지)
MIN_STT_LENGTH_FOR_ORDER = 2


def _numpy_available():
    try:
        import numpy as np
        return True
    except ImportError:
        return False


def _sounddevice_available():
    """sounddevice(및 PortAudio) 사용 가능 여부. OSError = PortAudio 미설치."""
    try:
        import sounddevice as sd  # noqa: F401
        return True
    except ImportError:
        return False
    except OSError:
        # PortAudio library not found → sudo apt install libportaudio2
        return False


def _record_wav_bytes(sample_rate: int, duration_sec: float) -> Optional[bytes]:
    """마이크로 duration_sec초 녹음 후 WAV 바이트 반환. 실패 시 None."""
    try:
        import sounddevice as sd
        import numpy as np
    except (ImportError, OSError):
        return None
    try:
        samples = int(duration_sec * sample_rate)
        rec = sd.rec(samples, samplerate=sample_rate, channels=1, dtype=np.int16)
        sd.wait()
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(rec.tobytes())
        buf.seek(0)
        return buf.getvalue()
    except Exception:
        return None


class VoiceWaveformWidget(QWidget):
    """음성 인식 중 파형 애니메이션 위젯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 150)
        self.wave_offset = 0
        self.animation_timer = None
        self.is_active = False

    def start_animation(self):
        self.is_active = True
        if not self.animation_timer:
            self.animation_timer = QTimer()
            self.animation_timer.timeout.connect(self.update_wave)
            self.animation_timer.start(50)
        self.update_wave()

    def stop_animation(self):
        self.is_active = False
        if self.animation_timer:
            self.animation_timer.stop()
        self.update()

    def update_wave(self):
        self.wave_offset += 5
        if self.wave_offset > 360:
            self.wave_offset = 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        width = self.width()
        height = self.height()
        center_y = height // 2
        if not self.is_active:
            painter.setPen(QPen(QColor('#CCCCCC'), 2))
            painter.drawLine(0, center_y, width, center_y)
            return
        painter.setPen(QPen(QColor('#4A90E2'), 3))
        points = []
        for x in range(width):
            angle1 = (x + self.wave_offset) * 0.05
            angle2 = (x + self.wave_offset) * 0.08
            y = center_y + math.sin(angle1) * 30 + math.sin(angle2) * 20
            points.append((x, int(y)))
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(x1, y1, x2, y2)


class VoiceApiWorker(QObject):
    """다른 스레드에서 Voice API 호출 (UI 블로킹 방지)"""
    wake_detected = pyqtSignal(dict)       # agent_voice 결과 (웨이크 시)
    order_turn_done = pyqtSignal(str, dict, object)  # reply_text, state, tts_base64_or_none
    error_occurred = pyqtSignal(str)
    set_table_number_signal = pyqtSignal(int)
    set_order_mode_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._table_number = 1
        self._order_mode = False
        self._session_id = ""
        self._busy = False
        self._last_order_turn_text = ""  # 직전에 order_turn 보낸 텍스트 (중복/피드백 무시)

    def set_table_number(self, n: int):
        self._table_number = max(1, min(4, n))

    def set_order_mode(self, on: bool):
        self._order_mode = on
        if not on:
            self._session_id = ""
            self._last_order_turn_text = ""

    def handle_audio(self, audio_bytes: bytes):
        if not audio_bytes or len(audio_bytes) < 1000:
            return
        if self._busy:
            return
        self._busy = True
        try:
            if not self._order_mode:
                self._handle_wake(audio_bytes)
            else:
                self._handle_order_turn(audio_bytes)
        finally:
            self._busy = False

    def _handle_wake(self, audio_bytes: bytes):
        if agent_voice is None:
            self.error_occurred.emit("Voice API 클라이언트를 불러올 수 없습니다.")
            return
        result, err = agent_voice(
            audio_bytes,
            filename="audio.wav",
            run_wakeword=True,
            run_function_on_wake=True,
            tts_reply=True,
        )
        if err:
            self.error_occurred.emit(err)
            return
        wake = (result or {}).get("wake") or {}
        if wake.get("is_wake"):
            self._order_mode = True
            self._session_id = f"gui_t{self._table_number}_{time.time():.0f}"
            self.wake_detected.emit(result)
        # 웨이크 아니면 무시 (조용히)

    def _handle_order_turn(self, audio_bytes: bytes):
        if stt is None or order_turn is None:
            self.error_occurred.emit("Voice API 클라이언트를 불러올 수 없습니다.")
            return
        text, err = stt(audio_bytes, filename="audio.wav")
        if err:
            self.error_occurred.emit(err)
            return
        text = (text or "").strip()
        if len(text) < MIN_STT_LENGTH_FOR_ORDER:
            return
        if text == self._last_order_turn_text:
            return
        self._last_order_turn_text = text
        resp, err = order_turn(
            self._session_id,
            text,
            table_number=self._table_number,
        )
        if err:
            self.error_occurred.emit(err)
            return
        reply = (resp or {}).get("reply_text") or ""
        state = (resp or {}).get("state") or {}
        tts_b64 = None
        if reply and tts_json:
            tts_res, _ = tts_json(reply)
            if tts_res:
                tts_b64 = tts_res.get("audio_base64")
        self.order_turn_done.emit(reply, state, tts_b64)

    def get_order_mode(self):
        return self._order_mode

    def get_session_id(self):
        return self._session_id


class RecordWorker(QThread):
    """주기적으로 마이크 녹음 후 시그널로 전달. TTS 재생 중에는 일시정지."""
    audio_recorded = pyqtSignal(bytes)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = True
        self._paused = False

    def stop(self):
        self._running = False

    def set_paused(self, paused: bool):
        self._paused = bool(paused)

    def run(self):
        while self._running:
            if self._paused:
                self.msleep(500)
                continue
            if not _sounddevice_available() or not _numpy_available():
                self.msleep(2000)
                continue
            wav = _record_wav_bytes(SAMPLE_RATE, RECORD_CHUNK_DURATION)
            if wav and self._running and not self._paused:
                self.audio_recorded.emit(wav)
            if not self._running:
                break


class VoiceFeedbackWidget(QWidget):
    """음성만 사용하는 주문 UI. 버튼 없음, 테이블만 드롭다운, 진입은 웨이크업."""

    voice_recognition_complete = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = VoiceRecognitionState()
        self._order_mode = False
        self._api_worker = None
        self._api_thread = None
        self._record_worker = None
        self._tts_player = None
        self._tts_prev_state = None  # QMediaPlayer state (재생 종료 감지용)
        self._tts_state_connected = False
        self.setup_ui()
        self.setup_workers()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # 테이블 선택 (드롭다운만)
        table_row = QHBoxLayout()
        table_row.addWidget(QLabel("테이블:"))
        self.combo_table = QComboBox()
        self.combo_table.addItems(["1", "2", "3", "4"])
        idx = max(0, min(Config.TABLE_NUMBER - 1, 3))
        self.combo_table.setCurrentIndex(idx)
        self.combo_table.setMinimumWidth(80)
        table_row.addWidget(self.combo_table)
        table_row.addStretch()
        layout.addLayout(table_row)

        self.label_status = QLabel("말씀해 주세요 (웨이크워드로 주문을 시작합니다)")
        self.label_status.setAlignment(Qt.AlignCenter)
        self.label_status.setStyleSheet("""
            font-size: 20px; font-weight: bold; color: #333333; padding: 10px;
        """)
        layout.addWidget(self.label_status)

        self.waveform = VoiceWaveformWidget()
        layout.addWidget(self.waveform)

        self.label_recognized_text = QLabel("")
        self.label_recognized_text.setAlignment(Qt.AlignCenter)
        self.label_recognized_text.setWordWrap(True)
        self.label_recognized_text.setStyleSheet("""
            font-size: 16px; color: #4A90E2; padding: 8px;
            background-color: #F0F8FF; border-radius: 5px;
        """)
        self.label_recognized_text.hide()
        layout.addWidget(self.label_recognized_text)

        self.label_reply = QLabel("")
        self.label_reply.setAlignment(Qt.AlignCenter)
        self.label_reply.setWordWrap(True)
        self.label_reply.setStyleSheet("""
            font-size: 18px; color: #2d5a27; padding: 10px;
            background-color: #e8f5e9; border-radius: 5px;
        """)
        self.label_reply.hide()
        layout.addWidget(self.label_reply)

        self.label_confidence = QLabel("")
        self.label_confidence.setAlignment(Qt.AlignCenter)
        self.label_confidence.setStyleSheet("font-size: 14px; color: #666666;")
        self.label_confidence.hide()
        layout.addWidget(self.label_confidence)

        self.setLayout(layout)
        self.setMinimumSize(500, 380)

    def setup_workers(self):
        self._api_worker = VoiceApiWorker()
        self._api_thread = QThread()
        self._api_worker.moveToThread(self._api_thread)
        self._api_thread.start()

        self._api_worker.set_table_number_signal.connect(self._api_worker.set_table_number)
        self._api_worker.set_order_mode_signal.connect(self._api_worker.set_order_mode)
        self._api_worker.wake_detected.connect(self._on_wake_detected)
        self._api_worker.order_turn_done.connect(self._on_order_turn_done)
        self._api_worker.error_occurred.connect(self._on_api_error)

        self.combo_table.currentIndexChanged.connect(self._on_table_changed)
        self._on_table_changed(self.combo_table.currentIndex())

        self._record_worker = RecordWorker(self)
        self._record_worker.audio_recorded.connect(self._on_audio_recorded)
        self._record_worker.start()

        self.start_listening()
        if not _sounddevice_available():
            self.label_status.setText(
                "마이크 사용 불가: PortAudio 미설치\n"
                "Ubuntu/Debian: sudo apt install libportaudio2"
            )
            self.label_status.setStyleSheet("""
                font-size: 16px; font-weight: bold; color: #FFA500; padding: 10px;
            """)

    def _on_table_changed(self, index: int):
        table_num = index + 1
        Config.TABLE_NUMBER = table_num
        self._api_worker.set_table_number_signal.emit(table_num)

    def _on_audio_recorded(self, audio_bytes: bytes):
        if self._api_worker:
            self._api_worker.handle_audio(audio_bytes)

    def _on_wake_detected(self, result: dict):
        self._order_mode = True
        reply = result.get("reply_text") or "주문 모드를 시작했습니다. 원하시는 메뉴를 말씀해 주세요."
        self.label_status.setText("🎤 주문 중 — 메뉴를 말씀해 주세요")
        self.label_status.setStyleSheet("""
            font-size: 20px; font-weight: bold; color: #4A90E2; padding: 10px;
        """)
        self.label_reply.setText(reply)
        self.label_reply.show()
        self.waveform.start_animation()
        self._play_tts(result.get("tts_audio_base64"))
        stt_text = result.get("stt_text") or ""
        if stt_text:
            self.label_recognized_text.setText(f'인식: "{stt_text}"')
            self.label_recognized_text.show()
        print("[VoiceFeedback] 웨이크 감지 — 주문 모드 진입")

    def _on_order_turn_done(self, reply_text: str, state: dict, tts_base64=None):
        self.label_reply.setText(reply_text)
        self.label_reply.show()
        self._play_tts(tts_base64)
        stage = state.get("stage", "")
        items = state.get("items", [])
        if items:
            summary = ", ".join(f'{x.get("menu_name","")} {x.get("quantity",1)}' for x in items)
            self.label_recognized_text.setText(f"담은 메뉴: {summary}")
            self.label_recognized_text.show()
        if stage == "idle" and state.get("order_ids"):
            self.label_status.setText("✅ 주문 접수되었습니다")
            self.label_status.setStyleSheet("""
                font-size: 20px; font-weight: bold; color: #2d5a27; padding: 10px;
            """)
            self._order_mode = False
            if self._api_worker:
                self._api_worker.set_order_mode_signal.emit(False)
            self.waveform.stop_animation()
            QTimer.singleShot(3000, self._reset_after_order)
        print(f"[VoiceFeedback] order_turn reply: {reply_text[:50]}...")

    def _reset_after_order(self):
        self.label_status.setText("말씀해 주세요 (웨이크워드로 주문을 시작합니다)")
        self.label_status.setStyleSheet("""
            font-size: 20px; font-weight: bold; color: #333333; padding: 10px;
        """)
        self.label_recognized_text.hide()
        self.label_reply.hide()
        self.waveform.stop_animation()

    def _on_api_error(self, msg: str):
        self.show_error(msg)

    def _on_tts_player_state_changed(self, state):
        """TTS 재생 상태 변경: Playing → 녹음 일시정지, Playing→Stopped 전환 시 녹음 재개."""
        from PyQt5.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlayingState:
            if self._record_worker:
                self._record_worker.set_paused(True)
        elif state == QMediaPlayer.StoppedState:
            if self._tts_prev_state == QMediaPlayer.PlayingState:
                if self._record_worker:
                    self._record_worker.set_paused(False)
        self._tts_prev_state = state

    def _play_tts(self, audio_base64=None):
        if not audio_base64:
            return
        try:
            import base64
            from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
            from PyQt5.QtCore import QUrl
            data = base64.b64decode(audio_base64)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(data)
                path = f.name
            if self._record_worker:
                self._record_worker.set_paused(True)
            player = getattr(self, "_tts_player", None) or QMediaPlayer()
            self._tts_player = player
            if not self._tts_state_connected:
                player.stateChanged.connect(self._on_tts_player_state_changed)
                self._tts_state_connected = True
            player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
            player.play()
            QTimer.singleShot(5000, lambda: os.path.exists(path) and os.remove(path))
        except Exception as e:
            print(f"[VoiceFeedback] TTS 재생 실패: {e}")
            if self._record_worker:
                self._record_worker.set_paused(False)

    def start_listening(self):
        self.state.is_listening = True
        self.label_status.setText("말씀해 주세요 (웨이크워드로 주문을 시작합니다)")
        self.waveform.start_animation()
        print("[VoiceFeedback] 음성 인식 시작")

    def stop_listening(self):
        self.state.is_listening = False
        self.waveform.stop_animation()
        if self._record_worker and self._record_worker.isRunning():
            self._record_worker.stop()
            self._record_worker.wait(3000)
        print("[VoiceFeedback] 음성 인식 중지")

    def set_recognized_text(self, text: str, confidence: float = 0.0):
        self.state.recognized_text = text
        self.state.confidence = confidence
        if text:
            self.label_recognized_text.setText(f'인식됨: "{text}"')
            self.label_recognized_text.show()
            if confidence > 0:
                self.label_confidence.setText(f"신뢰도: {int(confidence*100)}%")
                self.label_confidence.show()
            self.voice_recognition_complete.emit(text)

    def show_processing(self):
        self.label_status.setText("⏳ 처리 중...")
        self.label_status.setStyleSheet("""
            font-size: 20px; font-weight: bold; color: #FFA500; padding: 10px;
        """)

    def show_error(self, error_message: str):
        self.label_status.setText(f"❌ 오류: {error_message}")
        self.label_status.setStyleSheet("""
            font-size: 18px; font-weight: bold; color: #FF4444; padding: 10px;
        """)
        self.waveform.stop_animation()
        print(f"[VoiceFeedback] 오류: {error_message}")

    def reset(self):
        self.stop_listening()
        self.state = VoiceRecognitionState()
        self._order_mode = False
        if self._api_worker:
            self._api_worker.set_order_mode_signal.emit(False)
        self.label_recognized_text.hide()
        self.label_reply.hide()
        self.label_confidence.hide()

    def closeEvent(self, event):
        self.stop_listening()
        if self._api_thread and self._api_thread.isRunning():
            self._api_thread.quit()
            self._api_thread.wait(2000)
        event.accept()


def main():
    """스탠드얼론 실행: 음성만으로 주문, 버튼 없음, 테이블 드롭다운만."""
    app = QApplication(sys.argv)

    if not _sounddevice_available():
        print("경고: 마이크 녹음 불가. PortAudio 필요 — Ubuntu/Debian: sudo apt install libportaudio2")
    if not _numpy_available():
        print("경고: numpy 미설치. pip install numpy")

    win = QMainWindow()
    win.setWindowTitle("음성 주문")
    widget = VoiceFeedbackWidget()
    win.setCentralWidget(widget)
    win.setMinimumSize(520, 420)
    win.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
