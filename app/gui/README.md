# 식당 주문 키오스크 GUI

PyQt5 기반 고객용 주문 키오스크 GUI 애플리케이션

## 프로젝트 구조

```
ui_sample/
├── customer_gui/           # 고객용 GUI
│   ├── ui/                # Qt Designer .ui 파일들
│   │   ├── main_window.ui
│   │   ├── menu_selection.ui
│   │   ├── order_confirmation.ui
│   │   └── delivery_notification.ui
│   ├── src/               # Python 소스 파일들
│   │   ├── main.py
│   │   ├── ui_main_window.py
│   │   ├── ui_menu_selection.py
│   │   ├── ui_order_confirmation.py
│   │   ├── ui_delivery_notification.py
│   │   ├── voice_feedback_widget.py
│   │   └── tcp_client.py
│   └── resources/         # 리소스 파일
│       └── style.qss
│
├── admin_gui/             # 관리자용 GUI
│   ├── ui/                # Qt Designer .ui 파일들
│   │   ├── dashboard.ui
│   │   ├── cooking_monitor.ui
│   │   ├── recipe_management.ui
│   │   └── stock_management.ui
│   ├── src/               # Python 소스 파일들
│   │   ├── main.py
│   │   ├── ui_dashboard.py
│   │   ├── ui_cooking_monitor.py
│   │   ├── ui_recipe_management.py
│   │   ├── ui_stock_management.py
│   │   ├── ui_fleet_monitor.py      # 🚗 서빙 로봇 모니터링 (새로 추가!)
│   │   ├── tcp_client.py
│   │   └── fleet_client.py           # Main Server 전용 TCP 클라이언트
│   └── resources/         # 리소스 파일
│       └── style.qss
│
├── common/                # 공통 모듈
│   ├── config.py
│   ├── models.py
│   └── __init__.py
│
├── .env                   # 환경 변수 설정
├── .env.example           # 환경 변수 예시
├── requirements.txt       # Python 패키지 의존성
└── README.md
```

## 기능 구현 상태

### 고객용 GUI

| 기능 | 설명 | 상태 |
|------|------|------|
| SR-01 | 메뉴 제공 | ✅ |
| SR-02 | 주문 시작 | ✅ |
| SR-03a | 화면 주문 (메뉴 선택, 수량 조절, 장바구니) | ✅ |
| SR-03b | 음성 주문 (시각적 피드백) | ✅ |
| SR-04 | 무효 주문 차단 (품절 메뉴 경고) | ✅ |
| SR-05 | 주문 내용 확인 (영수증 형태) | ✅ |
| SR-06 | 주문 전송 | ✅ |
| SR-16 | 도착 알림 및 수령 확인 | ✅ |

### 관리자용 GUI

| 기능 | 설명 | 상태 |
|------|------|------|
| SR-07 | 주문 모니터링 (목록, 정렬, 강제 개입, 히스토리) | ✅ |
| SR-08 | 주문 취소 | ✅ |
| SR-11 | 레시피 관리 (CRUD) | ✅ |
| SR-12 | 조리 모니터링 | ✅ |
| SR-13 | 조리 완료 알림, 음식 검수 | ✅ |
| SR-15 | 서빙 출발 제어 | ✅ |
| SR-19 | 재고 알림, 재고 수정 | ✅ |
| SR-20 | 재고 조회 | ✅ |
| **NEW** | **서빙 로봇 Fleet 모니터링** | ✅ |

### 화면 구성

#### 고객용 GUI 화면
1. **주문 시작 화면** - 주문 시작 버튼
2. **메뉴 선택 화면** - 메뉴 리스트, 장바구니, 수량 조절
3. **주문 확인 화면** - 영수증 형태로 주문 내용 표시
4. **수령 확인 화면** - 음식 도착 알림 및 수령 완료 버튼

#### 관리자용 GUI 화면
1. **주문 관제 대시보드** - 실시간 주문 목록, 상태 필터링, 주문 개입 (취소/일시중지)
2. **조리 상태 모니터링** - 조리 중/완료/검수 완료 주문, 검수 완료 및 서빙 출발 제어
3. **레시피 관리** - 레시피 CRUD, 재료 및 조리 단계 관리
4. **재고 관리** - 재고 조회, 수량 변경, 재고 부족 알림
5. **🚗 서빙 로봇 Fleet 모니터링** (**NEW!**) - 3대 서빙 로봇(pinky1/2/3) 실시간 상태 모니터링
   - Fleet 통계 (전체/대기/작업 중 로봇 수, 대기/진행 중 주문 수)
   - 로봇별 상태, 배터리 전압, 현재 작업 표시
   - 상태별/배터리별 색상 시각화

### 추가 기능

- 음성 인식 시각적 피드백 위젯 (파형 애니메이션)
- TCP 통신 클라이언트 (주문 MS와 통신)
- Mock 클라이언트 (테스트용)
- 밝은 컬러 테마 스타일시트

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

`.env` 파일을 편집하여 설정을 조정합니다:

```bash
# 테이블 번호 설정
TABLE_NUMBER=1

# 화면 크기 및 전체화면 모드
SCREEN_WIDTH=1024
SCREEN_HEIGHT=768
FULLSCREEN=false

# TCP 서버 주소 (필요시 수정)
ORDER_MS_HOST=127.0.0.1
ORDER_MS_PORT=5000
```

### 3. 실행

#### 고객용 GUI 실행
```bash
cd customer_gui/src
python main.py
```

#### 관리자용 GUI 실행
```bash
cd admin_gui/src
python main.py
```

## 개별 화면 테스트

각 화면을 개별적으로 테스트할 수 있습니다:

### 고객용 GUI 화면 테스트
```bash
# 주문 시작 화면
python customer_gui/src/ui_main_window.py

# 메뉴 선택 화면
python customer_gui/src/ui_menu_selection.py

# 주문 확인 화면
python customer_gui/src/ui_order_confirmation.py

# 수령 확인 화면
python customer_gui/src/ui_delivery_notification.py

# 음성 피드백 위젯
python customer_gui/src/voice_feedback_widget.py

# TCP 클라이언트
python customer_gui/src/tcp_client.py
```

### 관리자용 GUI 화면 테스트
```bash
# 주문 관제 대시보드
python admin_gui/src/ui_dashboard.py

# 조리 상태 모니터링
python admin_gui/src/ui_cooking_monitor.py

# 레시피 관리
python admin_gui/src/ui_recipe_management.py

# 재고 관리
python admin_gui/src/ui_stock_management.py

# TCP 클라이언트 (Mock)
python admin_gui/src/tcp_client.py

# 🚗 서빙 로봇 Fleet 모니터링 (NEW!)
python admin_gui/src/ui_fleet_monitor.py

# Fleet 클라이언트 (Mock)
python admin_gui/src/fleet_client.py
```

### 서빙 로봇 Fleet 모니터링 사용법

#### Mock 모드 (서버 없이 테스트)
```bash
cd admin_gui/src
python main.py  # 기본적으로 Mock 모드
```

"🚗 서빙 로봇" 탭으로 이동하면 Mock 데이터로 3대 로봇 상태를 볼 수 있습니다.

#### 실제 서버 연결 모드

**사전 요구사항**:
1. Main Server 실행 (포트 9999)
2. FMS 실행
3. 3대 서빙 로봇 (/pinky1, /pinky2, /pinky3) 실행

**실행**:
```bash
# 터미널 1: Main Server
cd /path/to/backend
ros2 run main_server main_server

# 터미널 2: FMS
cd /path/to/fms
ros2 launch fms fms_launch.py

# 터미널 3: Admin GUI
cd admin_gui/src
USE_MOCK=false python main.py
```

**Main Server IP 변경이 필요한 경우**:
```python
# fleet_client.py 수정
client = FleetClient(host='192.168.1.100', port=9999)  # Main Server IP
```

## 현재 메뉴

1. **햄치즈샌드위치** (5,000원)
   - 재료: 빵, 양상추, 토마토, 치즈, 햄 (아래부터 위로 쌓음)
   - 조리 시간: 약 7분 20초

2. **머쉬룸샌드위치** (5,500원)
   - 재료: 빵, 버섯, 토마토, 치즈, 햄 (아래부터 위로 쌓음)
   - 조리 시간: 약 10분 20초

3. **올인원샌드위치** (6,500원)
   - 재료: 빵, 토마토, 치즈, 햄, 버섯, 양상추 (아래부터 위로 쌓음)
   - 조리 시간: 약 11분 40초

메뉴는 `customer_gui/src/tcp_client.py`의 `MockOrderServiceClient.fetch_menus()` 메서드와 `admin_gui/src/tcp_client.py`의 `MockAdminServiceClient.mock_recipes`에서 수정할 수 있습니다.

## 주요 기술 스택

- **GUI 프레임워크**: PyQt5
- **통신**: TCP Socket
- **설정 관리**: python-dotenv
- **디자인**: Qt Designer (.ui 파일)

## 화면 조작

- **ESC 키**: 전체화면 모드 해제 또는 종료
- 터치스크린 지원 (마우스 클릭으로 대체 가능)

## 데이터 모델

### 기본 모델
- **MenuItem**: 메뉴 아이템 (menu_id, name, price, available 등)
- **Order**: 주문 (order_id, table_number, items, status, total_price 등)
- **OrderStatus**: 주문 상태 (pending, confirmed, cooking, ready, inspected, delivering, delivered, completed, cancelled, halted)

### Admin 전용 모델
- **Recipe**: 레시피 (재료 리스트, 조리 단계, 조리 시간, 난이도)
- **Ingredient**: 재료 (ingredient_id, name, unit, allergens)
- **Stock**: 재고 (재료, 수량, 임계값, 공급업체 정보)
- **Supplier**: 공급업체 정보
- **ServingStatus**: 서빙 상태 (waiting, called, moving, arrived, error, delayed)

## 다음 단계

- [ ] 실제 TCP 서버 연동 (주문 MS, 레시피 MS, 재고 MS)
- [ ] 음성 인식 백엔드 연동
- [x] 관리자 GUI 구현 (완료)
- [x] **서빙 로봇 Fleet 모니터링 구현 (완료)** ✅
- [ ] Main Server와 실제 연동 테스트
- [ ] 이미지 리소스 추가
- [ ] 다국어 지원
- [ ] 실시간 알림 강화 (서빙 오류 알림 등)

## 라이선스

MIT License

## 개발자

Restaurant System Development Team
