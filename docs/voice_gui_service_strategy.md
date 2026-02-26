# 음성 주문 GUI 실제 서비스화 전략 및 실행 계획

## 1. 파일 개발 내용 분석

### 1.1 `voice_feedback_widget.py` (데모 음성 인터페이스 GUI)

| 구성 요소 | 내용 |
|-----------|------|
| **역할** | SR-03b: 음성 주문 시각적 피드백만 제공, 웨이크업 콜 이용 |
| **VoiceWaveformWidget** | 음성 인식 중 파형 애니메이션 (사인파). `start_animation()` / `stop_animation()` |
| **VoiceFeedbackWidget** | 상태 레이블, 파형, 인식 텍스트, 신뢰도 표시. `VoiceRecognitionState` 보유 |
| **메서드** | `start_listening()`, `stop_listening()`, `set_recognized_text(text, confidence)`, `show_processing()`, `show_error()`, `reset()` |
| **시그널** | `voice_recognition_complete = pyqtSignal(str)` — 인식 완료 시 인식된 텍스트 전달 |
| **연동** | **없음**. 실제 STT/Voice 서버/Backend와 연결되지 않음. 테스트 시 `QTimer.singleShot`으로 가짜 인식 결과 표시 |

### 1.2 `main.py` (고객용 GUI 메인)

| 항목 | 내용 |
|------|------|
| **VoiceFeedbackWidget 사용** | `voice_feedback = VoiceFeedbackWidget(self)` 로 생성 후 화면 하단 고정 위치(500x300), **기본 hide()** |
| **노출/연결** | **어디에서도 `voice_feedback.show()` 또는 음성 시작 버튼 연결이 없음** → 현재 플로우에서 음성 위젯 미사용 |
| **주문 플로우** | 메인 → 주문 시작 → 메뉴 선택 → 주문 확인 → 전송 → 메인 (또는 배달 알림 → 수령 확인) |
| **클라이언트** | `OrderServiceClient`(Backend TCP) 또는 FMS Direct. `fetch_menus`, `submit_order`, `confirm_delivery`, 배달 푸시 수신 |

### 1.3 Voice 서버 (ai_server/voice_processing_server)

| API | 용도 |
|-----|------|
| `POST /agent/voice` | 오디오 업로드 → STT → 웨이크업 → (웨이크 시) test_voice_order → TTS 응답 |
| `POST /agent/voice/text` | 텍스트 입력 → 웨이크업 → test_voice_order → TTS 응답 |
| `POST /agent/order_turn` | **음성 주문 1턴**: `session_id`, `text`, `table_number` → `process_order_turn()` → `reply_text`, `state` (idle → collecting → ask_more → confirming → idle, 주문 확정 시 Backend `submit_voice_order`) |

플로우: **웨이크업** → **주문 대화(메뉴 담기)** → **추가 주문 / 주문 완료** → **주문 확인(네)** → Backend 주문 전송.

### 1.4 Backend (app/backend/main_server)

- TCP 서버: `get_menus`, `order_request`(항목별), `submit_order` 등.
- Voice 서버의 `backend_client.submit_voice_order`는 항목별 `order_request`로 주문 전송.

---

## 2. 기존 구현 완료 vs 추가 구현 필요

### 2.1 이미 구현된 기능

| 기능 | 구현 위치 | 비고 |
|------|-----------|------|
| 웨이크업/주문 대화/확정/추가주문/완료 플로우 | Voice 서버 `voice_order_state.process_order_turn` | idle → collecting → ask_more → confirming, "주문 완료" 후 "네" 시 Backend 전송 |
| 주문 확인 후 Backend 전송 | Voice 서버 `backend_client.submit_voice_order` | 항목별 order_request, voice_order=True |
| 테이블 선택 UI | `ui_main_window.py` | 1~4 콤보, `Config.TABLE_NUMBER` 반영 |
| 음성 피드백 UI (데모) | `voice_feedback_widget.py` | 대기/듣는 중/인식 결과/처리 중/에러 표시, 파형 애니메이션 |
| 고객 GUI 주문 플로우 | `main.py` | 메뉴 선택 → 확인 → 전송 → 배달 알림 → 수령 확인 |
| Backend TCP 프로토콜 | `tcp_server.py`, `main_server_node.py` | get_menus, order_request, 배달 푸시 등 |

### 2.2 추가 구현 필요한 기능

| 번호 | 기능 | 설명 |
|------|------|------|
| 1 | **메인 화면에서 음성 주문 진입** | 메인 윈도우에 "음성으로 주문하기" 버튼(또는 기존 주문 시작과 병행) 추가 → 클릭 시 `voice_feedback.show()` 및 음성 세션 시작 |
| 2 | **Voice 서버 HTTP 연동** | GUI에서 Voice API 호출: (A) `POST /agent/order_turn` 연속 호출(텍스트 기반), (B) 필요 시 `POST /agent/voice`(오디오) 또는 `POST /agent/voice/text`(텍스트). Voice 서버 base URL 설정 필요 (예: `VOICE_SERVER_URL=http://127.0.0.1:8000`) |
| 3 | **음성 위젯 ↔ order_turn 플로우 매핑** | 사용자 발화(텍스트 또는 오디오) → `order_turn` 요청 → 응답 `reply_text`/`state` 수신 → 위젯에 인식 텍스트·상태·에이전트 답변 반영, 필요 시 TTS 재생 |
| 4 | **주문 상태 반영 및 주문 완료 처리** | `state.stage`가 idle로 돌아오고 `order_ids` 수신 시 → GUI에서 "주문 접수됨" 표시, `pending_order` 등으로 관리하고 기존 배달 알림 플로우와 연동 |
| 5 | **테이블 번호 전달** | 메인에서 선택한 `Config.TABLE_NUMBER`를 Voice 세션에 전달 (`order_turn`의 `table_number`). Voice 서버는 이미 `table_number` 지원 |
| 6 | **(옵션) 오디오 입력** | 마이크 → 오디오 전송 → `POST /agent/voice` 호출 시 오디오 업로드. 데모는 텍스트만으로도 가능하므로 2단계로 나누어 구현 가능 |
| 7 | **(옵션) TTS 재생** | `order_turn`은 TTS를 반환하지 않음. Agent 답변 스피커 재생이 필요하면 `POST /tts/json` 등 별도 호출 또는 `agent/voice` 사용 |

---

## 3. 구현 전략

### 3.1 방향

- **1단계(우선)**: **텍스트 기반 음성 주문**  
  - GUI에서 "음성으로 주문하기" 클릭 → Voice 피드백 위젯 표시 → 사용자 **텍스트 입력**(또는 시뮬레이션)으로 `POST /agent/order_turn` 연속 호출.  
  - 응답의 `reply_text`/`state`를 위젯에 표시하고, 주문 확정 시 Backend까지 전송되는지 확인.
- **2단계(선택)**: 오디오 입력(`/agent/voice`) 및 TTS 재생 연동.

### 3.2 설계 포인트

- **Voice API 클라이언트**: GUI 전용 모듈(예: `voice_api_client.py`)에서 `requests`로 `VOICE_SERVER_URL` + `/agent/order_turn` 호출. 스레드 또는 QThread로 호출해 UI 블로킹 방지.
- **세션 ID**: 키오스크당 또는 진입당 1개(예: `session_id = f"gui_{table}_{timestamp}"`) 유지.
- **테이블 번호**: `Config.TABLE_NUMBER`를 `order_turn`의 `table_number`에 그대로 전달.
- **주문 완료 처리**: `state`에 `order_ids`가 있으면 주문 접수 성공으로 간주하고, 기존 `on_order_submitted`와 유사하게 메시지 표시 후 메인으로 복귀(또는 배달 알림 대기).

---

## 4. 실행 계획

| 단계 | 작업 | 산출물 |
|------|------|--------|
| 1 | GUI 설정에 `VOICE_SERVER_URL` 추가 (환경 변수/Config) | `app/gui/common/config.py` |
| 2 | Voice API 클라이언트 구현 (`order_turn` 호출, 테이블 번호 전달) | `app/gui/customer_gui/src/voice_api_client.py` |
| 3 | `VoiceFeedbackWidget` 확장: 주문 단계 표시(state.stage), 에이전트 답변(reply_text), 오류 표시 | `voice_feedback_widget.py` |
| 4 | 메인 윈도우에 "음성으로 주문하기" 진입점 추가, 클릭 시 voice_feedback 표시 및 세션 시작 | `ui_main_window.py`, `main.py` |
| 5 | 위젯에서 텍스트 입력/전송 시 `voice_api_client.order_turn()` 호출, 응답으로 위젯 갱신 및 주문 완료 시 앱 레벨 처리(주문 접수 메시지, 메인 복귀) | `voice_feedback_widget.py`, `main.py` |
| 6 | (선택) 오디오 업로드 + TTS 재생 | 별도 이슈 |

---

## 5. 테스트 전략 및 실행 계획

### 5.1 단위/연동

- **Voice API 클라이언트**: Mock 서버(Flask/FastAPI)로 `POST /agent/order_turn` 응답 흉내 → reply/state 반영 확인.
- **VoiceFeedbackWidget**: 시그널/상태 문자열만 주입해 단계별 문구·에러 표시 확인.

### 5.2 E2E 시나리오 (기존 통합 테스트와 동일)

1. **Phase A (Mock Backend)**  
   - Mock Backend TCP 기동.  
   - Voice 서버는 Mock Backend로 설정.  
   - GUI 실행 → "음성으로 주문하기" → 텍스트로 "주문할게요" → "햄치즈샌드위치" → "추가주문" → "머쉬룸샌드위치" → "주문 완료" → "네".  
   - Mock Backend에서 `order_request` 수신 횟수/메뉴 확인.

2. **Phase B (OpenAI + Mock Backend)**  
   - 동일 시나리오를 실제 음성 또는 오디오 파일로 진행(필요 시 `/agent/voice` 사용).  
   - TTS/스피커 재생 여부 확인.

3. **Phase C (Real Backend + DB)**  
   - Main Server + DB 기동.  
   - GUI에서 테이블 선택 후 동일 플로우 실행.  
   - DB `orders`에 `voice_order=true` 등으로 저장되는지 확인.

### 5.3 테스트 체크리스트

- [ ] 메인에서 "음성으로 주문하기" 클릭 시 Voice 피드백 위젯 표시.
- [ ] 텍스트 입력 후 order_turn 호출 시 상태/답변 문구 갱신.
- [ ] "주문 완료" → "네" 후 주문 접수 메시지 표시 및 메인 복귀(또는 배달 대기).
- [ ] 테이블 번호 변경 시 order_turn에 반영.
- [ ] Voice 서버 다운 시 에러 메시지 표시.

---

## 6. Voice 서버 URL 설정 (상세 설명)

### 6.1 무엇을 위한 선택인가?

고객용 음성 GUI는 **키오스크(또는 실행하는 PC)** 에서 돌아가고, **Voice 처리 서버**(STT·웨이크업·주문 플로우·TTS)는 별도 프로세스로 **다른 호스트/포트**에서 동작할 수 있습니다.  
GUI가 `POST /agent/voice`, `POST /stt/`, `POST /agent/order_turn` 등을 호출하려면 **어디로 요청을 보낼지** 알려줘야 하므로, 그 **기준 주소**가 필요합니다. 이 기준 주소를 **Voice 서버 URL**이라고 합니다.

### 6.2 어떤 문제를 해결하려는 것인가?

- **같은 PC에서만 실행하는 경우**: Voice 서버를 `http://127.0.0.1:8000` 에 띄우고, GUI도 같은 PC에서 실행하면 별도 설정 없이 이 주소를 쓰면 됩니다.
- **다른 PC/서버에서 Voice를 띄우는 경우**: 예를 들어 Voice 서버는 `192.168.1.10:8000` 에 있고, 키오스크는 `192.168.1.20` 이라면, GUI에는 `http://192.168.1.10:8000` 처럼 **Voice 서버 주소**를 알려줘야 합니다. 이 값을 잘못 두면 **연결 거부(Connection refused)** 또는 **타임아웃**이 발생합니다.
- **포트를 바꿔서 실행하는 경우**: Voice 서버를 8001 등 다른 포트로 띄우면, GUI 쪽에서도 같은 포트를 쓰도록 설정해야 합니다.

즉, **Voice 서버 URL 설정**은 “GUI가 어떤 호스트:포트로 HTTP 요청을 보낼지”를 정하는 것이고, 잘못 설정하면 **음성 인식/주문이 동작하지 않는 연결 문제**를 해결하기 위한 것입니다.

### 6.3 선택 가능한 방안

| 방안 | 설명 | 장점 | 단점 |
|------|------|------|------|
| **A. 고정 기본값만 사용** | 코드에 `http://127.0.0.1:8000` 만 사용. 설정 파일/환경 변수 없음. | 구현이 단순함. | Voice 서버를 다른 PC/포트에서 쓰려면 코드 수정 필요. |
| **B. 환경 변수로 지정 (미설정 시 기본값)** | `VOICE_SERVER_URL` 환경 변수로 지정. 없으면 `http://127.0.0.1:8000` 사용. | 같은 실행 파일로 로컬/원격 서버 전환 가능. 배포 시 스크립트나 systemd에서만 환경 변수로 설정하면 됨. | 환경 변수 설정을 한 번 해줘야 함. |
| **C. 설정 파일(YAML 등) + 환경 변수 덮어쓰기** | 예: `config.yaml` 에 `voice_server_url` 있고, 있으면 `VOICE_SERVER_URL` 로 덮어씀. | 다른 GUI 설정과 한 파일에서 관리 가능. | 설정 파일 경로·포맷을 정해야 함. |

**권장**: 실제 서비스에서는 키오스크마다/환경마다 Voice 서버 주소가 다를 수 있으므로 **방안 B(환경 변수 + 기본값)** 를 권장합니다.  
**구현 반영**: **방안 B** 적용. `app/gui/common/config.py` 에 `VOICE_SERVER_URL = os.getenv('VOICE_SERVER_URL', 'http://127.0.0.1:8000')` 사용.

**TTS 재생 중 녹음 제어**: 상수 대기 시간 대신, `QMediaPlayer.stateChanged` 로 재생 시작(PlayingState) 시 녹음 일시정지, **Playing → Stopped** 전환 시에만 녹음 재개하도록 시스템적으로 감지하여 처리.

---

## 7. 이해 확인 및 피드백 요청

**요청하신 내용 이해 요약**

1. **기존 GUI 활용 테스트**  
   - `voice_feedback_widget.py`를 데모가 아닌 **실제 서비스**에 가깝게 쓰고, 기존 고객 GUI(`main.py`)와 함께 테스트하고자 하심.

2. **제공할 플로우**  
   - **웨이크업** → **주문 대화** → **주문 확인** → **추가 주문** → **주문 완료** → (옵션) **테이블 선택**  
   - 위 플로우를 Voice 인터페이스 + Backend와 연동해 **실제 주문 처리**까지 되게 하고 싶으심.

3. **진행 방식**  
   - 파일 분석 → 기존/추가 기능 리포트 → Voice·Backend 연동 구현  
   - 전략 수립 → 실행 계획 → 테스트 전략/실행 계획 수립  
   - 이해 설명 후 **피드백 요청** → 피드백 반영하여 구현 진행

**확인 요청 사항**

- **진입 방식**: 메인 화면에 "주문 시작"과 별도로 "음성으로 주문하기" 버튼을 두는 방식이 괜찮을까요? (한 버튼으로 터치/음성 분기도 가능)
- **입력 방식 1단계**: 먼저 **텍스트 입력**만 지원(필드에 입력 후 전송)하고, 오디오(마이크)는 2단계로 할까요?
- **테이블 선택**: 이미 메인에 1~4 선택이 있으므로, 음성 주문 시에도 이 값을 Voice 서버·Backend에 그대로 쓰면 될까요?
- **Voice 서버 URL**: 기본값 `http://127.0.0.1:8000`으로 두고 환경 변수로 덮는 방식으로 할까요?

위 네 가지에 대한 선호만 알려주시면, 그에 맞춰 구현을 진행하겠습니다.
