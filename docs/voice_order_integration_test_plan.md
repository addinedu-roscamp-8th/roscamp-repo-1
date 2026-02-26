# 음성 주문 통합 테스트 계획

**실제로 복사·실행하면서 테스트하려면** → **[음성 주문 통합 테스트 진행 가이드](./voice_order_integration_test_guide.md)** 를 사용하세요.  
(실행 위치, 복사 가능한 curl/psql 명령, DB 계정, Phase A/B/C 단계별 절차가 정리되어 있습니다.)

---

## 1. 통합 테스트 요구사항 정리

| 번호 | 요구사항 | 설명 |
|------|----------|------|
| 1 | **GUI 활성화** | 고객용 GUI(키오스크)가 실행 중이며, 메인 화면·메뉴 선택·주문 확인·음성 피드백 위젯 등이 동작 가능한 상태 |
| 2 | **Mock으로 API 활성화·메뉴 선택·주문 요청** | 실제 Backend(Main Server) 대신 Mock 서버/클라이언트로 주문 MS 연동을 흉내 내어, 음성 플로우만 검증 |
| 3 | **실제 OpenAI API와 통신해 동적 결과 테스트** | STT/TTS/웨이크업·의도 판별에 **실제 OpenAI API** 사용, 음성 인식·Agent 답변이 동적으로 생성되도록 테스트 |
| 4 | **AI Agent 답변을 개발 머신 스피커로 재생** | TTS 출력 오디오를 로컬 스피커로 재생하여 사용자 관점의 음성 피드백 검증 |
| 5 | **주문 결과를 DB에서 확인** | 최종 주문이 PostgreSQL(또는 설정된 DB)에 저장되며, 주문 ID·테이블·메뉴·수량·voice_order 등 조회 가능 |

---

## 2. 개발 머신 기반 Mock 통합 테스트 전략

### 2.1 테스트 레이어 구분

| 레이어 | 역할 | Mock/Real |
|--------|------|-----------|
| **GUI** | 주문 시작, 테이블 선택, (옵션) 음성 위젯 노출 | Real (PyQt5 실행) |
| **Voice 서버** | STT·웨이크업·플로우·TTS·펑션 콜 | **Real** (OpenAI API 사용) |
| **Backend (주문 MS)** | get_menus, order_request 수신·DB 저장 | **Mock** 또는 **Real** 단계별 전환 |
| **DB** | 주문 저장·조회 | **Real** (통합 검증 시) 또는 Mock DB |

### 2.2 단계별 전략

- **Phase A – Mock 통합 (OpenAI 제외)**  
  - Backend를 **Mock TCP 서버**로 대체.  
  - Voice 서버는 **텍스트 입력만** 사용(`/agent/order_turn` 등)하고, STT/TTS는 사용하지 않거나 Mock.  
  - GUI는 **Mock OrderServiceClient**로 실행.  
  - 목표: GUI ↔ Voice 플로우 ↔ Mock Backend ↔ (선택) Mock DB 까지 경로 검증.

- **Phase B – OpenAI + Mock Backend**  
  - Voice 서버가 **실제 OpenAI**(STT/TTS/웨이크업) 사용.  
  - Backend는 계속 **Mock TCP 서버** (get_menus, order_request 응답만 구현).  
  - GUI는 Mock 클라이언트 유지 또는 Real Backend 주소를 Mock 서버로 설정.  
  - 목표: 음성 입력 → 인식 → 플로우 → TTS 재생까지 한 번에 검증, 주문 로직은 Mock으로 안전하게 검증.

- **Phase C – Full 통합 (Real Backend + Real DB)**  
  - Backend = **실제 Main Server**, DB = **실제 PostgreSQL**.  
  - Voice 서버 → Real Backend TCP로 order_request 전송.  
  - 주문 결과를 **DB에서 직접 조회**하여 검증.  
  - 목표: E2E 음성 주문이 DB에 실제로 반영되는지 확인.

### 2.3 Mock 구성 포인트

- **Backend Mock**  
  - TCP 포트 1개(예: 9998)에서 4바이트 길이 + JSON 프로토콜 구현.  
  - `get_menus` → 고정 메뉴 목록 반환.  
  - `order_request` → 고정 order_id·estimated_time 반환 (DB 미사용).  
  - Voice 서버의 `ORDER_BACKEND_HOST`/`ORDER_BACKEND_PORT`를 이 Mock으로 설정하면, 실제 Main Server 없이 통합 테스트 가능.

- **GUI Mock**  
  - 기존 `MockOrderServiceClient` 사용 시: 메뉴·주문 전송이 메모리/고정 응답만 반환.  
  - “음성 주문 통합”만 볼 때는 GUI에서 **음성 진입 버튼**으로 Voice 서버(또는 로컬 테스트 스크립트)만 호출하고, 주문 전송은 Voice 서버 → Backend(Mock/Real)로만 가도 됨.

---

## 3. 수행 계획

### 3.1 사전 준비

| 항목 | 내용 |
|------|------|
| 환경 변수 | `OPENAI_API_KEY` 설정. Voice 서버 `.env`에 `ORDER_BACKEND_HOST`, `ORDER_BACKEND_PORT`(Mock 시 Mock 서버 주소/포트) |
| DB (Phase C) | PostgreSQL 접속 정보 설정. `database/README.md` 기준 DB 생성·스키마 적용. 주문 조회용 계정 준비 |
| 포트 | Voice 서버 8000, Backend Mock 9998(또는 9999 비사용 시 9999), Main Server 실제 시 9999 |

### 3.2 Phase A – Mock 통합 (GUI + Voice 플로우 + Mock Backend)

| 순서 | 작업 | 담당 요소 |
|------|------|-----------|
| A1 | Backend Mock TCP 서버 스크립트 작성 (get_menus, order_request 응답) | `tests/integration/mock_backend_server.py` 또는 유사 |
| A2 | Voice 서버 설정으로 Mock Backend(host/port) 지정 | `.env` 또는 환경 변수 |
| A3 | GUI 실행 (Mock OrderServiceClient 또는 Backend 주소를 Mock으로) | `python main.py --mock` 등 |
| A4 | 음성 없이 텍스트로 플로우 검증: `POST /agent/order_turn` 연속 호출 (주문 시작 → 메뉴명 → 추가주문 → 주문 완료 → 네) | curl/스크립트 |
| A5 | Mock Backend가 order_request를 N회 수신했는지 로그/카운트로 확인 | Mock 서버 로그 |

**검증 포인트**: 주문 시작 → 메뉴 담기 → 추가주문/주문 완료 → 확정 시 Mock Backend로 order_request 전송됨.

### 3.3 Phase B – OpenAI + 스피커 재생 + Mock Backend

| 순서 | 작업 | 담당 요소 |
|------|------|-----------|
| B1 | Voice 서버 실행 (OpenAI 실제 사용) | `uvicorn` 등 |
| B2 | GUI 실행 (또는 테스트 전용 작은 클라이언트), 음성 입력 장치(마이크) 연결 | 개발 머신 |
| B3 | TTS 재생: **기존 Voice 서버의 OpenAI TTS 사용** (별도 스크립트 없음). 파이프라인/Agent 응답의 `tts_audio_base64`를 브라우저(static/index.html 등)에서 재생하거나, 동일 서버의 `POST /tts/`·`POST /tts/json`으로 생성한 오디오를 재생 | 기존 `/tts/`, `/static/index.html` |
| B4 | E2E 시나리오 1회: 웨이크업 발화 → 메뉴 발화 → "추가주문" → 메뉴 → "주문 완료" → "네" (실제 음성 또는 오디오 파일 업로드) | 수동/반자동 |
| B5 | Mock Backend 로그에서 order_request 수신 건수·메뉴 ID 일치 여부 확인 | 로그 모니터링 |

**검증 포인트**: 실제 음성(또는 오디오 파일) → STT → 플로우 → TTS → 개발 머신 스피커 재생, 주문은 Mock Backend로만 전송.

**TTS 관련 설명**:  
통합 테스트에서 "Agent 답변을 스피커로 재생"하는 부분은 **별도 play_tts.py를 두지 않고**, 이미 구현된 **OpenAI TTS**를 그대로 사용합니다. Voice 서버의 `POST /tts/`·`POST /tts/json`과 파이프라인/Agent 응답 필드 `tts_audio_base64`가 동일한 TTS 엔진을 사용하므로, 테스트 시에는 (1) 기존 테스트 페이지 `GET /static/index.html`에서 TTS 입력 후 재생하거나, (2) Agent/파이프라인 호출 응답의 base64 오디오를 브라우저 `<audio>` 또는 기존 재생 UI로 재생하면 됩니다. 즉, **구현 중복 없이 기존 OpenAI TTS 기능만으로** 스피커 재생 검증이 가능합니다.

### 3.4 Phase C – Real Backend + DB 확인

| 순서 | 작업 | 담당 요소 |
|------|------|-----------|
| C1 | Main Server(Backend) 실행, DB 연결 (pinky_robot_store 등) | `app/backend` |
| C2 | Voice 서버 설정을 Real Backend(host/port 9999)로 변경 | `.env` |
| C3 | GUI에서 테이블 선택(1~4) 후, 음성 주문 플로우 1회 수행 (또는 동일 시나리오를 API로만 호출) | GUI 또는 스크립트 |
| C4 | 주문 완료 후 DB에서 확인: `orders` 테이블에 최신 행 1건 이상, `voice_order=true`, `table_number`, `menu_id` 등 | `psql` 또는 DB 클라이언트 |
| C5 | (선택) Main Server 로그에서 order_request 수신·CONFIRMED·ROS 브릿지 발행까지 확인 | 로그 |

**검증 포인트**: 음성 주문 결과가 실제 DB에 저장되고, 필요 시 ROS/FMS까지 이어지는지 확인.

---

## 4. 테스트 결과 모니터링 방안

### 4.1 로그 수집

| 대상 | 방법 |
|------|------|
| Voice 서버 | 표준 출력/파일 로깅. `logging` 레벨 INFO 이상, 요청/응답 요약(세션 ID, stt_text, reply_text, function_called) 로그 |
| Mock Backend | 수신 메시지 타입·payload·횟수를 콘솔/파일에 기록 |
| Main Server | 기존 로그에 order_request, create_order, order_id 출력 유지 |

### 4.2 런타임 모니터링

- **최근 주문 시도 대시보드 (구현됨)**  
  - 간단한 웹 페이지(Flask/FastAPI) 1개: 최근 N건 “주문 시도” `/agent/order_turn` 호출 시마다 세션 ID·발화·응답·단계·order_ids 기록, GET /monitor/order_attempts·GET /static/monitor.html 로 3초마다 갱신하여 실시간 모니터링.

- **터미널 실시간**  
  - Voice 서버 + Mock Backend(또는 Main Server)를 각각 터미널에서 실행하고, `tail -f` 또는 터미널 로그로 동시에 확인.

- **DB 실시간**  
  - Phase C: `watch -n 2 'psql -U ... -d ... -c "SELECT id, table_number, menu_id, voice_order, created_at FROM orders ORDER BY created_at DESC LIMIT 5;"'` 로 2초마다 최신 주문 N건 확인.

### 4.3 결과 정리(체크리스트)

- **Phase A**  
  - [ ] Mock Backend 기동 후 get_menus 1회, order_request N회 수신  
  - [ ] /agent/order_turn 응답의 state.stage, state.items 일치

- **Phase B**  
  - [ ] 실제 음성(또는 오디오) 1회 입력 시 STT 텍스트 정확  
  - [ ] Agent 답변이 개발 머신 스피커로 재생됨  
  - [ ] Mock Backend에 동일 건수 order_request 도달

- **Phase C**  
  - [ ] DB `orders`에 voice_order=true인 신규 행 존재  
  - [ ] table_number, menu_id, quantity가 기대값과 일치

---

## 5. 피드백 반영 및 구현 요약

- **전략**: Phase A(Mock 통합) → Phase B(OpenAI + 스피커 + Mock Backend) → Phase C(Real Backend + DB) 순서로 진행하는 것이 적절한지,  
- **Mock Backend**: 별도 스크립트(`tests/integration/mock_backend_server.py`)로 구현해 두고, Voice 서버만 포트 설정으로 전환하는 방식으로 괜찮은지,  
- **TTS 재생**: 기존 Voice 서버 응답(base64 오디오)을 재생하는 **작은 Python 스크립트**(예: `tests/play_tts.py`)를 추가하는 방식으로 진행해도 되는지,  
- **모니터링**: 초기에는 로그 + DB 직접 조회만으로 하고, “최근 주문 시도 대시보드”는 옵션으로 두는 것에 동의하시는지 → **대시보드 구현 완료** (GET /monitor/order_attempts, /static/monitor.html).

구현 반영 완료.

---

## 6. 통합 테스트 실행 순서

### 6.1 Phase A (Mock 통합)

1. **Mock Backend 기동**: `cd ai_server/voice_processing_server && python3 tests/integration/mock_backend_server.py --port 9998`
2. **Voice 서버 설정**: `.env` 또는 환경 변수 `ORDER_BACKEND_HOST=127.0.0.1`, `ORDER_BACKEND_PORT=9998`
3. **Voice 서버 기동**: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. **대시보드**: 브라우저 `http://localhost:8000/static/monitor.html`
5. **플로우 검증**: `POST /agent/order_turn` 연속 호출 후 대시보드·Mock Backend 로그 확인.

### 6.2 Phase B (OpenAI + Mock Backend)

- 위 1~4 동일. `OPENAI_API_KEY` 설정. 기존 `/static/index.html` 에서 TTS 재생으로 스피커 확인.

### 6.3 Phase C (Real Backend + DB)

- Main Server(9999) 기동, Voice 서버를 Real Backend로 설정 후 음성 주문 1회 수행, DB `orders` 조회.
- **실사용자 테스트**: [음성 주문 통합 테스트 진행 가이드](./voice_order_integration_test_guide.md)의 **4.4 실사용자 테스트 (음성인터페이스 GUI)** 를 따르면, (1) 음성인터페이스 GUI(`/static/index.html`) 실행, (2) 사용자 음성으로 OpenAI와 상호작용하여 주문, (3) 같은 GUI·monitor·DB에서 주문 결과 확인까지 진행할 수 있습니다.
