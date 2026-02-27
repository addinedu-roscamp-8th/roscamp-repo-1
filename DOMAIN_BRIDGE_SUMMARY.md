# Domain Bridge 설정 분석 - 최종 요약

**날짜**: 2026-02-26
**분석 대상**: Kitchmatics FMS Domain Bridge 설정
**결론**: ✅ 현재 전략은 올바름. 누락 토픽 추가 필요.

---

## 핵심 답변

### Q: "namespace 사용을 최대한 지양하면서 브릿징하는 방법?"

### A: ✅ **현재 시스템이 이미 최적 방식을 사용하고 있습니다!**

```
┌────────────────────────────────┐
│  Robot (pinky1)                │
│  발행: /amcl_pose              │   ← Namespace 없음!
│        /odom                    │
│        /cmd_vel                 │
└───────────┬────────────────────┘
            │
            │ Domain Bridge
            │ (remap 기능 사용)
            │
            ▼
┌────────────────────────────────┐
│  Main PC (FMS)                 │
│  수신: /pinky1/amcl_pose       │   ← Namespace 추가됨
│        /pinky1/odom             │
│  발행: /pinky1/cmd_vel → /cmd_vel │
└────────────────────────────────┘
```

**이 방식의 장점**:
1. ✅ 로봇 측 코드는 namespace 불필요 (단순함 유지)
2. ✅ Main PC에서 여러 로봇 구분 가능 (충돌 없음)
3. ✅ Fleet management 가능
4. ✅ 요구사항 충족 ("namespace 최소화")

---

## 환경 정보

```
Main PC (FMS):    ROS_DOMAIN_ID=25
├── pinky1:       ROS_DOMAIN_ID=11  (IP: 192.168.1.7)
├── pinky2:       ROS_DOMAIN_ID=12  (IP: 192.168.1.6)
├── 로봇팔A:       ROS_DOMAIN_ID=20  (IP: 192.168.1.4)
└── 로봇팔B:       ROS_DOMAIN_ID=21  (IP: 192.168.1.10)
```

**주의**: 문서에 Domain 0이라고 나와있지만, **실제 시스템은 Domain 25 사용**

---

## 현재 상태 평가

| 구성요소 | 상태 | 설명 |
|---------|------|------|
| **Namespace 전략** | ✅ 우수 | 로봇 측 namespace 없음, 브릿지가 추가 |
| **모바일 로봇 토픽** | ⚠️ 부분 | amcl_pose, battery는 OK. odom, scan, cmd_vel 누락 |
| **로봇팔 토픽** | ❌ 없음 | 별도 브릿지 설정 필요 |
| **Action 브릿징** | ✅ 우수 | navigate_to_pose, follow_waypoints 지원 |
| **QoS 정책** | ⚠️ 기본값 | 명시적 설정 권장 |

---

## 필요한 수정사항

### 1. 모바일 로봇 토픽 추가 (HIGH)

**누락된 토픽**:
- `/odom` - 주행거리계 (CRITICAL)
- `/scan` - LiDAR 데이터 (HIGH)
- `/cmd_vel` - 속도 명령 (CRITICAL)
- `/goal_pose` - 목표 위치 (HIGH)

**해결책**: `domain_bridge_pinky1_improved.yaml` 사용

### 2. 로봇팔 브릿징 추가 (HIGH)

**필요한 토픽**:
- `/arm_a/cmd`, `/arm_a/status`
- `/arm_b/cmd`, `/arm_b/status`
- `/verify/cmd`, `/verify/status`
- `/fms/pickup_arrival`, `/cooking/order`, `/cooking/loading_complete`

**해결책**: `domain_bridge_arms.yaml` 생성 및 실행

### 3. QoS 정책 명시 (MEDIUM)

센서 데이터는 `best_effort`, 제어 명령은 `reliable` 사용 권장

---

## 제공된 파일

### 분석 문서
```
/home/gw/kitchmatics/roscamp-repo-1/
├── DOMAIN_BRIDGE_SUMMARY.md          ← 이 파일 (요약)
├── DOMAIN_BRIDGE_REPORT.md           ← 상세 분석 (한글, 권장)
├── DOMAIN_BRIDGE_ANALYSIS.md         ← 기술 분석 (영문)
└── DOMAIN_BRIDGE_QUICK_GUIDE.md      ← 빠른 실행 가이드
```

### 설정 파일
```
/home/gw/kitchmatics/roscamp-repo-1/fms/config/
├── domain_bridge_pinky1.yaml              [현재 사용 중]
├── domain_bridge_pinky1_improved.yaml     [개선 버전 - 권장]
├── domain_bridge_pinky2.yaml              [현재 사용 중]
├── domain_bridge_pinky2_improved.yaml     [개선 버전 - 권장]
├── domain_bridge_arms.yaml                [로봇팔용 - 신규 생성]
└── domain_bridge_complete.yaml            [통합 버전 - 참고용]
```

---

## 빠른 실행

### 현재 설정으로 테스트
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py
```

### 개선된 설정으로 테스트 (권장)
```bash
# Terminal 1: pinky1
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# Terminal 2: pinky2
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky2_improved.yaml

# Terminal 3: 로봇팔
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_arms.yaml
```

### 확인
```bash
# 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep -E "pinky|arm"

# 데이터 수신
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/odom --once
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status
```

---

## 토픽 매핑 요약

### pinky1 예시

| 로봇 측 토픽 | Main PC 토픽 | 방향 |
|------------|------------|------|
| /amcl_pose | /pinky1/amcl_pose | → |
| /odom | /pinky1/odom | → |
| /scan | /pinky1/scan | → |
| /battery/voltage | /pinky1/battery/voltage | → |
| /initialpose | /pinky1/initialpose | ← |
| /cmd_vel | /pinky1/cmd_vel | ← |
| /goal_pose | /pinky1/goal_pose | ← |

### 로봇팔 예시

| 토픽 | Domain | 방향 |
|------|--------|------|
| /arm_a/cmd | 20 | Main → armA |
| /arm_a/status | 20 | armA → Main |
| /arm_b/cmd | 21 | Main → armB |
| /arm_b/status | 21 | armB → Main |
| /verify/cmd | 21 | Main → armB |
| /verify/status | 21 | armB → Main |

---

## 문제점 및 해결방안

### 문제 1: TF (Transform) 충돌

**현상**: 여러 로봇이 동일한 frame 이름 사용 (`base_link`, `odom`, `map`)

**해결방안**:
- **권장**: TF를 브릿지하지 않음. Main PC는 `/amcl_pose`로 로봇 위치 파악.
- **대안**: 로봇 측에서 tf_prefix 사용 (예: `pinky1_base_link`)

**현재 개선 설정**: TF 브릿지 안 함 (충돌 방지)

### 문제 2: Coordinator 위치

**질문**: Coordinator node는 어느 domain에서 실행?

**답변**:
- **권장**: Main PC (Domain 25)에서 실행
- Domain bridge로 로봇팔 (Domain 20, 21)과 통신
- `/arm_a/cmd`, `/arm_b/cmd` 등은 namespace 없이 사용

**설정**: `domain_bridge_arms.yaml`에 포함됨

### 문제 3: 동일 토픽을 여러 domain에 전송

**사례**: `/fms/pickup_arrival`을 Domain 20과 21 모두에 전송 필요

**해결**:
```yaml
# Domain 20으로 전송
fms_pickup_arrival_20:
  topic: fms/pickup_arrival
  from_domain: 25
  to_domain: 20

# Domain 21로 전송
fms_pickup_arrival_21:
  topic: fms/pickup_arrival
  from_domain: 25
  to_domain: 21
```

**설정**: `domain_bridge_arms.yaml`에 구현됨

---

## 권장 작업 순서

### Phase 1: 단일 로봇 검증 (1-2시간)

```bash
# 1. pinky1 개선 설정 테스트
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# 2. 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep pinky1

# 3. 데이터 수신 확인
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/odom --once
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/scan --once

# 4. 명령 전송 테스트
ROS_DOMAIN_ID=25 ros2 topic pub /pinky1/cmd_vel \
  geometry_msgs/msg/Twist "{linear: {x: 0.1}}" --once
```

### Phase 2: 다중 로봇 검증 (1-2시간)

```bash
# 1. pinky1, pinky2 브릿지 동시 실행
# Terminal 1
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky1_improved.yaml

# Terminal 2
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_pinky2_improved.yaml

# 2. 충돌 없는지 확인
ROS_DOMAIN_ID=25 ros2 topic hz /pinky1/amcl_pose
ROS_DOMAIN_ID=25 ros2 topic hz /pinky2/amcl_pose

# 3. 데이터가 섞이지 않는지 확인
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose &
ROS_DOMAIN_ID=25 ros2 topic echo /pinky2/amcl_pose &
```

### Phase 3: 로봇팔 통합 (1-2시간)

```bash
# 1. 로봇팔 브릿지 실행
ROS_DOMAIN_ID=25 ros2 run domain_bridge domain_bridge \
  fms/config/domain_bridge_arms.yaml

# 2. 로봇팔 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list | grep -E "arm|verify"

# 3. 통신 테스트
ROS_DOMAIN_ID=25 ros2 topic echo /arm_a/status
ROS_DOMAIN_ID=25 ros2 topic pub /arm_a/cmd std_msgs/msg/String \
  "data: 'TEST_JOB|pick_ham'" --once

# 4. FMS ↔ Coordinator 통신 테스트
ROS_DOMAIN_ID=25 ros2 topic pub /fms/pickup_arrival \
  fleet_interfaces/msg/PickupArrival \
  "{robot_id: 'pinky1', location: 'station_a'}" --once
```

### Phase 4: Launch 파일 통합 (30분)

```python
# fms/launch/domain_bridges.launch.py 수정
# arms_bridge 노드 추가

Node(
    package='domain_bridge',
    executable='domain_bridge',
    name='arms_bridge',
    arguments=[arms_config],
    output='screen',
    respawn=True,
),
```

```bash
# 실행
ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py
```

---

## 체크리스트

### 설정 준비
- [ ] `domain_bridge_pinky1_improved.yaml` 검토 완료
- [ ] `domain_bridge_pinky2_improved.yaml` 검토 완료
- [ ] `domain_bridge_arms.yaml` 검토 완료
- [ ] Launch 파일 수정 완료

### 테스트
- [ ] pinky1 단독 테스트 성공
- [ ] pinky2 단독 테스트 성공
- [ ] pinky1 + pinky2 동시 테스트 (충돌 없음)
- [ ] 로봇팔 통신 테스트 성공
- [ ] FMS ↔ Coordinator 통신 테스트 성공
- [ ] Navigation action 테스트 성공

### 성능 확인
- [ ] 토픽 주기 정상 (ros2 topic hz)
- [ ] 지연 시간 측정
- [ ] 네트워크 대역폭 확인
- [ ] 장시간 안정성 테스트 (1시간+)

---

## 최종 권장사항

### ✅ 현재 전략 유지
- Namespace 전략은 올바름
- 로봇 측 코드 변경 불필요
- Domain bridge remap 기능 잘 활용 중

### ⚠️ 즉시 적용 필요
1. 누락 토픽 추가 (`odom`, `scan`, `cmd_vel`)
2. 로봇팔 브릿지 추가
3. QoS 정책 명시

### 📊 향후 개선 사항
1. 성능 모니터링 및 QoS 튜닝
2. TF 전략 재검토 (필요시)
3. 네트워크 보안 강화 (DDS Security)

---

## 문의 및 문제 해결

**상세 가이드**: `DOMAIN_BRIDGE_REPORT.md` 섹션 10
**빠른 시작**: `DOMAIN_BRIDGE_QUICK_GUIDE.md`
**기술 분석**: `DOMAIN_BRIDGE_ANALYSIS.md`

**테스트 명령**:
```bash
# 토픽 확인
ROS_DOMAIN_ID=25 ros2 topic list

# 데이터 수신
ROS_DOMAIN_ID=25 ros2 topic echo /pinky1/amcl_pose --once

# Domain bridge 프로세스 확인
ps aux | grep domain_bridge
```

---

**분석 완료**: 2026-02-26
**결론**: 현재 시스템은 올바른 방향. 누락 토픽 추가 및 로봇팔 브릿지 설정 필요.
**다음 단계**: 개선된 설정 파일 테스트 및 적용
