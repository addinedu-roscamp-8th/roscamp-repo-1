# 음성 주문 통합 테스트 진행 가이드

비개발자도 복사·붙여넣기로 따라 할 수 있도록, **실행 위치**와 **실제 입력할 명령/URL**을 그대로 적었습니다.  
프로젝트 루트는 아래 예시 경로라고 가정합니다. 본인 PC 경로가 다르면 해당 경로로 바꿔서 실행하세요.

- **프로젝트 루트 예시**: `/home/addinedu/Documents/team_syncronized/roscamp-repo-1`

---

## 0. 테스트에 사용하는 DB 계정 (Backend ↔ pinky_robot_store)

통합 테스트(Phase C) 및 Backend 실행 시 아래 DB를 사용합니다. 이미 `app/backend/config/database.env` 에 넣어 두었습니다.

| 항목 | 값 |
|------|-----|
| DB_HOST | 192.168.0.27 |
| DB_PORT | 5432 |
| DB_NAME | pinky_robot_store |
| DB_USER | deepdive |
| DB_PASSWORD | deepdive_team123!# |

- **확인**: Backend(Main Server)는 `app/backend/config/database.env` 파일을 읽어 위 값으로 DB에 접속합니다.  
- **Phase C 이후**: 주문 결과 확인 시 아래 **5.3 DB에서 주문 확인**의 `psql` 명령에서 같은 계정을 사용합니다.

---

## 1. 사전 준비 (한 번만)

### 1.1 프로젝트 루트로 이동

- **실행 위치**: 터미널을 열고 프로젝트 루트로 이동합니다.

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1
```

(본인 PC에서 프로젝트가 다른 폴더에 있으면 그 경로로 바꿔서 실행하세요.)

### 1.2 Voice 서버용 OpenAI API 키 설정

- **실행 위치**: 프로젝트 루트에서 아래처럼 Voice 서버 설정 폴더로 이동한 뒤, `.env` 파일을 엽니다.

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1/ai_server/voice_processing_server
```

`.env` 파일이 없으면 `config/.env.example` 을 복사해 만듭니다.

```bash
cp config/.env.example .env
```

`.env` 파일을 편집해 `OPENAI_API_KEY=sk-...` 에 본인 OpenAI API 키를 넣고 저장합니다.  
(Phase B에서 실제 음성 인식·TTS를 쓸 때 필요합니다.)

### 1.3 Backend용 DB 설정 확인 (Phase C용)

- **실행 위치**: 프로젝트 루트

아래 파일이 있고, 안에 DB 접속 정보가 들어 있는지 확인합니다.

- **파일 경로**: `app/backend/config/database.env`

아래와 같은 내용이 있으면 됩니다 (비밀번호는 실제 사용 중인 값으로).

```
# Backend → pinky_robot_store (same as db_server)
DB_HOST=192.168.0.27
DB_PORT=5432
DB_NAME=pinky_robot_store
DB_USER=deepdive
DB_PASSWORD=deepdive_team123!#
```

---

## 2. Phase A – Mock Backend로 플로우만 검증 (OpenAI 없이)

목적: 음성 주문 **플로우**(주문 시작 → 메뉴 담기 → 추가주문/주문 완료 → 확정)가 Mock Backend까지 도달하는지 확인합니다.  
실제 음성 인식/OpenAI는 쓰지 않고, **텍스트로 한 턴씩** API를 호출합니다.

### 2.1 터미널 1: Mock Backend 서버 실행

- **실행 위치**: 프로젝트 루트에서 Voice 서버 디렉터리로 이동한 뒤 실행합니다.

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1/ai_server/voice_processing_server
python3 tests/integration/mock_backend_server.py --port 9998
```

- **기대 결과**:  
  - 터미널에 `[MockBackend] Listening on 127.0.0.1:9998 ...` 이 보이면 정상입니다.  
  - 이 터미널은 **끄지 말고** 그대로 둡니다.

### 2.2 Voice 서버가 Mock Backend를 쓰도록 설정

- **실행 위치**: `ai_server/voice_processing_server` (위와 동일)

`.env` 파일을 열어 아래 두 줄이 있는지 확인하고, 없으면 추가·수정합니다.  
(Mock Backend가 본인 PC에서만 돌 때는 호스트를 `127.0.0.1`로 둡니다.)

```
ORDER_BACKEND_HOST=127.0.0.1
ORDER_BACKEND_PORT=9998
```

저장 후 터미널을 닫아도 됩니다.

### 2.3 터미널 2: Voice 서버 실행

- **실행 위치**: Voice 서버 디렉터리

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1/ai_server/voice_processing_server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **기대 결과**:  
  - `Uvicorn running on http://0.0.0.0:8000` 같은 메시지가 보이면 정상입니다.  
  - 이 터미널도 **끄지 말고** 둡니다.

### 2.4 브라우저: 주문 시도 모니터링 대시보드 열기

- **URL**: 브라우저 주소창에 아래를 입력해 엽니다.

```
http://localhost:8000/static/monitor.html
```

- **역할**:  
  - 이후 단계에서 `POST http://localhost:8000/agent/order_turn` 을 호출할 때마다,  
    “사용자 발화”, “Agent 응답”, “단계”, “order_ids” 등이 이 페이지에 **자동으로** 쌓입니다.  
  - 3초마다 갱신되므로, 터미널에서 curl을 실행한 뒤 이 탭을 보면 결과를 바로 확인할 수 있습니다.

### 2.5 터미널 3: 음성 주문 플로우를 텍스트로 한 턴씩 호출

- **실행 위치**: 어디서든 상관없습니다 (같은 PC에서 Voice 서버가 8000 포트로 떠 있어야 함).

아래 명령을 **순서대로** 복사해 터미널에 붙여 넣고 실행합니다.  
각 명령은 **한 줄 전체**를 복사해서 실행하세요.

**① 주문 시작 (첫 발화)**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"주문할게요","table_number":1}'
```

- **기대**: JSON 안에 `"reply_text"` 에 “샌드위치 주문을 도와드리겠습니다” 또는 “원하시는 메뉴를 말씀해주세요” 비슷한 문장이 나옵니다.  
- **모니터**: `http://localhost:8000/static/monitor.html` 에 1행이 추가됩니다.

**② 메뉴 담기 (햄치즈샌드위치 1개)**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"햄치즈샌드위치","table_number":1}'
```

- **기대**: `"reply_text"` 에 “1건 담았습니다”, “추가주문”, “주문 완료” 안내가 나옵니다.

**③ 더 담기 (추가주문)**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"추가주문","table_number":1}'
```

- **기대**: “다음 메뉴를 말씀해주세요” 같은 응답이 나옵니다.

**④ 두 번째 메뉴 담기 (머쉬룸샌드위치 1개)**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"머쉬룸샌드위치","table_number":1}'
```

- **기대**: 다시 “N건 담았습니다”, “추가주문/주문 완료” 안내가 나옵니다.

**⑤ 주문 완료 선택**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"주문 완료","table_number":1}'
```

- **기대**: `"reply_text"` 에 “주문을 진행할까요?” 가 나옵니다.

**⑥ 주문 확정 (진행)**

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"네","table_number":1}'
```

- **기대**:  
  - `"reply_text"` 에 “주문이 접수되었습니다” 가 나옵니다.  
  - `"state"` 안에 `"order_ids"` 배열이 있고, Mock에서 준 ID(예: `mock-order-1`, `mock-order-2`)가 보입니다.

### 2.6 확인할 것 (Phase A)

1. **Mock Backend 터미널 (2.1)**  
   - `get_menus` 1번, `order_request` 2번(햄치즈 1건 + 머쉬룸 1건) 수신 로그가 나와야 합니다.  
   - 예: `[MockBackend] get_menus #1 ...`, `[MockBackend] order_request #1 table=1 menu_id=M001 ...`, `[MockBackend] order_request #2 ...`

2. **모니터 대시보드**  
   - `http://localhost:8000/static/monitor.html` 에 위 6번의 턴이 순서대로 보이고, 마지막 행에 `order_ids` 에 mock ID가 있어야 합니다.

여기까지 되면 Phase A는 성공입니다.  
Phase B로 가려면 **2.1, 2.3 터미널은 그대로 두고**, 아래 Phase B만 추가로 진행하면 됩니다.

---

## 3. Phase B – 실제 OpenAI + 스피커 재생 (Mock Backend 유지)

목적: **실제 음성 인식(STT)** 과 **Agent 답변 스피커 재생(TTS)** 까지 확인합니다. Backend는 계속 Mock(9998)을 씁니다.

### 3.1 전제

- **2.1** Mock Backend가 **9998** 포트로 계속 실행 중  
- **2.2** Voice 서버 `.env` 에 `ORDER_BACKEND_HOST=127.0.0.1`, `ORDER_BACKEND_PORT=9998` 설정됨  
- **2.3** Voice 서버가 **8000** 포트로 실행 중  
- **1.2** `.env` 에 `OPENAI_API_KEY` 가 설정되어 있음  

### 3.2 브라우저에서 테스트 페이지 열기

- **URL** (주소창에 입력):

```
http://localhost:8000/static/index.html
```

- **역할**:  
  - “녹음” → Voice 서버로 오디오 전송 → STT·웨이크업·플로우·TTS 후,  
  - 응답 오디오를 **브라우저에서 재생**할 수 있습니다. (개발 머신 스피커로 재생됨)

### 3.3 수동 시나리오 (한 번에 한 문장씩)

1. **마이크**를 켜고, 테스트 페이지에서 “녹음 시작” 후 아래 문장을 **한 문장씩** 말합니다.  
2. 각 문장 말한 뒤 “녹음 중지” → 전송되면, 화면에 인식 결과와 Agent 응답이 뜨고, **스피커로 안내가 재생**됩니다.

권장 순서:

1. “여기 주문이요” 또는 “주문할게요”  
2. “햄치즈샌드위치”  
3. “추가주문”  
4. “머쉬룸샌드위치”  
5. “주문 완료”  
6. “네”

### 3.4 확인할 것 (Phase B)

- Mock Backend 터미널에 `order_request` 2건(햄치즈 1, 머쉬룸 1) 수신 로그가 찍히는지  
- `http://localhost:8000/static/monitor.html` 에 위 턴들이 기록되는지  
- 각 Agent 안내가 **스피커로 재생**되는지  

---

## 4. Phase C – 실제 Backend + DB 저장 확인

목적: Voice 서버가 **실제 Main Server(Backend)** 로 주문을 보내고, 주문이 **DB(pinky_robot_store)** 에 저장되는지 확인합니다.

### 4.1 Backend(Main Server)용 DB 설정 확인

- **파일**: `app/backend/config/database.env`  
- **내용**: 아래와 동일한지 확인합니다 (이미 0절과 동일하게 설정되어 있음).

```
# Backend → pinky_robot_store (same as db_server)
DB_HOST=192.168.0.27
DB_PORT=5432
DB_NAME=pinky_robot_store
DB_USER=deepdive
DB_PASSWORD=deepdive_team123!#
```

### 4.2 터미널 1: Main Server(Backend) 실행

- **실행 위치**: 프로젝트 루트

**방법 A (권장)** – 루트 워크스페이스 스크립트 사용:

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1
./run_backend_from_workspace.sh
```

**방법 B** – Backend 디렉터리에서 직접 실행:

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1/app/backend
python3 run_main_server.py
```

- **기대 결과**:  
  - “TCP Server started on 0.0.0.0:9999”, “Database connection established” 등이 보이면 정상입니다.  
  - 이 터미널은 **끄지 말고** 유지합니다.  
- **참고**: ROS2/venv 환경이 필요합니다. 방법 A는 스크립트가 venv·빌드 경로를 자동으로 처리합니다.

### 4.3 Voice 서버를 실제 Backend로 전환

- **실행 위치**: `ai_server/voice_processing_server`

Voice 서버가 **실제 Backend(9999)** 를 바라보도록 `.env` 를 수정합니다.

- Main Server를 **같은 PC**에서 실행 중이면:

```
ORDER_BACKEND_HOST=127.0.0.1
ORDER_BACKEND_PORT=9999
```

- Main Server를 **다른 PC**에서 실행 중이면, 그 PC의 IP로 바꿉니다.

```
ORDER_BACKEND_HOST=192.168.0.xx
ORDER_BACKEND_PORT=9999
```

저장한 뒤, **Voice 서버(2.3에서 띄운 uvicorn)를 한 번 종료했다가 다시 실행**합니다.

- **실행 위치**:

```bash
cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1/ai_server/voice_processing_server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

(이때 **Mock Backend(9998)는 끄고**, Main Server(9999)만 켜 두면 됩니다.)

### 4.4 실사용자 테스트 (음성인터페이스 GUI) – 고객 가이드

아래 순서대로 하면 **실제 사용자 음성**으로 OpenAI와 상호작용하여 주문하고, **같은 화면에서 주문 결과**를 확인할 수 있습니다.

#### 1) 음성인터페이스 GUI 실행

- 브라우저(Chrome 등)를 열고 아래 주소로 접속합니다.  
  (Voice 서버를 다른 PC에서 실행 중이면 `localhost` 를 그 PC의 IP로 바꿉니다.)

```
http://localhost:8000/static/index.html
```

- 이 페이지가 **음성 주문용 테스트 GUI(음성인터페이스 GUI)** 입니다.

#### 2) 사용자 음성으로 OpenAI와 상호작용하여 주문

1. 페이지에서 **「6. 음성 주문 (한 턴씩)」** 섹션을 찾습니다.
2. **테이블 번호**를 1~4 중에서 선택합니다.
3. **한 문장씩** 아래 순서대로 진행합니다.  
   각 문장마다 **「녹음 후 주문 턴 전송」** 버튼을 누른 뒤, 말하고, **「중지」**를 누릅니다.

   | 순서 | 말할 내용 (예시) |
   |------|------------------|
   | 1 | "주문할게요" 또는 "여기 주문이요" |
   | 2 | "햄치즈샌드위치" (또는 다른 메뉴명) |
   | 3 | (추가 주문 시) "추가주문" → 다음에 "머쉬룸샌드위치" 등 |
   | 4 | "주문 완료" |
   | 5 | "네" (확정) |

4. 각 턴마다 **인식**, **응답**, **주문 상태**가 화면에 표시되고, 응답 음성은 **오디오 재생**으로 들을 수 있습니다.

#### 3) 주문 결과를 같은 음성 주문 GUI에서 확인

- **같은 페이지(6번 섹션)** 에서 확인할 수 있는 것:
  - **응답**: Agent가 말한 내용(예: "주문이 접수되었습니다").
  - **주문 상태**: 단계(stage)와 담은 항목 개수.

- **최근 주문 시도 전체**를 보려면 브라우저에서 아래 주소를 엽니다.

```
http://localhost:8000/static/monitor.html
```

- **실제 DB에 저장된 주문**은 아래 **5. DB에서 주문 결과 확인** 절의 `psql` 명령으로 확인합니다.

### 4.5 주문 플로우 한 번 실행 (curl – 개발자용)

- **2.5** 와 같은 순서로, 터미널에서 아래를 **순서대로** 실행합니다.  
  (Voice 서버 주소가 다른 PC면 `localhost` 를 그 PC IP로 바꿉니다.)

```bash
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"주문할게요","table_number":1}'
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"햄치즈샌드위치","table_number":1}'
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"주문 완료","table_number":1}'
curl -s -X POST "http://localhost:8000/agent/order_turn" -H "Content-Type: application/json" -d '{"session_id":"default","text":"네","table_number":1}'
```

- **기대**: 마지막 응답에 “주문이 접수되었습니다” 와 함께 `order_ids` 에 실제 UUID가 나옵니다.  
  이 ID를 복사해 두면, 다음 단계에서 DB 조회할 때 편합니다.

---

## 5. DB에서 주문 결과 확인

Phase C까지 진행했다면, 주문이 **pinky_robot_store** DB의 `orders` 테이블에 저장되어 있어야 합니다.  
아래는 **복사해서 그대로 쓸 수 있는** 확인 방법입니다.

### 5.1 psql이 설치되어 있는지 확인

- **실행 위치**: 아무 터미널에서나

```bash
which psql
```

- **기대**: `/usr/bin/psql` 같은 경로가 나오면 됩니다. 없으면 PostgreSQL 클라이언트를 설치한 뒤 진행합니다.

### 5.2 DB 접속 정보 (복사용)

테스트에 사용하는 값입니다.

| 항목 | 값 |
|------|-----|
| 호스트 | 192.168.0.27 |
| 포트 | 5432 |
| DB 이름 | pinky_robot_store |
| 사용자 | deepdive |
| 비밀번호 | deepdive_team123!# |

### 5.3 최근 주문 N건 조회 (복사해서 실행)

- **실행 위치**: 아무 터미널에서나  
- **역할**: `orders` 테이블에서 최근 10건을 보여줍니다. `voice_order` 가 `t` 이면 음성 주문으로 들어온 것입니다.

**한 줄 전체**를 복사해 터미널에 붙여 넣고 실행하세요.

```bash
PGPASSWORD="deepdive_team123!#" psql -h 192.168.0.27 -p 5432 -U deepdive -d pinky_robot_store -c "SELECT id, table_number, menu_id, quantity, status, voice_order, created_at FROM orders ORDER BY created_at DESC LIMIT 10;"
```

- **기대**:  
  - Phase C에서 방금 넣은 주문이 맨 위에 보이고,  
  - `voice_order` 컬럼이 `t` 이고, `table_number` 가 `1`, `menu_id` 가 `M001` 등으로 나오면 정상입니다.

### 5.4 특정 주문 ID로 한 건만 조회 (선택)

Phase C 마지막 응답에서 받은 `order_ids` 중 하나(예: `abc12345-...`)를 알고 있을 때, 그 ID만 보고 싶다면 아래처럼 실행합니다.  
`'여기에-주문-uuid'` 부분을 **실제 주문 ID**로 바꿉니다.

```bash
PGPASSWORD="deepdive_team123!#" psql -h 192.168.0.27 -p 5432 -U deepdive -d pinky_robot_store -c "SELECT id, table_number, menu_id, quantity, status, voice_order, created_at FROM orders WHERE id = '여기에-주문-uuid';"
```

---

## 6. 요약: 복사용 체크리스트

- **프로젝트 루트**: `cd /home/addinedu/Documents/team_syncronized/roscamp-repo-1` (본인 경로로 변경 가능)
- **DB 계정**: Host 192.168.0.27, Port 5432, DB pinky_robot_store, User deepdive, Password deepdive_team123!#
- **Phase A**: Mock Backend(9998) + Voice(8000) 띄운 뒤, `http://localhost:8000/agent/order_turn` 에 curl 6번 호출 → Mock 터미널 로그 + `http://localhost:8000/static/monitor.html` 로 확인
- **Phase B**: 같은 구성 + `OPENAI_API_KEY` 설정 후 `http://localhost:8000/static/index.html` 에서 녹음·재생으로 스피커 확인
- **Phase C (실사용자 테스트)**:  
  1) Main Server(9999) 실행: `./run_backend_from_workspace.sh` (또는 `app/backend` 에서 `python3 run_main_server.py`)  
  2) Voice `.env` 를 `ORDER_BACKEND_HOST=127.0.0.1`, `ORDER_BACKEND_PORT=9999` 로 설정 후 Voice 서버 재시작  
  3) **음성인터페이스 GUI**: 브라우저 `http://localhost:8000/static/index.html` → **「6. 음성 주문 (한 턴씩)」** 에서 테이블 선택 후 음성으로 한 문장씩 주문  
  4) 주문 결과: 같은 화면의 응답·주문 상태 + `http://localhost:8000/static/monitor.html` + **5.3** `psql` 명령으로 DB 확인

이 문서만 보고도, **실행 위치**와 **복사 가능한 커맨드/URL**만 따라 하면 통합 테스트를 끝까지 진행할 수 있습니다.
