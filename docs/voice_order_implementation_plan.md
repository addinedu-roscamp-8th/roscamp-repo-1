# 음성 주문 연동 구현 전략 및 실행 계획

## 1. 반영된 요구사항 요약

| 요구사항 | 반영 내용 |
|----------|------------|
| 진행 여부 | order_request 기반, TDD, 최대 10회 Failover로 진행 |
| 테이블 | 총 4개(1~4번), 기본값 1번, **테이블 번호 변경 UI 간단 제공** |
| 다건 주문 | **다건 주문 지원 확장**. 확인 단계에서 "더 주문하실 메뉴가 있으신가요? 있으면 '추가주문', 아니면 '주문 완료'를 말씀해주세요." 방식 |
| 메뉴 매핑 | **DB에서 읽어오기** (Backend `get_menus` 호출) |
| GUI 현황 | `docs/voice_gui_development_status.md` 반영. Agent 대화 텍스트·음성 주문 상태 표시는 **구현 필요**로 정리, 필요 시 단계별 반영 |

---

## 2. 구현 전략

### 2.1 아키텍처

- **음성 서버(voice_processing_server)**  
  - 주문 확정 시 **Main Server(Backend) TCP**로 `order_request`(항목당 1건, `voice_order=true`) 전송.  
  - 메뉴 목록은 동일 TCP로 `get_menus` 호출 후 **DB 응답으로 이름→menu_id 매핑** 사용.
- **Backend**  
  - 기존 `order_request`·`get_menus` 유지.  
  - 다건 주문은 **음성 서버에서 항목별로 order_request 여러 번** 호출 (Backend 다건 확장 없이 처리).
- **GUI**  
  - 테이블 1~4 선택 UI 추가.  
  - 음성 위젯 노출·대화 텍스트·주문 단계 표시는 **2단계(옵션)** 로 두고, 1단계는 음성 서버·Backend 연동만 완료.

### 2.2 테이블 번호

- Backend 전송 시 `table_number`는 **1~4** 문자열.  
- 기본값 **1**.  
- GUI: 메인 화면 등에 테이블 선택(1/2/3/4) 콤보 또는 버튼 추가.

### 2.3 다건 주문 플로우 (음성)

1. 웨이크업 → "샌드위치 주문을 도와드릴까요?"
2. 사용자: "햄치즈샌드위치" 등 메뉴명 발화.
3. 복명복창 후, **"더 주문하실 메뉴가 있으신가요? 있으면 '추가주문', 아니면 '주문 완료'를 말씀해주세요."**
4. 사용자: "추가주문" → 2~3 반복. "주문 완료" → 5로.
5. "주문을 진행할까요?" 확인 후 진행.
6. Backend 연동: 항목별 `order_request`(voice_order=true) 호출.

### 2.4 TDD 및 Failover

- pytest로 단위·통합 테스트 작성 후 구현.  
- 실패 시 원인 수정 후 재실행, **최대 10회**까지 허용.

---

## 3. 실행 계획 (단계별)

### Phase 1: Backend 연동 기반 (음성 서버)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 1.1 | Backend TCP 클라이언트 모듈 (길이 헤더 + JSON, 9999) | `voice_processing_server/app/core/backend_client.py` |
| 1.2 | `get_menus()` 호출 및 메뉴 목록 반환 (DB 기반) | 동일 모듈 |
| 1.3 | `send_order_request(table_number, menu_id, quantity, voice_order=True)` 구현 | 동일 모듈 |
| 1.4 | 설정: ORDER_BACKEND_HOST, ORDER_BACKEND_PORT, VOICE_ORDER_TABLE_NUMBER(기본 1) | `app/config/settings.py` 또는 .env |
| 1.5 | 단위 테스트: Mock TCP 서버 또는 실제 Backend로 get_menus/order_request 송수신 검증 | `tests/test_backend_client.py` |

### Phase 2: 주문 확정 로직 (음성 서버)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 2.1 | `submit_voice_order(items: list[dict], table_number: str)` (항목별 order_request) | `app/core/backend_client.py` 또는 `app/core/order_submit.py` |
| 2.2 | 메뉴명→menu_id 매핑: get_menus 응답으로 매핑 테이블 구성, 주문 시 사용 | 동일 |
| 2.3 | 펑션 콜링에 `submit_voice_order` 등록 (인자: items, table_number) | `app/core/function_calling.py` |
| 2.4 | 테스트: submit_voice_order 호출 시 TCP로 여러 건 order_request 전송·응답 검증 | `tests/test_voice_order_submit.py` |

### Phase 3: 음성 플로우 (추가주문/주문 완료)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 3.1 | 주문 상태: "메뉴 수집 중" / "확인 대기" / "추가주문 대기" / "주문 완료 대기" 등 단계 정의 | 파이프라인/Agent 내 상태 또는 별도 state 모듈 |
| 3.2 | "더 주문하실 메뉴가 있으신가요? 있으면 '추가주문', 아니면 '주문 완료'를 말씀해주세요." 발화 및 분기 | 웨이크업/의도 판별 또는 LLM 프롬프트로 처리 |
| 3.3 | 사용자 "추가주문" → 메뉴 추가 수집. "주문 완료" → 최종 확인 후 submit_voice_order 호출 | 파이프라인/Agent 수정 |
| 3.4 | 테스트: 추가주문/주문완료 시나리오 (TDD, 최대 10회 Failover) | `tests/test_voice_order_flow.py` |

### Phase 4: GUI – 테이블 번호 변경 UI

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 4.1 | 메인 화면(또는 주문 시작 화면)에 테이블 1~4 선택 UI 추가 (콤보박스 또는 버튼) | `ui_main_window.py` + 필요 시 `main_window.ui` |
| 4.2 | 선택값을 `Config.TABLE_NUMBER` 또는 앱 전역 변수에 반영, label_table 갱신 | `main.py` 등 |

### Phase 5 (옵션): GUI – 음성 상태·대화 표시

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 5.1 | "음성으로 주문" 진입 버튼 추가, 클릭 시 VoiceFeedbackWidget 표시 | `main.py`, `ui_main_window.py` |
| 5.2 | 음성 서버 Agent 턴 결과(stt_text, reply_text)를 GUI로 전달 (HTTP 폴링 또는 WebSocket) 후 위젯에 표시 | 별도 이슈/단계 |

---

## 4. 구현 순서 및 산출물 요약

1. **Phase 1** → **Phase 2** → **Phase 3** 순으로 진행. (TDD 적용, 최대 10회 Failover)
2. **Phase 4** (테이블 UI)는 Phase 1·2와 병렬 또는 직후 진행 가능.
3. **Phase 5**는 1~4 완료 후, 필요 시 진행.

| Phase | 핵심 산출물 |
|-------|-------------|
| 1 | backend_client.py, get_menus/order_request, 설정, 테스트 |
| 2 | submit_voice_order, 메뉴 매핑, 펑션 콜링 등록, 테스트 |
| 3 | 추가주문/주문 완료 플로우, 상태 분기, 테스트 |
| 4 | 테이블 1~4 선택 UI, Config 반영 |
| 5 (옵션) | 음성 진입점, 대화 텍스트 표시 |

---

## 5. 진행 여부 피드백 요청

- 위 전략·실행 계획대로 **Phase 1 → 2 → 3 → 4** 순으로 구현을 진행해도 될지 확인 부탁드립니다.
- **Phase 5**(GUI 음성 상태·대화 표시)는 이번 단계에서 제외하고, 1~4 완료 후 별도로 진행해도 되는지 알려주시면 그에 맞춰 반영하겠습니다.
- **진행 가능**이라고 확인해 주시면, TDD(최대 10회 Failover)를 적용해 구현을 시작하겠습니다.
