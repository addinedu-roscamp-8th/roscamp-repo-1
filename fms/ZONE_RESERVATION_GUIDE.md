# Zone Manager - 사전 예약 시스템 가이드

## 개요

Zone Manager는 Kitchmatics FMS에서 다중 로봇 운영을 조율하기 위한 사전 예약 메커니즘을 갖춘 종합 구역 기반 충돌 회피 시스템을 구현합니다.

### 핵심 개념

**구역(Zone)**: 지도 위 중요 위치(픽업, 테이블, 주차 지점, 웨이포인트) 주변의 원형 영역

**예약(Reservation)**: 로봇이 도착 시 독점 접근을 보장하기 위해 구역을 사전 예약 (최대 30초)

**점유(Occupation)**: 로봇이 물리적으로 구역에 진입한 후 해당 구역을 점유하는 상태

**충돌(Conflict)**: 다른 로봇이 이미 예약 또는 점유 중인 구역을 사용하려 할 때 발생

## 아키텍처

### Zone 클래스

지도 위 단일 구역을 나타내며 충돌 회피 속성을 포함합니다.

**속성:**
- `zone_id`: 고유 식별자 (예: 'zone_pickup', 'zone_table1')
- `center_x`, `center_y`: 구역 중심 좌표 (미터)
- `radius`: 구역 반경 (미터)
- `occupied_by`: 현재 구역에 있는 로봇 ID (비어있으면 None)
- `reserved_by`: 구역을 예약한 로봇 ID (예약 없으면 None)
- `reserved_at`: 예약 시각 타임스탬프
- `reservation_timeout`: 예약 만료까지의 시간(초) (기본값: 30.0)

**상태 머신:**
```
AVAILABLE → RESERVED → OCCUPIED → AVAILABLE
                ↓
           EXPIRED
```

### ZoneManager 클래스

모든 구역을 관리하고 다중 로봇 접근을 조율합니다.

**핵심 책임:**
1. 구역 초기화 및 관리
2. 구역 사전 예약
3. 점유 상태 추적
4. 만료 및 정리
5. 충돌 감지
6. 경로 검증

## API 레퍼런스

### 핵심 메서드

#### `reserve_zone(robot_id: str, zone_id: str) -> bool`

로봇을 위해 구역을 사전 예약합니다.

**매개변수:**
- `robot_id`: 로봇 식별자
- `zone_id`: 구역 식별자

**반환값:** 성공 시 True, 구역 사용 불가 시 False

**예제:**
```python
manager = ZoneManager()
if manager.reserve_zone('pinky1', 'zone_pickup'):
    print("Reservation successful")
else:
    print("Zone already reserved or occupied")
```

**동작:**
- 구역이 완전히 사용 가능한 경우(점유도 예약도 아닌 경우)에만 작동
- 예약 타임스탬프 기록
- 다른 로봇의 해당 구역 접근을 차단

#### `occupy_zone(robot_id: str, zone_id: str) -> bool`

구역을 예약 상태에서 점유 상태로 전환합니다.

**매개변수:**
- `robot_id`: 로봇 식별자
- `zone_id`: 구역 식별자

**반환값:** 성공 시 True, 그 외 False

**예제:**
```python
# 구역으로 내비게이션 후
if manager.occupy_zone('pinky1', 'zone_pickup'):
    print("Zone entered successfully")
```

**동작:**
- 해당 로봇이 예약했거나 구역이 사용 가능한 경우 점유 가능
- 예약 해제 (한 로봇이 예약 후 무기한 점유하는 것을 방지)
- 구역을 활발히 점유 중으로 표시

#### `leave_zone(robot_id: str, zone_id: str) -> bool`

로봇 퇴장 후 구역을 해제합니다.

**매개변수:**
- `robot_id`: 로봇 식별자
- `zone_id`: 구역 식별자

**반환값:** 성공 시 True, 로봇이 구역 소유자가 아닌 경우 False

**예제:**
```python
# 배달 완료 또는 다음 구역으로 이동 후
manager.leave_zone('pinky1', 'zone_table1')
```

**동작:**
- 해당 로봇이 점유 중인 경우에만 작동
- 다른 로봇이 예약할 수 있도록 구역 해제
- 로봇이 구역 영역을 벗어날 때 호출해야 함

#### `release_reservation(robot_id: str, zone_id: str) -> bool`

구역 예약을 해제합니다 (점유하지 않고).

**매개변수:**
- `robot_id`: 로봇 식별자
- `zone_id`: 구역 식별자

**반환값:** 예약이 존재했으면 True, 아니면 False

**예제:**
```python
# 더 높은 우선순위의 주문이 들어와 계획된 배달을 취소하는 경우
manager.release_reservation('pinky1', 'zone_table1')
```

**동작:**
- 해당 로봇이 예약한 경우에만 작동
- 로봇의 계획이 변경될 때 사용
- 점유 중인 구역에는 영향 없음

### 조회 메서드

#### `is_zone_available(zone_id: str) -> bool`

구역 예약 가능 여부를 확인합니다.

**예제:**
```python
if manager.is_zone_available('zone_pickup'):
    manager.reserve_zone('pinky2', 'zone_pickup')
```

#### `get_zone_status(zone_id: str) -> Dict`

구역의 상세 상태를 조회합니다.

**반환값:** 다음을 포함하는 딕셔너리:
- `zone_id`: 구역 식별자
- `occupied_by`: 현재 점유자 (또는 None)
- `reserved_by`: 현재 예약자 (또는 None)
- `reserved_at`: 예약 ISO 타임스탬프
- `reservation_age_sec`: 예약 이후 경과 시간(초)
- `reservation_timeout`: 타임아웃 기간
- `is_reservation_expired`: 만료 여부 불리언 플래그
- `available`: 사용 가능 여부 불리언 플래그

**예제:**
```python
status = manager.get_zone_status('zone_pickup')
print(f"Zone occupied by: {status['occupied_by']}")
print(f"Reserved by: {status['reserved_by']}")
print(f"Available: {status['available']}")
```

#### `get_all_zones_status() -> List[Dict]`

모든 구역의 상태를 한 번에 조회합니다.

**예제:**
```python
for zone_status in manager.get_all_zones_status():
    if not zone_status['available']:
        print(f"{zone_status['zone_id']} is in use")
```

#### `get_robot_reserved_zones(robot_id: str) -> List[str]`

로봇이 현재 예약한 모든 구역을 조회합니다.

**예제:**
```python
reserved = manager.get_robot_reserved_zones('pinky1')
print(f"Robot has {len(reserved)} zones reserved")
```

#### `get_robot_occupied_zones(robot_id: str) -> List[str]`

로봇이 현재 점유한 모든 구역을 조회합니다.

**예제:**
```python
occupied = manager.get_robot_occupied_zones('pinky1')
for zone_id in occupied:
    print(f"Robot is in {zone_id}")
```

### 경로 및 충돌 감지

#### `check_path_conflicts(robot_id: str, path_zones: List[str]) -> List[str]`

계획된 경로에 구역 충돌이 있는지 확인합니다.

**매개변수:**
- `robot_id`: 로봇 식별자
- `path_zones`: 계획된 경로의 구역 ID 목록

**반환값:** 충돌이 있는 구역 ID 목록 (충돌 없으면 빈 목록)

**예제:**
```python
path = ['zone_parking1', 'zone_point1', 'zone_pickup', 'zone_table1']
conflicts = manager.check_path_conflicts('pinky1', path)

if conflicts:
    print(f"Path blocked by: {conflicts}")
    # 경로 재계획
else:
    # 경로 구역 예약
    for zone_id in path:
        manager.reserve_zone('pinky1', zone_id)
```

**동작:**
- 다른 로봇이 점유한 구역 반환
- 다른 로봇이 예약한 구역 반환
- 요청 로봇이 예약한 구역은 포함하지 않음
- 내비게이션 확정 전 경로 검증에 사용

#### `check_collision_risk(robot_id: str, target_zone_id: str) -> bool`

구역 진입 시 충돌 발생 여부를 빠르게 확인합니다.

**예제:**
```python
if manager.check_collision_risk('pinky1', 'zone_pickup'):
    print("Zone occupied, wait")
else:
    manager.reserve_zone('pinky1', 'zone_pickup')
```

### 유지보수 및 정리

#### `cleanup_expired_reservations() -> int`

타임아웃이 초과된 예약을 제거합니다.

**반환값:** 정리된 예약 수

**예제:**
```python
# 주기적으로 호출 (예: 5초마다)
expired_count = manager.cleanup_expired_reservations()
if expired_count > 0:
    logger.info(f"Cleaned up {expired_count} expired reservations")
```

**동작:**
- 모든 구역에서 만료된 예약 확인
- 구역별 기본 타임아웃은 30초
- 정리된 구역 로깅
- 해당 구역을 다른 로봇이 사용할 수 있도록 해제

#### `clear_robot(robot_id: str)`

긴급 정리: 로봇의 모든 구역을 해제합니다.

**예제:**
```python
# 로봇 오류 발생 또는 오프라인 전환 시
manager.clear_robot('pinky1')
```

**동작:**
- 모든 점유 구역 해제
- 모든 예약 구역 해제
- 내부 추적에서 제거
- 로봇 오류 감지 시 사용

### 유틸리티 메서드

#### `get_zone_by_location(location_name: str) -> Optional[str]`

위치명을 구역 ID로 변환합니다.

**지원되는 위치명:**
- `pickup_spot` → `zone_pickup`
- `table1` ~ `table8` → `zone_table1` ~ `zone_table8`
- `pinky1_spot`, `pinky2_spot`, `pinky3_spot` → `zone_parking1` ~ `zone_parking3`

**예제:**
```python
zone_id = manager.get_zone_by_location('table3')
manager.reserve_zone('pinky1', zone_id)
```

## 일반적인 사용 패턴

### 단일 로봇 배달

```python
manager = ZoneManager()
robot_id = 'pinky1'

# 1. 픽업 구역 예약
if not manager.reserve_zone(robot_id, 'zone_pickup'):
    print("Pickup busy, wait")
    return

# 2. 픽업으로 내비게이션
navigate_to_pickup_spot(robot_id)

# 3. 도착 시 픽업 구역 점유
manager.occupy_zone(robot_id, 'zone_pickup')

# 4. 음식 적재 (외부 시스템)
wait_for_food_loaded()

# 5. 배달 테이블 예약
table_zone = manager.get_zone_by_location(f'table{order.table_number}')
if not manager.reserve_zone(robot_id, table_zone):
    print("Table busy, try another")
    return

# 6. 픽업 퇴장
manager.leave_zone(robot_id, 'zone_pickup')

# 7. 테이블로 내비게이션
navigate_to_location(robot_id, order.table_number)

# 8. 테이블 구역 점유
manager.occupy_zone(robot_id, table_zone)

# 9. 고객 확인
wait_for_delivery_complete()

# 10. 테이블 퇴장
manager.leave_zone(robot_id, table_zone)

# 11. 주차 지점 복귀
parking_zone = manager.get_zone_by_location(f'{robot_id}_spot')
manager.reserve_zone(robot_id, parking_zone)
navigate_to_parking_spot(robot_id)
manager.occupy_zone(robot_id, parking_zone)
```

### 다중 로봇 배달 조율

```python
manager = ZoneManager()

# 배달 가능 여부 확인
table_zone = manager.get_zone_by_location('table1')
pickup_zone = manager.get_zone_by_location('pickup_spot')

if manager.is_zone_available(pickup_zone):
    robot = select_available_robot()

    # 확정 전 두 구역 모두 예약
    if (manager.reserve_zone(robot, pickup_zone) and
        manager.reserve_zone(robot, table_zone)):

        # 배달 수행
        complete_delivery(robot, 'table1')

        # 정리
        manager.leave_zone(robot, table_zone)
        manager.leave_zone(robot, pickup_zone)
    else:
        print("Zones not available, try later")
else:
    print("Pickup busy")
```

### 경로 검증

```python
# 로봇 경로 계획
path_zones = ['zone_parking1', 'zone_point1', 'zone_pickup']

# 충돌 확인
conflicts = manager.check_path_conflicts('pinky1', path_zones)

if conflicts:
    print(f"Path blocked by: {conflicts}")
    # 경로 재계획 또는 충돌 해소 대기
else:
    # 경로 구역 예약
    for zone_id in path_zones:
        manager.reserve_zone('pinky1', zone_id)

    # 내비게이션 수행
    for zone_id in path_zones:
        navigate_to_zone(zone_id)
        manager.occupy_zone('pinky1', zone_id)
        # ... 내비게이션
        manager.leave_zone('pinky1', zone_id)
```

## 구역 설정

구역은 `fms/config/fms_config.yaml`에 정의됩니다:

```yaml
zones:
  - id: "zone_pickup"
    center_x: 0.47
    center_y: 0.63
    radius: 0.10
    reservation_timeout: 30.0  # 선택 사항, 기본값 30초

  - id: "zone_table1"
    center_x: 1.785
    center_y: 0.35
    radius: 0.10
```

**매개변수:**
- `id`: 고유 구역 식별자
- `center_x`, `center_y`: 구역 중심 (미터)
- `radius`: 구역 반경 (미터) - 충돌 여유
- `reservation_timeout`: 선택적 커스텀 타임아웃 (초)

## 예약 타임아웃 메커니즘

### 작동 방식

1. 시간 T에 구역이 예약됨
2. 타임아웃이 T + 30초로 설정됨
3. 로봇이 30초 이내에 구역을 점유하지 않으면 예약 만료
4. `cleanup_expired_reservations()`를 호출하여 만료된 예약 제거
5. 이후 다른 로봇이 만료된 구역을 예약할 수 있음

### 타임아웃이 중요한 이유

**시나리오:**
- 로봇이 픽업으로 이동 중 비정상 종료
- 네트워크 장애로 로봇이 점유 상태 업데이트 불가
- 로봇이 장애물에 걸려 진행 불가
- 주문 취소 후 예약이 해제되지 않음

**해결:**
- 타임아웃이 구역의 영구 잠금을 방지
- 주기적 정리가 교착 상태의 구역 해제
- 구역별로 타임아웃 조정 가능 (일부 구역은 더 긴 타임아웃 필요)

### 권장 정리 주기

```python
# 메인 FMS 루프에서
cleanup_timer = 0
cleanup_interval = 5.0  # 초

def main_loop():
    global cleanup_timer

    while running:
        # ... 로봇 주문 및 이동 처리

        cleanup_timer += loop_delta_time
        if cleanup_timer >= cleanup_interval:
            count = manager.cleanup_expired_reservations()
            cleanup_timer = 0
```

## 테스트

종합 테스트 스위트 실행:

```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m pytest fms/tests/test_zone_manager_reservation.py -v
```

**테스트 범위:**
- 구역 생성 및 상태 전이
- 예약 및 점유
- 만료 감지
- 다중 로봇 조율
- 경로 충돌 감지
- 전체 배달 흐름 시나리오

## FMS 통합

ZoneManager는 메인 FMS 노드에 통합되어야 합니다:

```python
# fms_node.py 또는 fleet_controller.py 내

class FMSNode:
    def __init__(self):
        # fms_config.yaml에서 구역 설정 로드
        config = load_config('fms/config/fms_config.yaml')
        self.zone_manager = ZoneManager(config)

        # 정리 타이머 생성
        self.create_timer(5.0, self.cleanup_zones)

    def cleanup_zones(self):
        """만료된 예약의 주기적 정리"""
        cleaned = self.zone_manager.cleanup_expired_reservations()
        if cleaned > 0:
            self.get_logger().info(f"Cleaned {cleaned} expired zones")

    def assign_delivery(self, order):
        """구역 조율을 적용한 로봇 배달 할당"""
        robot = self.select_robot(order)

        # 구역 ID 조회
        pickup_zone = self.zone_manager.get_zone_by_location('pickup_spot')
        table_zone = self.zone_manager.get_zone_by_location(f'table{order.table}')

        # 구역 예약 시도
        if not self.zone_manager.reserve_zone(robot.id, pickup_zone):
            return False  # 픽업 사용 중

        if not self.zone_manager.reserve_zone(robot.id, table_zone):
            self.zone_manager.release_reservation(robot.id, pickup_zone)
            return False  # 테이블 사용 중

        # 구역 정보를 포함한 작업 생성
        task = Task(
            robot_id=robot.id,
            order_id=order.id,
            pickup_zone=pickup_zone,
            delivery_zone=table_zone
        )

        self.task_manager.assign_task(task)
        return True
```

## 문제 해결

### 구역 사용 불가

**문제:** 구역이 비어 보이는데 `reserve_zone()`이 False를 반환

**원인:**
1. 다른 로봇이 실제로 구역을 점유 중
2. 다른 로봇이 구역을 예약 중 (`get_zone_status()`로 확인)
3. 로봇이 오프라인이지만 구역이 정리되지 않음 (`clear_robot()` 호출)

**해결:**
```python
status = manager.get_zone_status('zone_pickup')
print(f"Occupied: {status['occupied_by']}, Reserved: {status['reserved_by']}")

# 오프라인 로봇에 의해 점유된 경우:
manager.clear_robot('pinky1')
```

### 구역이 정리되지 않음

**문제:** 구역이 무기한으로 점유/예약 상태 유지

**원인:**
1. `cleanup_expired_reservations()`가 호출되지 않음
2. 로봇이 `leave_zone()`을 제대로 호출하지 않음
3. 로봇이 정리 없이 비정상 종료

**해결:**
1. 정리가 주기적으로 호출되는지 확인
2. 항상 정리를 호출하도록 오류 처리 추가:
   ```python
   try:
       deliver_package(robot)
   finally:
       manager.clear_robot(robot.id)
   ```

### 다중 로봇 교착 상태

**문제:** 순환 경로에서 로봇끼리 서로 차단

**원인:**
1. 구역을 통한 비효율적인 경로 계획
2. 여러 로봇이 같은 구역을 다른 순서로 예약
3. 타임아웃 없음 또는 타임아웃이 너무 김

**해결:**
1. 경로 확정 전에 `check_path_conflicts()` 사용
2. 전체 경로를 한 번에 예약 (전부 아니면 전무)
3. 혼잡 구역에 더 짧은 타임아웃 사용:
   ```yaml
   zones:
     - id: "zone_point1"
       reservation_timeout: 10.0  # 더 짧은 타임아웃
   ```

## 성능 고려사항

- 구역 조회는 zone_id로 O(1)
- 경로 충돌 확인은 O(경로 길이)
- 정리는 O(구역 수)
- 메모리 사용량: 구역당 ~1KB + 로봇 추적

**20개 구역, 3대 로봇 기준:** ~50KB 메모리 사용 (무시 가능)

## 향후 개선 사항

1. **동적 타임아웃:** 구역 유형에 따라 타임아웃 조정
2. **우선순위 구역:** 일부 구역에 우선 예약 부여
3. **구역 그룹:** 인접 구역을 단일 단위로 처리
4. **마감 시간 추적:** 작업 마감 시간에 맞춘 구역 예약
5. **시각화:** 구역 점유 상태를 보여주는 RViz 플러그인
