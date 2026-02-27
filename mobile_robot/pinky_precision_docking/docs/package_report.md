# Pinky Precision Docking Package 리포트

**패키지명**: `pinky_precision_docking`  
**버전**: 0.0.0  
**작성일**: 2024년  
**분석 범위**: 전체 소스 코드

---

## 1. 패키지 개요

### 1.1 패키지 정보

- **이름**: `pinky_precision_docking`
- **타입**: ROS2 Python 패키지 (ament_python)
- **목적**: 시각 마커(ArUco/AprilTag) 기반 정밀 도킹/파킹 시스템
- **메인테이너**: addinedu (guehojung88@gmail.com)
- **라이선스**: TODO (미정)

### 1.2 의존성

**ROS2 의존성:**
- `rclpy`: ROS2 Python 클라이언트 라이브러리
- `geometry_msgs`: Twist 메시지 (속도 명령)
- `std_msgs`: 표준 메시지 타입
- `rclpy_action`: ROS2 Action 서버/클라이언트
- `pinky_precision_interfaces`: 커스텀 인터페이스 (Marker2D, Dock.action)

**추가 의존성:**
- `setuptools`: 패키지 빌드
- `numpy`: 수치 계산 (odom_helper.py에서 사용)

### 1.3 패키지 구조

```
pinky_precision_docking/
├── package.xml                    # ROS2 패키지 메타데이터
├── setup.py                        # Python 패키지 설정
├── setup.cfg                       # 빌드 설정
├── resource/
│   └── pinky_precision_docking    # 리소스 마커 파일
├── pinky_precision_docking/        # 메인 패키지 디렉토리
│   ├── __init__.py                # 패키지 초기화
│   ├── docking_action_server.py   # 메인 Action Server (790 lines)
│   ├── fsm.py                     # FSM 상태 정의 (32 lines)
│   ├── pid.py                     # PID 제어기 (50 lines)
│   ├── utils/                     # 유틸리티 모듈
│   │   ├── geometry.py            # 2D 기하학 유틸 (206 lines)
│   │   └── odom_helper.py         # Odometry 헬퍼 (66 lines)
│   └── docking_action_server_BAK*.py  # 백업 파일들 (5개)
├── test/                          # 테스트 파일
│   ├── test_copyright.py
│   ├── test_flake8.py
│   └── test_pep257.py
└── docs/                          # 문서
    └── presentation.md             # 발표 자료
```

**통계:**
- 총 Python 파일: 17개
- 총 코드 라인 수: 약 5,139 lines
- 메인 소스 코드: 약 1,344 lines (백업 제외)

---

## 2. 핵심 컴포넌트 분석

### 2.1 PrecisionDockingServer (docking_action_server.py)

**역할**: ROS2 Action Server로 도킹 FSM을 실행하는 메인 노드

**주요 기능:**

1. **ROS2 통신**
   - **구독**: `/precision/marker2d` (Marker2D) - 마커 정보 수신
   - **발행**: `/cmd_vel_raw` (Twist) - 속도 명령 전송
   - **액션 서버**: `/precision/dock` (Dock.action) - 도킹 요청 처리

2. **Finite State Machine (FSM)**
   - 10개 상태 관리 (향후 11개로 확장 예정)
   - 상태: IDLE, SEARCH, CENTERING, FACE_ALIGN, VERIFY_POSE, APPROACH, FINAL_ALIGN, DOCKED, FAILSAFE
   - 향후: FACE_ALIGN_TRANSLATE, FACE_ALIGN_ROTATE로 분리 예정

3. **PID 제어기**
   - 5개의 독립 PID 제어기
     - `pid_yaw`: 일반 각도 제어
     - `pid_dist`: 접근 거리 제어
     - `pid_dist_final`: 최종 거리 제어
     - `pid_center`: 화면 중앙 제어
     - `pid_pose`: 법선 각도 제어

4. **멀티스레딩**
   - `ReentrantCallbackGroup` 사용
   - `MultiThreadedExecutor`로 동시 콜백 처리

**주요 메서드:**

| 메서드 | 역할 |
|--------|------|
| `__init__()` | 노드 초기화, Pub/Sub/Action 설정, PID 제어기 초기화 |
| `marker_cb()` | 마커 정보 콜백 (멀티스레드 환경) |
| `execute_cb()` | Action 실행 콜백, FSM 메인 루프 |
| `goal_cb()` | Goal 요청 검증 |
| `cancel_cb()` | 취소 요청 처리 |
| `publish_cmd()` | 속도 명령 발행 |
| `reset_controllers()` | 모든 PID 제어기 리셋 |
| `hard_stop()` | 안전 정지 (반복 발행) |

**코드 통계:**
- 총 라인 수: 790 lines
- 클래스: 1개 (PrecisionDockingServer)
- 함수: 3개 (normalize_angle, yaw_from_quat, main)

### 2.2 DockState (fsm.py)

**역할**: FSM 상태를 정의하는 Enum 클래스

**상태 목록:**

```python
class DockState(Enum):
    # 기본 상태
    IDLE = auto()                    # 대기
    SEARCH = auto()                  # 마커 탐색
    
    # 정렬 단계 (세분화)
    CENTERING = auto()               # 화면 중앙 맞추기
    FACE_ALIGN_TRANSLATE = auto()   # [향후] 위치 이동으로 법선 각도 줄이기
    FACE_ALIGN_ROTATE = auto()      # [향후] 회전만으로 법선 미세 정렬
    VERIFY_POSE = auto()             # 정렬 안정성 검증
    
    # 접근 / 완료
    APPROACH = auto()                # 거리 접근
    FINAL_ALIGN = auto()             # 최종 미세 정렬
    DOCKED = auto()                  # 도킹 완료
    
    # 예외
    FAILSAFE = auto()                # 마커 유실 / 타임아웃
```

**코드 통계:**
- 총 라인 수: 32 lines
- Enum 항목: 10개 (향후 11개)

### 2.3 PID 제어기 (pid.py)

**역할**: PID 제어 알고리즘 구현

**주요 클래스:**

1. **PIDGains** (dataclass)
   - `kp`: 비례 게인
   - `ki`: 적분 게인
   - `kd`: 미분 게인
   - `i_limit`: 적분항 제한 (anti-windup)

2. **PID**
   - `__init__(gains)`: PID 게인 설정
   - `reset()`: 내부 상태 리셋
   - `step(err, dt, saturated)`: PID 계산
     - `err`: 오차
     - `dt`: 시간 간격
     - `saturated`: 출력 포화 여부 (anti-windup)

**특징:**
- Anti-windup 지원 (적분항 제한)
- 포화 시 적분 누적 억제
- 미분항 계산 (이전 오차 기반)

**코드 통계:**
- 총 라인 수: 50 lines
- 클래스: 2개 (PIDGains, PID)
- 함수: 1개 (clamp)

### 2.4 Geometry 유틸리티 (utils/geometry.py)

**역할**: 2D 평면 기하학 계산 유틸리티

**주요 기능:**

1. **각도 처리**
   - `wrap_to_pi()`: 각도를 [-π, +π] 범위로 정규화
   - `shortest_angular_distance()`: 최단 각도 차이 계산
   - `yaw_from_quaternion()`: Quaternion → yaw 변환

2. **2D 변환**
   - `Pose2D`: 2D 포즈 (x, y, yaw)
   - `rot2d()`: 2D 회전 행렬
   - `transform_point_2d()`: 로컬 → 월드 변환
   - `inverse_transform_point_2d()`: 월드 → 로컬 변환

3. **거리/방향 계산**
   - `distance_2d()`: 2D 거리 계산
   - `heading_to_target()`: 목표점 방향 계산

4. **Yaw 융합 (Complementary Filter)**
   - `YawFusionState`: 융합 상태 관리
   - `unwrap_angle()`: 각도 연속성 유지
   - `fuse_yaw_complementary()`: odom + IMU yaw 융합

5. **Standoff 벡터**
   - `standoff_vector_from_normal()`: 마커 법선 방향 벡터 계산

**코드 통계:**
- 총 라인 수: 206 lines
- 클래스: 2개 (Pose2D, YawFusionState)
- 함수: 10개

### 2.5 Odometry 헬퍼 (utils/odom_helper.py)

**역할**: Odometry 및 IMU 기반 위치 추정 헬퍼

**주요 클래스:**

**OdomState**
- `x, y`: 위치 (m)
- `yaw_odom`: Odometry yaw
- `yaw_imu`: IMU yaw (선택적)
- `update_from_odom()`: Odometry 업데이트
- `update_from_imu()`: IMU 업데이트
- `get_fused_yaw()`: 융합 yaw 계산 (alpha 가중치)
- `position()`: 위치 배열 반환
- `distance_to()`: 목표점까지 거리
- `heading_error_to()`: 목표점 방향 오차

**코드 통계:**
- 총 라인 수: 66 lines
- 클래스: 1개 (OdomState)
- 메서드: 6개

---

## 3. FSM 상태 전이 로직

### 3.1 현재 구현된 상태

| 상태 | 역할 | 제어 변수 | 전이 조건 |
|------|------|----------|----------|
| **IDLE** | 대기 | - | Goal 수신 → SEARCH |
| **SEARCH** | 마커 탐색 | - | 마커 발견 → CENTERING |
| **CENTERING** | 화면 중앙 정렬 | `center_x_err` | `abs(cx) ≤ 0.08` → FACE_ALIGN |
| **FACE_ALIGN** | 법선 정렬 | `pose_yaw_err`, `center_x_err` | `abs(pose_err) ≤ 0.10` → VERIFY_POSE |
| **VERIFY_POSE** | 안정성 검증 | `pose_yaw_err`, `center_x_err` | 0.25초 유지 → APPROACH |
| **APPROACH** | 거리 접근 | `distance_m`, `yaw_rad` | `distance < 0.10m` → FINAL_ALIGN |
| **FINAL_ALIGN** | 최종 정렬 | `distance_m`, `yaw_rad` | 완료 조건 → DOCKED |
| **DOCKED** | 도킹 완료 | - | Action Success |
| **FAILSAFE** | 안전 모드 | - | Action Abort |

### 3.2 향후 구현 예정 상태

- **FACE_ALIGN_TRANSLATE**: 위치 이동으로 큰 `pose_yaw_err` 보정
- **FACE_ALIGN_ROTATE**: 회전만으로 미세 정렬

### 3.3 주요 제어 파라미터

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `center_exit_th` | 0.08 | CENTERING 종료 임계값 |
| `center_enter_th` | 0.15 | CENTERING 재진입 임계값 |
| `pose_exit_th` | 0.10 rad | FACE_ALIGN 종료 임계값 |
| `pose_enter_th` | 0.20 rad | FACE_ALIGN 재진입 임계값 |
| `verify_hold_sec` | 0.25 s | VERIFY_POSE 유지 시간 |
| `align_loss_grace` | 0.30 s | 마커 유실 Grace Period |
| `centering_timeout_sec` | 10.0 s | CENTERING 타임아웃 |
| `yaw_align_enter` | 0.10 rad | ALIGN 진입 임계값 |
| `yaw_align_exit` | 0.035 rad | ALIGN 종료 임계값 |

---

## 4. 코드 품질 분석

### 4.1 강점

1. **모듈화**
   - FSM, PID, Geometry, Odometry가 명확히 분리
   - 각 모듈의 책임이 명확함

2. **멀티스레딩 지원**
   - `ReentrantCallbackGroup` 사용
   - 동시 콜백 처리 가능

3. **안전성**
   - Grace Period로 마커 일시적 유실 처리
   - 타임아웃 보호
   - `hard_stop()` 안전 정지 메커니즘

4. **로깅**
   - 상세한 모니터링 로그
   - 상태 전이 추적 가능

5. **확장성**
   - 향후 FACE_ALIGN 분리 계획 반영
   - 유틸리티 모듈로 기능 확장 용이

### 4.2 개선 필요 사항

1. **백업 파일 관리**
   - `docking_action_server_BAK*.py` 파일 5개 존재
   - 버전 관리 시스템(Git) 사용 권장
   - 백업 파일 정리 필요

2. **문서화**
   - `package.xml`의 description이 "TODO"
   - 라이선스 미정
   - 일부 함수에 docstring 부족

3. **테스트**
   - 단위 테스트 부재
   - 통합 테스트 필요

4. **에러 처리**
   - 일부 예외 상황 처리 부족
   - 타임아웃 처리 개선 여지

5. **파라미터 관리**
   - 하드코딩된 파라미터 다수
   - ROS2 파라미터 시스템 활용 권장

### 4.3 코드 메트릭

| 메트릭 | 값 |
|--------|-----|
| 총 파일 수 | 17개 |
| 메인 소스 코드 | ~1,344 lines |
| 최대 파일 크기 | 790 lines (docking_action_server.py) |
| 평균 파일 크기 | ~79 lines |
| 클래스 수 | 6개 |
| 함수 수 | ~20개 |

---

## 5. 아키텍처 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│         Pinky Precision Docking System                    │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ Marker2D     │────────▶│ Action       │             │
│  │ Subscriber   │         │ Server       │             │
│  └──────────────┘         └──────────────┘             │
│         │                        │                       │
│         │                        │                       │
│         ▼                        ▼                       │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ FSM State    │────────▶│ PID          │             │
│  │ Machine      │         │ Controllers  │             │
│  │ (fsm.py)     │         │ (pid.py)     │             │
│  └──────────────┘         └──────────────┘             │
│         │                        │                       │
│         │                        │                       │
│         └──────────┬─────────────┘                       │
│                    ▼                                     │
│         ┌──────────────┐                                 │
│         │ Twist        │                                 │
│         │ Publisher    │                                 │
│         └──────────────┘                                 │
│                                                          │
│  ┌──────────────┐         ┌──────────────┐             │
│  │ Geometry     │         │ Odom         │             │
│  │ Utils        │         │ Helper       │             │
│  │ (utils/)     │         │ (utils/)     │             │
│  └──────────────┘         └──────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 6. 주요 기능 상세

### 6.1 마커 기반 정렬

**CENTERING 단계:**
- `center_x_err`를 PID로 제어
- 회전만으로 화면 중앙 맞추기
- 회전 방향 자동 감지 및 보정
- 적응형 속도 제한

**FACE_ALIGN 단계:**
- `pose_yaw_err`와 `center_x_err` 하이브리드 제어
- 우선 보정 모드 (center_x_err 우선)
- CRITICAL 모드 (center_x_err만 제어)
- 드리프트 방지 메커니즘

### 6.2 안전 메커니즘

1. **Grace Period**
   - 마커 일시적 유실 허용 (0.3초)
   - 즉시 상태 전이 방지

2. **타임아웃 보호**
   - CENTERING 타임아웃 (10초)
   - 전체 타임아웃 (Goal에서 설정)

3. **안전 정지**
   - `hard_stop()`: 반복 정지 명령
   - 취소/타임아웃 시 즉시 정지

### 6.3 제어 알고리즘

**PID 제어기 구성:**

| 제어기 | 변수 | Gains (kp, ki, kd) | 용도 |
|--------|------|-------------------|------|
| `pid_yaw` | `yaw_rad` | (1.6, 0.0, 0.10) | 일반 각도 제어 |
| `pid_dist` | `distance_m` | (0.8, 0.0, 0.0) | 접근 거리 제어 |
| `pid_dist_final` | `distance_m` | (0.6, 0.0, 0.0) | 최종 거리 제어 |
| `pid_center` | `center_x_err` | (1.2, 0.0, 0.0) | 화면 중앙 제어 |
| `pid_pose` | `pose_yaw_err` | (1.2, 0.0, 0.08) | 법선 각도 제어 |

**특징:**
- Anti-windup 지원
- 포화 감지 및 적분 누적 억제
- 미분항으로 안정성 향상

---

## 7. 향후 개발 계획

### 7.1 단기 계획

1. **FACE_ALIGN 분리 구현**
   - `FACE_ALIGN_TRANSLATE` 상태 구현
   - `FACE_ALIGN_ROTATE` 상태 구현
   - 두 상태 간 전이 로직

2. **코드 정리**
   - 백업 파일 제거
   - Git 버전 관리 적용

3. **파라미터 관리**
   - ROS2 파라미터 시스템 도입
   - YAML 설정 파일 지원

### 7.2 중기 계획

1. **테스트**
   - 단위 테스트 작성
   - 통합 테스트 구현

2. **문서화**
   - API 문서 작성
   - 사용자 가이드 작성

3. **성능 개선**
   - 동적 파라미터 조정
   - 최적화

### 7.3 장기 계획

1. **기능 확장**
   - 다중 마커 지원
   - 동적 장애물 회피

2. **학습 기반 제어**
   - 머신러닝 기반 파라미터 튜닝
   - 적응형 제어

---

## 8. 결론

### 8.1 요약

**Pinky Precision Docking** 패키지는 ROS2 기반의 정밀 도킹 시스템으로, 다음과 같은 특징을 가집니다:

- ✅ **모듈화된 구조**: FSM, PID, Geometry, Odometry가 명확히 분리
- ✅ **안전 메커니즘**: Grace Period, 타임아웃, 안전 정지
- ✅ **정밀 제어**: 5개의 독립 PID 제어기
- ✅ **멀티스레딩 지원**: 동시 콜백 처리
- ✅ **확장 가능**: 향후 기능 추가 용이

### 8.2 개선 권장 사항

1. **즉시 개선**
   - 백업 파일 정리
   - `package.xml` description/라이선스 업데이트

2. **단기 개선**
   - ROS2 파라미터 시스템 도입
   - 단위 테스트 작성

3. **중장기 개선**
   - FACE_ALIGN 분리 구현
   - 문서화 강화
   - 성능 최적화

### 8.3 평가

**전체 평가: ⭐⭐⭐⭐ (4/5)**

- **구조**: ⭐⭐⭐⭐⭐ (5/5) - 명확한 모듈화
- **기능**: ⭐⭐⭐⭐ (4/5) - 핵심 기능 구현 완료
- **코드 품질**: ⭐⭐⭐⭐ (4/5) - 전반적으로 양호
- **문서화**: ⭐⭐⭐ (3/5) - 개선 필요
- **테스트**: ⭐⭐ (2/5) - 테스트 부재

---

**작성자**: Package Analysis System  
**버전**: 1.0  
**최종 업데이트**: 2024년

