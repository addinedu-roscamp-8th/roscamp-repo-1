# 음성 주문 GUI 개발 현황 리포트

**작성 기준**: 현재까지 구현 완료된 음성 주문 GUI 및 Voice·Backend 연동 내용을 정리한 문서입니다.  
**최종 업데이트**: 2025-02-23

---

## 1. 목표 및 범위

| 항목 | 내용 |
|------|------|
| **대상** | 기존 데모용 `voice_feedback_widget.py`를 실제 서비스 수준으로 확장 |
| **진입** | 버튼 없음. **웨이크업 워드**가 서비스 진입점 |
| **입력** | **음성만** 사용 (마이크 → STT → 주문 플로우) |
| **테이블** | 화면에 **테이블 드롭다운(1~4)** 만 제공 |
| **플로우** | 웨이크업 → 주문 대화 → 주문 확인 → 추가 주문 → 주문 완료 → Backend 주문 전송 |

---

## 2. 완료된 개발 항목

### 2.1 설정 및 공통

| 파일 | 내용 |
|------|------|
| `app/gui/common/config.py` | **VOICE_SERVER_URL** 추가. `os.getenv('VOICE_SERVER_URL', 'http://127.0.0.1:8000')`. 다른 호스트/포트 사용 시 환경 변수로 지정. |

### 2.2 Voice API 클라이언트

| 파일 | 내용 |
|------|------|
| `app/gui/customer_gui/src/voice_api_client.py` | Voice 서버 HTTP 클라이언트. **stt**(오디오→텍스트), **agent_voice**(오디오→웨이크업+TTS), **order_turn**(텍스트→주문 1턴), **tts_json**(텍스트→base64 오디오). 타임아웃·에러 처리 포함. |

### 2.3 음성 주문 UI (스탠드얼론)

| 파일 | 내용 |
|------|------|
| `app/gui/customer_gui/src/voice_feedback_widget.py` | **스탠드얼론 실행** (`python voice_feedback_widget.py`). 테이블 드롭다운(1~4) + 상태/파형/인식 텍스트/에이전트 답변. 버튼 없음. |

**주요 동작**:

- **녹음**: `RecordWorker`가 4초 단위로 마이크 WAV 녹음 → 시그널로 전달.
- **웨이크**: 오디오 → `POST /agent/voice`. `is_wake` 시 주문 모드 진입, 응답 TTS 재생.
- **주문 대화**: 주문 모드에서 오디오 → `POST /stt` → 텍스트 → `POST /agent/order_turn`(table_number 전달) → reply/state 표시, `POST /tts/json`으로 답변 TTS 재생.
- **주문 완료**: `state.stage == "idle"` 이고 `order_ids` 있으면 "주문 접수되었습니다" 표시 후 대기 상태로 복귀.

**피드백 루프 방지**:

- **TTS 재생 중 녹음 일시정지**: `QMediaPlayer.stateChanged` 로 재생 중(PlayingState)일 때만 녹음 pause, **Playing → Stopped** 전환 시에만 녹음 재개. (상수 대기 시간 없음)
- **짧은/중복 STT 무시**: `MIN_STT_LENGTH_FOR_ORDER`(2글자) 미만이거나 직전과 동일한 텍스트는 `order_turn` 호출 안 함.

**환경 대응**:

- PortAudio 미설치 시 `OSError` 처리 후 앱은 실행, 화면/콘솔에 설치 안내 표시.

### 2.4 의존성 및 문서

| 파일 | 내용 |
|------|------|
| `app/gui/customer_gui/requirements-voice-gui.txt` | `requests`, `sounddevice`, `numpy`. 시스템 의존성 안내: Ubuntu/Debian `libportaudio2`, Fedora `portaudio-devel`. |
| `docs/voice_gui_service_strategy.md` | 전략·실행 계획·테스트 계획, Voice 서버 URL 설명(목적·문제·방안 A/B/C), TTS 재생 중 녹음 제어 방식 정리. |

---

## 3. 현재 동작 플로우 (요약)

1. 사용자가 `python voice_feedback_widget.py` 실행 → 테이블 선택(드롭다운) + "말씀해 주세요" 표시.
2. 마이크 4초 청크 녹음 → `POST /agent/voice`. 웨이크 아님 → 무시. 웨이크 → 주문 모드, TTS 재생, 재생 중에는 녹음 일시정지.
3. 주문 모드에서 녹음 청크 → STT → 2글자 미만 또는 직전과 동일 텍스트면 무시. 그 외 → `order_turn` → 답변 표시·TTS 재생(TTS 재생 중 녹음 일시정지).
4. "주문 완료" → "네" 등으로 확정 시 Voice 서버가 Backend에 주문 전송 → GUI에서 "주문 접수되었습니다" 표시 후 초기 상태로.

---

## 4. 실행 환경

| 항목 | 내용 |
|------|------|
| **Voice 서버** | 기본 `http://127.0.0.1:8000`. 변경 시 `VOICE_SERVER_URL` 환경 변수. |
| **실행** | `cd app/gui/customer_gui/src && python voice_feedback_widget.py` |
| **Python 패키지** | `pip install -r ../requirements-voice-gui.txt` |
| **시스템(마이크)** | Ubuntu/Debian: `sudo apt install libportaudio2` |

---

## 5. 미연동·선택 과제

| 항목 | 설명 |
|------|------|
| **main.py 통합** | 현재 음성 주문은 `voice_feedback_widget.py` **스탠드얼론**만 사용. 메인 고객 GUI(`main.py`)에 음성 진입 버튼/오버레이로 붙이는 작업은 미진행. |
| **배달 알림 연동** | 주문 접수 후 Backend→GUI 배달 푸시·수령 확인 플로우는 스탠드얼론 위젯에서 별도 구현하지 않음. (main.py 쪽 기존 플로우는 유지됨.) |
| **VAD/PTT** | 음성 활동 감지(VAD) 또는 푸시-투-토크 방식은 미구현. 현재는 고정 4초 청크 녹음. |

---

## 6. 참고 문서

- **전략·계획**: `docs/voice_gui_service_strategy.md`
- **통합 테스트**: `docs/voice_order_integration_test_plan.md`
