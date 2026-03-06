# Zone Manager 사전 예약 시스템

## 빠른 시작

Zone Manager는 Kitchmatics FMS에서 다중 로봇 조율을 위한 사전 예약 기반의 종합 충돌 회피 시스템을 구현합니다.

### 기본 사용법

```python
from fms.zone_manager import ZoneManager

# 매니저 초기화 (설정에서 구역 정보 로드)
manager = ZoneManager()

# 진입 전 구역 예약
manager.reserve_zone('pinky1', 'zone_pickup')

# 로봇 진입 시 구역 점유
manager.occupy_zone('pinky1', 'zone_pickup')

# 로봇 퇴장 시 구역 해제
manager.leave_zone('pinky1', 'zone_pickup')

# 구역 사용 가능 여부 확인
if manager.is_zone_available('zone_table1'):
    manager.reserve_zone('pinky1', 'zone_table1')
```

## 핵심 기능

### 1. 사전 예약 시스템

로봇이 내비게이션 전에 구역을 예약하여 독점 접근을 보장합니다.

**장점:**
- 다중 로봇 간 충돌 방지
- 로봇 도착 시 구역 사용 가능 보장
- 예약은 30초 후 만료 (설정 가능)
- 다른 로봇이 예약된 구역을 차단할 수 없음

### 2. 3단계 구역 관리

```
AVAILABLE → RESERVED → OCCUPIED → AVAILABLE
                ↓
           EXPIRED
```

**Available:** 구역이 비어 있으며, 모든 로봇이 예약 가능

**Reserved:** 특정 로봇에게 예약됨 (최대 30초 타임아웃)

**Occupied:** 로봇이 물리적으로 구역을 점유 중

**Expired:** 예약 타임아웃 경과 (자동 정리 필요)

### 3. 충돌 감지

계획된 경로에 충돌이 있는지 확인:

```python
path_zones = ['zone_parking1', 'zone_point1', 'zone_pickup']
conflicts = manager.check_path_conflicts('pinky1', path_zones)

if conflicts:
    print(f"Path blocked: {conflicts}")
    # 경로 재계획 또는 대기
else:
    # 경로 예약 후 내비게이션
    for zone_id in path_zones:
        manager.reserve_zone('pinky1', zone_id)
```

### 4. 주기적 정리

만료된 예약은 주기적으로 정리해야 합니다:

```python
# 메인 FMS 루프에서 5초마다 호출
cleaned = manager.cleanup_expired_reservations()
if cleaned > 0:
    logger.info(f"Cleaned {cleaned} expired zones")
```

## API 메서드

### 예약 연산

| 메서드 | 용도 | 반환값 |
|--------|------|--------|
| `reserve_zone(robot_id, zone_id)` | 로봇을 위한 구역 예약 | bool |
| `release_reservation(robot_id, zone_id)` | 예약 취소 | bool |
| `occupy_zone(robot_id, zone_id)` | 구역을 점유 상태로 전환 | bool |
| `leave_zone(robot_id, zone_id)` | 점유 구역 해제 | bool |

### 조회 연산

| 메서드 | 용도 | 반환값 |
|--------|------|--------|
| `is_zone_available(zone_id)` | 구역 예약 가능 여부 확인 | bool |
| `get_zone_status(zone_id)` | 구역 상세 상태 조회 | dict |
| `get_all_zones_status()` | 전체 구역 상태 조회 | list[dict] |
| `get_robot_reserved_zones(robot_id)` | 로봇의 예약 구역 조회 | list[str] |
| `get_robot_occupied_zones(robot_id)` | 로봇의 점유 구역 조회 | list[str] |

### 충돌 감지

| 메서드 | 용도 | 반환값 |
|--------|------|--------|
| `check_path_conflicts(robot_id, path_zones)` | 경로 검증 | list[str] |
| `check_collision_risk(robot_id, zone_id)` | 빠른 충돌 확인 | bool |

### 유지보수

| 메서드 | 용도 | 반환값 |
|--------|------|--------|
| `cleanup_expired_reservations()` | 만료된 예약 제거 | int |
| `clear_robot(robot_id)` | 오프라인 로봇 긴급 정리 | None |
| `get_zone_by_location(location_name)` | 위치명을 구역 ID로 변환 | str |

## 일반적인 배달 흐름

```python
def complete_delivery(robot_id, table_number):
    """구역 관리를 포함한 배달 수행"""
    manager = ZoneManager()

    # 1. 픽업 구역 예약 및 점유
    if not manager.reserve_zone(robot_id, 'zone_pickup'):
        print("Pickup busy")
        return False

    navigate_to('pickup_spot', robot_id)
    manager.occupy_zone(robot_id, 'zone_pickup')

    # 2. 음식 적재 대기 (외부 시스템)
    wait_for_food_loaded()

    # 3. 배달 테이블 예약
    table_zone = manager.get_zone_by_location(f'table{table_number}')
    if not manager.reserve_zone(robot_id, table_zone):
        print("Table busy, try another")
        return False

    manager.leave_zone(robot_id, 'zone_pickup')

    # 4. 테이블로 이동 및 점유
    navigate_to(f'table{table_number}', robot_id)
    manager.occupy_zone(robot_id, table_zone)

    # 5. 배달 확인 대기
    wait_for_customer_confirmation()

    manager.leave_zone(robot_id, table_zone)

    # 6. 주차 지점 복귀
    parking_zone = manager.get_zone_by_location(f'{robot_id}_spot')
    manager.reserve_zone(robot_id, parking_zone)
    navigate_to('parking_spot', robot_id)
    manager.occupy_zone(robot_id, parking_zone)

    return True
```

## 설정

구역은 `fms/config/fms_config.yaml`에 정의됩니다:

```yaml
zones:
  - id: "zone_pickup"
    center_x: 0.47
    center_y: 0.63
    radius: 0.10
    reservation_timeout: 30.0  # 선택 사항

  - id: "zone_table1"
    center_x: 1.785
    center_y: 0.35
    radius: 0.10
```

### 구역 매개변수

- **id**: 고유 구역 식별자
- **center_x, center_y**: 중심 좌표 (미터)
- **radius**: 충돌 판정용 구역 반경 (미터)
- **reservation_timeout**: 예약 만료까지의 시간(초) (선택 사항, 기본값 30)

## 사용 가능한 구역

### 픽업 구역
- `zone_pickup` → 위치: `pickup_spot`

### 테이블 구역
- `zone_table1` ~ `zone_table8` → 위치: `table1` ~ `table8`

### 주차 구역
- `zone_parking1` → 위치: `pinky1_spot`
- `zone_parking2` → 위치: `pinky2_spot`
- `zone_parking3` → 위치: `pinky3_spot`

### 웨이포인트 구역
- `zone_point1` ~ `zone_point4` → 왼쪽 웨이포인트
- `zone_point13` → 픽업 접근 지점

## 다중 로봇 조율 예제

```python
def schedule_multi_robot_delivery(orders, manager):
    """충돌 회피를 적용한 다중 배달 스케줄링"""

    for order in orders:
        robot = select_best_robot(order)

        # 필요한 구역 확인
        pickup_zone = 'zone_pickup'
        table_zone = manager.get_zone_by_location(f'table{order.table}')
        parking_zone = manager.get_zone_by_location(f'{robot}_spot')

        # 모든 구역을 한 번에 예약 시도
        if (manager.reserve_zone(robot, pickup_zone) and
            manager.reserve_zone(robot, table_zone)):

            # 배달 작업 생성
            task = Task(
                robot_id=robot,
                order_id=order.id,
                table=order.table,
                zones=[pickup_zone, table_zone, parking_zone]
            )
            schedule_task(task)
        else:
            # 구역 사용 불가, 나중에 재시도
            queue_order(order)
```

## 테스트

종합 테스트 스위트 실행:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
```

**테스트 범위:**
- 구역 생성 및 상태 전이
- 단일 및 다중 로봇 조율
- 경로 충돌 감지
- 예약 만료
- 전체 배달 흐름
- 긴급 정리

## 사용 예제

예제 시나리오 실행:

```bash
python3 fms/scripts/zone_manager_example.py
```

**포함 내용:**
1. 단일 로봇 배달 흐름
2. 다중 로봇 조율
3. 경로 검증
4. 만료 및 정리
5. 긴급 정리
6. 구역 모니터링

## 문제 해결

### 구역이 예약/점유 상태로 유지됨

**증상:** `is_zone_available()`이 False를 반환

**원인:**
- 다른 로봇이 실제로 구역을 사용 중 (`get_zone_status()` 확인)
- 로봇이 구역을 해제하지 않고 비정상 종료
- 예약이 타임아웃되지 않음

**해결:**
```python
# 구역 상태 확인
status = manager.get_zone_status('zone_pickup')
print(status['occupied_by'], status['reserved_by'])

# 오프라인 로봇으로 인한 고아 구역인 경우:
manager.clear_robot('pinky1')

# 주기적 정리가 호출되고 있는지 확인
manager.cleanup_expired_reservations()
```

### 다중 로봇 교착 상태

**증상:** 로봇끼리 서로 차단

**원인:**
- 비효율적인 경로 계획
- 구역 예약 타임아웃이 너무 김
- 로봇이 순환 의존성으로 구역을 예약

**해결:**
- 경로 확정 전에 `check_path_conflicts()` 사용
- 전체 경로를 한 번에 예약 (전부 아니면 전무)
- 트래픽이 많은 구역의 타임아웃 단축
- 교차를 피하는 경로 계획

### 구역 접근 지연

**증상:** 예약 실패가 빈번

**원인:**
- 같은 구역에 너무 많은 로봇이 경쟁
- 타임아웃이 너무 김 (로봇이 구역을 오래 점유)
- 충돌 감지 시 경로 재계획 없음

**해결:**
- 핫스팟 구역에 우선순위 대기열 구현
- 혼잡 지역의 예약 타임아웃 단축
- 충돌 시 자동 경로 재계획 추가
- 인접 지역에 대한 구역 그룹 고려

## FMS 통합

FMS 노드에 Zone Manager 추가:

```python
class FMSNode:
    def __init__(self):
        # 설정 로드
        config = load_yaml('fms/config/fms_config.yaml')

        # Zone Manager 초기화
        self.zone_manager = ZoneManager(config)

        # 정리 타이머 생성
        self.cleanup_timer = self.create_timer(
            5.0,  # 5초마다
            self.cleanup_expired_zones
        )

    def cleanup_expired_zones(self):
        """주기적 정리 콜백"""
        cleaned = self.zone_manager.cleanup_expired_reservations()
        if cleaned > 0:
            self.get_logger().info(f"Cleaned {cleaned} expired zones")

    def handle_new_order(self, order):
        """구역 조율을 적용한 배달 할당"""
        robot = self.select_robot(order)

        # 구역 확인
        pickup = 'zone_pickup'
        table = self.zone_manager.get_zone_by_location(f'table{order.table}')

        # 구역 예약
        if not self.zone_manager.reserve_zone(robot, pickup):
            return False
        if not self.zone_manager.reserve_zone(robot, table):
            self.zone_manager.release_reservation(robot, pickup)
            return False

        # 작업 할당
        self.assign_delivery_task(robot, order)
        return True
```

## 성능

**메모리:** 구역당 ~1KB + 로봇 추적 (20개 구역, 3대 로봇 기준 무시 가능)

**CPU:** O(1) 구역 조회, O(경로 길이) 충돌 확인

**확장성:** 17개 구역과 3대 로봇 동시 운영 테스트 완료

## 향후 개선 사항

- 구역 트래픽에 따른 동적 타임아웃 조정
- 시간 민감 배달을 위한 우선순위 대기열
- 조율된 다중 구역 접근을 위한 구역 그룹
- 구역 점유 시각화 플러그인
- 마감 시간 인식 예약 (특정 시간까지 예약)
- 머신러닝 기반 경로 계획 통합

## 파일

| 파일 | 용도 |
|------|------|
| `/fms/fms/zone_manager.py` | 핵심 구현 |
| `/fms/tests/test_zone_manager_reservation.py` | 30개의 종합 테스트 |
| `/fms/ZONE_RESERVATION_GUIDE.md` | 상세 API 문서 |
| `/fms/scripts/zone_manager_example.py` | 사용 예제 |
| `/fms/config/fms_config.yaml` | 구역 설정 |

## 참고 자료

- **ZONE_RESERVATION_GUIDE.md**: 상세 API 문서
- **zone_manager_example.py**: 전체 동작 예제
- **test_zone_manager_reservation.py**: 테스트 케이스 및 사용 패턴

## 궁금한 점이 있다면?

다음을 참고하세요:
1. ZONE_RESERVATION_GUIDE.md - 상세 API 문서
2. zone_manager_example.py - 동작하는 코드 예제
3. 테스트 케이스 - 엣지 케이스 및 오류 처리
