"""
음성 인식 시각적 피드백 위젯
SR-03b: 음성 주문 (시각적 피드백만 제공, wakeup call 이용)
"""
import sys
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QApplication
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QPen, QFont
import math

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from common import VoiceRecognitionState


class VoiceWaveformWidget(QWidget):
    """음성 인식 중 파형 애니메이션 위젯"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 150)
        self.wave_offset = 0
        self.animation_timer = None
        self.is_active = False

    def start_animation(self):
        """애니메이션 시작"""
        self.is_active = True
        if not self.animation_timer:
            self.animation_timer = QTimer()
            self.animation_timer.timeout.connect(self.update_wave)
            self.animation_timer.start(50)  # 50ms 간격

    def stop_animation(self):
        """애니메이션 중지"""
        self.is_active = False
        if self.animation_timer:
            self.animation_timer.stop()
        self.update()

    def update_wave(self):
        """파형 업데이트"""
        self.wave_offset += 5
        if self.wave_offset > 360:
            self.wave_offset = 0
        self.update()

    def paintEvent(self, event):
        """파형 그리기"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_y = height // 2

        if not self.is_active:
            # 비활성 상태 - 직선
            painter.setPen(QPen(QColor('#CCCCCC'), 2))
            painter.drawLine(0, center_y, width, center_y)
            return

        # 활성 상태 - 파형
        painter.setPen(QPen(QColor('#4A90E2'), 3))

        # 사인 파형 그리기
        points = []
        for x in range(width):
            # 여러 개의 사인파 조합
            angle1 = (x + self.wave_offset) * 0.05
            angle2 = (x + self.wave_offset) * 0.08
            y1 = math.sin(angle1) * 30
            y2 = math.sin(angle2) * 20
            y = center_y + y1 + y2
            points.append((x, int(y)))

        # 선 그리기
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(x1, y1, x2, y2)


class VoiceFeedbackWidget(QWidget):
    """음성 인식 피드백 통합 위젯"""

    # 시그널 정의
    voice_recognition_complete = pyqtSignal(str)  # 인식 완료 (인식된 텍스트)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = VoiceRecognitionState()
        self.setup_ui()

    def setup_ui(self):
        """UI 설정"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # 상태 레이블
        self.label_status = QLabel('음성 인식 대기 중...')
        self.label_status.setAlignment(Qt.AlignCenter)
        self.label_status.setStyleSheet('''
            font-size: 20px;
            font-weight: bold;
            color: #333333;
            padding: 10px;
        ''')
        layout.addWidget(self.label_status)

        # 파형 위젯
        self.waveform = VoiceWaveformWidget()
        layout.addWidget(self.waveform)

        # 인식된 텍스트 레이블
        self.label_recognized_text = QLabel('')
        self.label_recognized_text.setAlignment(Qt.AlignCenter)
        self.label_recognized_text.setWordWrap(True)
        self.label_recognized_text.setStyleSheet('''
            font-size: 18px;
            color: #4A90E2;
            padding: 10px;
            background-color: #F0F8FF;
            border-radius: 5px;
        ''')
        self.label_recognized_text.hide()
        layout.addWidget(self.label_recognized_text)

        # 신뢰도 레이블
        self.label_confidence = QLabel('')
        self.label_confidence.setAlignment(Qt.AlignCenter)
        self.label_confidence.setStyleSheet('''
            font-size: 14px;
            color: #666666;
        ''')
        self.label_confidence.hide()
        layout.addWidget(self.label_confidence)

        self.setLayout(layout)
        self.setMinimumSize(500, 300)

    def start_listening(self):
        """음성 인식 시작"""
        self.state.is_listening = True
        self.state.recognized_text = ''
        self.state.confidence = 0.0

        self.label_status.setText('🎤 듣고 있습니다...')
        self.label_status.setStyleSheet('''
            font-size: 20px;
            font-weight: bold;
            color: #4A90E2;
            padding: 10px;
        ''')

        self.label_recognized_text.hide()
        self.label_confidence.hide()

        self.waveform.start_animation()
        print('[VoiceFeedback] 음성 인식 시작')

    def stop_listening(self):
        """음성 인식 중지"""
        self.state.is_listening = False

        self.label_status.setText('음성 인식 대기 중...')
        self.label_status.setStyleSheet('''
            font-size: 20px;
            font-weight: bold;
            color: #333333;
            padding: 10px;
        ''')

        self.waveform.stop_animation()
        print('[VoiceFeedback] 음성 인식 중지')

    def set_recognized_text(self, text: str, confidence: float = 0.0):
        """인식된 텍스트 표시"""
        self.state.recognized_text = text
        self.state.confidence = confidence

        if text:
            self.label_recognized_text.setText(f'인식됨: "{text}"')
            self.label_recognized_text.show()

            if confidence > 0:
                confidence_percent = int(confidence * 100)
                self.label_confidence.setText(f'신뢰도: {confidence_percent}%')
                self.label_confidence.show()

            print(f'[VoiceFeedback] 인식 결과: {text} (신뢰도: {confidence:.2f})')

            # 인식 완료 시그널 발생
            self.voice_recognition_complete.emit(text)

    def show_processing(self):
        """처리 중 표시"""
        self.label_status.setText('⏳ 처리 중...')
        self.label_status.setStyleSheet('''
            font-size: 20px;
            font-weight: bold;
            color: #FFA500;
            padding: 10px;
        ''')

    def show_error(self, error_message: str):
        """에러 표시"""
        self.label_status.setText(f'❌ 오류: {error_message}')
        self.label_status.setStyleSheet('''
            font-size: 20px;
            font-weight: bold;
            color: #FF4444;
            padding: 10px;
        ''')
        self.waveform.stop_animation()
        print(f'[VoiceFeedback] 오류: {error_message}')

    def reset(self):
        """초기화"""
        self.stop_listening()
        self.state = VoiceRecognitionState()
        self.label_recognized_text.hide()
        self.label_confidence.hide()


def main():
    """테스트 실행"""
    app = QApplication(sys.argv)

    widget = VoiceFeedbackWidget()
    widget.show()

    # 테스트: 3초 후 음성 인식 시작
    QTimer.singleShot(1000, widget.start_listening)

    # 테스트: 5초 후 인식 결과 표시
    def show_result():
        widget.set_recognized_text('닭가슴살포케 두 개 주세요', 0.95)
        widget.stop_listening()

    QTimer.singleShot(5000, show_result)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
