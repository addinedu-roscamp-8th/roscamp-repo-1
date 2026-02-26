# 음성 주문 연동 분석 및 구현 계획 리포트

## 01. GUI와 Backend 연동 구조 분석

### 1.1 서비스 구조 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│  app/                                                                   │
│  ├── gui/                     (사용자 요청 수집·정리)                    │
│  │   ├── customer_gui/        → 주문 메뉴 조회, 주문 전송, 배달 알림 수신  │
│  │   ├── admin_gui/           → 대시보드, 레시피/재고/함대 모니터링       │
│  │   └── common/              → Config, Order/Menu 등 공통 모델          │
│  └── backend/                 (비즈니스 로직·DB·ROS 연동)                 │
│       └── main_server/        → TCP 서버, DB, ROS Bridge                  │
└─────────────────────────────────────────────────────────────────────────┘
```

- **GUI**: 사용자 입력을 받아 주문/조회 요청을 **정리**하고, **Backend(Main Server)** 에 비즈니스 로직을 요청합니다.
- **Backend**: TCP 서버(기본 포트 **9999**)로 JSON 메시지를 수신하고, DB·ROS(FMS)와 연동해 주문 생성·상태 조회·함대 상태 등을 처리합니다.

### 1.2 통신 프로토콜 (GUI ↔ Backend)

| 항목 | 내용 |
|------|------|
| 전송 방식 | TCP 소켓, JSON 메시지 |
| 메시지 형식 | **4바이트 길이 헤더(big-endian) + UTF-8 JSON 본문** |
| 주소 | `Config.get_order_ms_address()` → 기본 `(127.0.0.1, 5000)` ※ 실제 Main Server는 **9999** 사용 가능 |
| 메시지 필드 | `type` 또는 `command`(레거시), `data` 또는 최상위 필드에 payload |

- Backend는 `type`과 `command`를 모두 인식하며, `command` 사용 시 `command`를 제외한 나머지 필드를 `data`로 넘깁니다.

### 1.3 GUI → Backend 메시지 타입 (Customer GUI 기준)

| 메시지 타입 | 용도 | 요청 형식 (요약) |
|-------------|------|-------------------|
| `get_menus` | 메뉴 목록 조회 | `{ "command": "get_menus", "table_number": N }` |
| `submit_order` | 주문 전송 | `{ "command": "submit_order", "order": { "table_number", "items": [{ "menu_id", "menu_name", "price", "quantity" }], "total_price" } }` |
| (수령 확인) | 배달 수령 완료 | `{ "type": "delivery_complete", "data": { "order_id", "table_number" } }` |

- 응답 공통: `{ "status": "success" | "error", "data": { ... } }` 또는 `"message": "에러 메시지"`.

### 1.4 Backend 주문 처리 흐름

1. **TCP 수신** (`tcp_server.py`): 길이 헤더 + JSON 수신 → `message_type` 결정 → 해당 핸들러 호출.
2. **주문 관련 핸들러** (`main_server_node.py`):
   - **order_request**: 1건 주문 (table_number, menu_id, quantity, sauce_type, voice_order) → `DatabaseManager.create_order()` → `update_order_status(..., 'CONFIRMED')` → `ros_bridge.publish_order_request()` → TCP broadcast.
   - **submit_order**: Customer GUI용. `order` 안의 `items` 중 **첫 번째 항목만** 사용해 1건 생성 → `create_order()` → CONFIRMED → `publish_order_request()`.
3. **DB** (`database_manager.py`): `create_order(table_number, menu_id, quantity=1, voice_order=False)` → `Order` 행 생성, `order_id` 반환.

정리하면, **최종 주문을 DB에 넣고 FMS로 보내는 기능**은 다음 두 가지로 사용할 수 있습니다.

- **order_request**: 항목 1개당 1회 호출 (voice_order=True 지원).
- **submit_order**: 1회 호출당 1건(첫 번째 item만 사용), 현재 `voice_order`는 항상 False.

---

## 02. 음성 인터페이스 연동 지점 및 사용 기능

### 2.1 음성 주문 플로우 (1~6)

| 단계 | 담당 | 비고 |
|------|------|------|
| 1 | 사용자 | 메뉴 이름을 알고 있음 (메뉴 설명 불필요) |
| 2 | 음성 서버 | 웨이크업 후 "샌드위치 주문을 도와드릴까요?" 등 발화 |
| 3 | 음성 서버 | 사용자 음성 → '햄치즈샌드위치', '머쉬룸샌드위치', 'All-in-one' 등 인식 |
| 4 | 음성 서버 | 복명복창으로 주문 내용 확인 |
| 5 | 음성 서버 | "주문 진행할까요?" 확인 후 진행 결정 |
| **5~6** | **음성 서버 → Backend** | **주문 확정 시 Backend API 호출 → DB 저장** |

즉, **1~5는 음성 서버 내부에서 처리**하고, **5→6 구간에서만 Backend를 사용**합니다.

### 2.2 Backend에서 사용할 기능/함수

- **사용할 API**: Main Server **TCP** (호스트/포트 설정 필요, 기본 포트 **9999**).
- **사용할 메시지** (둘 중 선택):
  - **A) order_request** (권장)
    - 한 번에 **메뉴 1종, 수량 1** 기준.
    - 여러 메뉴 주문 시 **항목별로 order_request를 여러 번** 보냄.
    - `voice_order: true` 로 DB에 음성 주문 기록 가능.
    - 요청 예:  
      `{ "type": "order_request", "data": { "table_number": "1", "menu_id": "M001", "quantity": 1, "sauce_type": "mayo", "voice_order": true } }`
  - **B) submit_order**
    - 현재 구현은 **items[0]만** 사용해 1건만 생성.
    - 여러 메뉴를 한 번에 보내려면 Backend 수정(여러 item 루프 생성) 필요.
    - 요청 예:  
      `{ "type": "submit_order", "data": { "order": { "table_number": 1, "items": [ { "menu_id": "M001", "menu_name": "햄치즈샌드위치", "price": 5000, "quantity": 1 } ], "total_price": 5000 } } }`

- **메뉴명 → menu_id 매핑**  
  Backend mock 메뉴:  
  - 햄치즈샌드위치 → **M001**  
  - 머쉬룸샌드위치 → **M002**  
  - 올인원샌드위치 → **M003**  
  음성 서버는 주문 확정 시 위 매핑(또는 `get_menus` 응답)으로 `menu_id`를 채워 전송하면 됩니다.

### 2.3 음성 서버 내부 연동 지점

- **위치**: `ai_server/voice_processing_server/`
- **현재 구조**:
  - **파이프라인**: `app/pipeline/voice_pipeline.py` — STT → 웨이크업 → (웨이크 시) 펑션 콜 → TTS.
  - **펑션 콜링**: `app/core/function_calling.py` — 현재 `test_voice_order`만 등록되어 로그만 출력.
- **연동 지점**:  
  사용자가 주문을 확정하는 시점(플로우 5→6)에서 **실제 Backend 주문 전송**을 수행하는 **새 함수(예: `submit_voice_order`)** 를 추가하고,  
  - 입력: 확정된 주문 목록 `[{ "menu_id", "menu_name", "quantity" }, ...]`, (선택) `table_number`.  
  - 동작: Main Server TCP로 **order_request**를 항목별로 전송(또는 submit_order 1건).  
  - 출력: `{ "success", "order_ids", "message" }` 형태로 파이프라인/Agent에 반환.

이 함수를 **펑션 콜링에 등록**하면, "주문 진행할까요?" 확인 후 호출되도록 플로우를 만들 수 있습니다.

---

## 03. 구현 전략 및 실행 계획

### 3.1 구현 전략 요약

1. **Backend 호출 방식**: Main Server **TCP 클라이언트**를 음성 서버에 구현 (동기 요청/응답, 4바이트 길이 + JSON 프로토콜).
2. **주문 전송 API**: **order_request**를 항목당 1회 호출 (`voice_order=true`). 단순 접근이므로 먼저 1건만 보내도 됨.
3. **메뉴 매핑**: 고정 매핑(햄치즈→M001, 머쉬룸→M002, 올인원→M003) 또는 필요 시 `get_menus`로 목록 조회 후 이름→id 매핑.
4. **테이블 번호**: 설정(환경 변수 또는 config)으로 지정, 기본값 `"1"`.

### 3.2 TDD 구현 전략

- **테스트 프레임워크**: `pytest`.
- **순서**:
  1. **Backend TCP 클라이언트 모듈** 테스트: Mock 서버 또는 실제 Main Server(9999)에 연결해 `order_request` / `get_menus` 송수신 검증.
  2. **주문 전송 함수** 테스트: `submit_voice_order(items, table_number)` 가 올바른 JSON을 TCP로 보내고, 응답에서 `status: success`, `order_id` 등을 검증.
  3. **펑션 콜링 연동** 테스트: `submit_voice_order`를 등록한 뒤, Agent/파이프라인에서 호출했을 때 응답 형식 및 로그 검증.
- **Failover**: 테스트 실패 시 원인 수정 후 재실행. **최대 10회**까지 허용하여 통과할 때까지 반복.

### 3.3 실행 계획 (단계별)

| 단계 | 내용 | 산출물 |
|------|------|--------|
| 1 | 음성 서버에 Backend TCP 클라이언트 모듈 추가 (설정: host, port, table_number) | `app/core/backend_client.py` (또는 `app/integration/order_backend.py`) |
| 2 | `order_request` 전송 및 응답 파싱 함수 구현 | `send_order_request(table_number, menu_id, quantity, voice_order=True)` |
| 3 | `submit_voice_order(items, table_number)` 구현 (항목별 order_request 호출) | 위 모듈 내 함수 |
| 4 | 메뉴명→menu_id 매핑 (고정 또는 get_menus) | 매핑 테이블 또는 get_menus 호출 |
| 5 | `app/core/function_calling.py`에 `submit_voice_order` 등록 및 인자 스키마 정의 | 펑션 목록에 추가, run_test_function에서 분기 |
| 6 | 파이프라인/Agent에서 주문 확정 시 해당 함수 호출하도록 플로우 연결 | voice_pipeline / voice_agent 수정 |
| 7 | 단위/통합 테스트 작성 및 TDD 사이클 (최대 10회 Failover) | `tests/test_voice_order_backend.py` 등 |

### 3.4 설정 추가

- **voice_processing_server** 쪽 설정 예:
  - `ORDER_BACKEND_HOST` (기본: `127.0.0.1`)
  - `ORDER_BACKEND_PORT` (기본: `9999`)
  - `VOICE_ORDER_TABLE_NUMBER` (기본: `1`)

---

## 04. 최종 사용/연동 방안 요약

- **최종 주문을 처리하는 Backend 기능**:  
  - **DatabaseManager.create_order()** (내부)  
  - 대외 연동은 **TCP 메시지 `order_request`** (또는 `submit_order`)로 수행.

- **음성 서버 연동**:
  - 5→6 구간에서 **TCP로 order_request(voice_order=true)** 를 항목별로 전송.
  - 사용할 Backend 함수/API: **Main Server TCP `order_request`**.
  - 구현: 음성 서버에 TCP 클라이언트 + `submit_voice_order` + 펑션 콜링 등록 및 파이프라인에서 확정 시 호출.

---

## 05. 실행 여부 피드백 요청

위 분석과 구현 전략(Backend TCP 클라이언트, order_request 항목별 전송, TDD, 최대 10회 Failover)으로 진행해도 될지 알려주시면, 그에 맞춰 **TDD 방식으로 테스트 코드부터 작성한 뒤 구현**을 진행하겠습니다.

- **진행 시**: 테스트 실패 시 원인 수정 후 재실행을 최대 10회까지 반복합니다.
- **변경 원하시면**: Backend 포트(9999 외), 테이블 번호 기본값, 또는 submit_order 다건 확장 여부 등을 지정해 주시면 반영하겠습니다.
