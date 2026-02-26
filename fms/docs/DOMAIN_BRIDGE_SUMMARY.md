# Domain Bridge Configuration Review - Executive Summary

**작성일**: 2026-02-25
**검토 대상**: `/fms/config/domain_bridge.yaml`
**상태**: 5가지 주요 문제점 확인, 개선안 제시됨

---

## 주요 발견사항 (Top 5 Issues)

### 1. 토픽 네이밍 충돌 (CRITICAL)

**현재 상태**:
- 모든 로봇이 동일한 토픽명 사용
- 예: `/amcl_pose`, `/odom`, `/battery/voltage`
- pinky1과 pinky3 데이터가 Main PC에서 섞임

**영향**:
- 로봇 위치 추정 오류
- 배터리 상태 혼동
- Task allocation 실패

**해결책**: Namespace 기반 격리
```
/pinky1/amcl_pose
/pinky3/amcl_pose
```

---

### 2. TF (Transform) 프레임 브릿징 누락 (CRITICAL)

**현재 상태**:
- `/tf`, `/tf_static` 토픽이 브릿징되지 않음
- 로봇의 좌표계 정보가 Main PC에 전달 불가

**영향**:
- Nav2 경로 계획 실패
- 좌표 변환 오류
- AMCL 로컬라이제이션 불안정

**해결책**: TF 브릿징 추가
```yaml
/tf:
  type: tf2_msgs/msg/TFMessage
/tf_static:
  type: tf2_msgs/msg/TFMessage
```

---

### 3. Action 피드백 토픽 누락 (HIGH)

**현재 상태**:
- `/navigate_to_pose/_action/feedback` 미포함
- `/navigate_to_pose/_action/status` 미포함
- FMS가 네비게이션 진행 상황 파악 불가

**영향**:
- 로봇 상태 업데이트 지연
- 네비게이션 타임아웃 위험
- 로봇 감시 능력 저하

**해결책**: Action 피드백 브릿징 추가

---

### 4. QoS 정책 미설정 (MEDIUM)

**현재 상태**:
- domain_bridge.yaml에 QoS 정책이 없음
- 모든 토픽이 기본 설정 사용
- 신뢰도와 효율성 불균형

**영향**:
- 중요 메시지 손실 가능 (위치, 배터리)
- 고주파 데이터 병목 현상
- 네트워크 부하 증가

**해결책**: 토픽별 QoS 정책 설정
```yaml
qos:
  reliability: "RELIABLE"    # 위치, 배터리 정보
  reliability: "BEST_EFFORT"  # LiDAR, 주행거리계
```

---

### 5. FMS Node 코드 불일치 (HIGH)

**현재 상태**:
```python
# fms_node.py line 273
self.create_subscription(Pose, '/pose', ...)
```
- domain_bridge.yaml의 토픽명과 불일치
- 토픽명이 `/pose`가 아니라 `/amcl_pose`, `/odom`

**영향**:
- 로봇 토픽 구독 실패
- Fleet controller 정보 부족
- 로봇 모니터링 불가

**해결책**: FMS Node 코드 업데이트
```python
self.create_subscription(PoseWithCovarianceStamped, '/pinky1/amcl_pose', ...)
self.create_subscription(Odometry, '/pinky1/odom', ...)
```

---

## 개선 사항 요약

| 항목 | 현재 | 개선안 | 영향 |
|------|------|--------|------|
| 토픽 격리 | X | Namespace 기반 | 데이터 혼동 해결 |
| TF 브릿징 | X | 추가 | Nav2 작동 보장 |
| QoS 설정 | X | 토픽별 설정 | 통신 안정성 향상 |
| Action 피드백 | 부분 | 완전 브릿징 | 상태 모니터링 개선 |
| FMS 코드 | 오래됨 | 업데이트 | 토픽 구독 성공 |

---

## 제공된 파일

### 1. DOMAIN_BRIDGE_REVIEW.md
- **내용**: 5가지 문제점 상세 분석
- **분량**: 600+ 줄
- **위치**: `/fms/docs/DOMAIN_BRIDGE_REVIEW.md`
- **포함**:
  - 각 문제의 원인과 영향
  - 여러 해결책 제시
  - 전체 개선된 domain_bridge.yaml

### 2. domain_bridge_improved.yaml
- **내용**: 모든 개선사항이 반영된 설정
- **위치**: `/fms/config/domain_bridge_improved.yaml`
- **특징**:
  - Namespace 기반 토픽 격리
  - TF 프레임 포함
  - 토픽별 QoS 정책
  - 상세한 주석

### 3. CODE_FIXES_FOR_DOMAIN_BRIDGE.md
- **내용**: FMS Node 코드 수정 방법
- **위치**: `/fms/docs/CODE_FIXES_FOR_DOMAIN_BRIDGE.md`
- **포함**:
  - Before/After 코드 비교
  - 7개 함수 수정 상세 설명
  - 모니터링 도구 스크립트
  - 적용 체크리스트

### 4. DOMAIN_BRIDGE_SUMMARY.md (이 파일)
- **내용**: 종합 요약 및 실행 가이드
- **위치**: `/fms/docs/DOMAIN_BRIDGE_SUMMARY.md`

---

## 실행 계획 (권장)

### Week 1: 분석 및 계획 (완료)
- [x] Domain bridge 설정 검토
- [x] FMS Node 코드 분석
- [x] 문제점 파악 및 우선순위 지정
- [x] 개선안 작성

### Week 2: Priority 1 (즉시 수행)

**Phase 2-1: 설정 준비** (2시간)
```bash
# 백업
cp fms/config/domain_bridge.yaml fms/config/domain_bridge.yaml.backup

# 개선 설정 검토
cat fms/config/domain_bridge_improved.yaml
```

**Phase 2-2: Domain Bridge 테스트** (2시간)
```bash
# 현재 domain bridge 시작
ros2 run domain_bridge domain_bridge fms/config/domain_bridge.yaml

# 토픽 확인
ros2 topic list
ros2 topic echo /amcl_pose
ros2 topic echo /odom
```

**Phase 2-3: 개선 설정 적용** (1시간)
```bash
# 기존 설정 교체
cp fms/config/domain_bridge_improved.yaml fms/config/domain_bridge.yaml

# Domain Bridge 재시작
ros2 run domain_bridge domain_bridge fms/config/domain_bridge.yaml

# 토픽 확인 (namespace 포함)
ros2 topic list | grep pinky
```

### Week 3: FMS Node 코드 수정 (Priority 1)

**Phase 3-1: 코드 분석** (2시간)
```bash
# FMS Node 현재 상태 확인
cat fms/fms/fms_node.py | grep -n "subscribe"
cat fms/fms/fms_node.py | grep -n "initialpose"
```

**Phase 3-2: 코드 수정** (3시간)
```bash
# /fms/docs/CODE_FIXES_FOR_DOMAIN_BRIDGE.md의 내용 참고하여 수정
# 1. Import 추가
# 2. _setup_robot_monitoring() 함수 업데이트
# 3. robot_amcl_pose_callback() 추가
# 4. __init__() 업데이트
# 5. _navigate_robot() 개선
```

**Phase 3-3: 테스트** (2시간)
```bash
# Python 문법 검사
pylint fms/fms/fms_node.py

# FMS Node 시작
ros2 launch fms_system fms_bringup.launch.xml

# 토픽 구독 확인
ros2 topic echo /pinky1/amcl_pose
ros2 topic echo /pinky3/amcl_pose
```

### Week 4-5: Priority 2 (1-2주 내)
- QoS 정책 검증
- Action 서비스 전체 테스트
- 에러 처리 강화

---

## 빠른 시작 (Quick Start)

### 옵션 A: 즉시 적용 (권장)

```bash
cd /home/gw/kitchmatics/roscamp-repo-1

# 1. 설정 백업
cp fms/config/domain_bridge.yaml fms/config/domain_bridge.yaml.old

# 2. 개선 설정 적용
cp fms/config/domain_bridge_improved.yaml fms/config/domain_bridge.yaml

# 3. Domain Bridge 시작
ros2 run domain_bridge domain_bridge fms/config/domain_bridge.yaml

# 4. 다른 터미널에서 FMS Node 시작
ros2 launch fms_system fms_bringup.launch.xml

# 5. 토픽 확인
ros2 topic list | grep pinky
```

### 옵션 B: 단계적 적용 (보수적)

**Step 1**: 현재 설정으로 테스트 (기준선 수집)
```bash
# 현재 domain_bridge.yaml로 FMS 실행
# 문제점 확인 및 로깅
```

**Step 2**: 개선 설정만 적용 (domain bridge 설정만)
```bash
cp fms/config/domain_bridge_improved.yaml fms/config/domain_bridge.yaml
# domain bridge만 재시작
# FMS Node는 현재 코드로 실행 (일시적으로 토픽 미구독)
```

**Step 3**: FMS Node 코드 수정 (CODE_FIXES_FOR_DOMAIN_BRIDGE.md 참고)
```bash
# FMS Node 코드 업데이트
# FMS 재시작 시 토픽 구독 성공 확인
```

---

## 문제 해결 (Troubleshooting)

### 증상: "토픽을 찾을 수 없음"
```
Error: Could not find topic '/pose'
```
**원인**: FMS Node가 구형 토픽명으로 구독 시도
**해결**: FMS Node 코드 업데이트 필요

### 증상: "AMCL 로컬라이제이션 실패"
```
Warning: No TF available
```
**원인**: `/tf` 토픽이 브릿징되지 않음
**해결**: domain_bridge.yaml에 `/tf` 추가

### 증상: "네비게이션 액션 타임아웃"
```
Error: Navigation goal request timeout
```
**원인**: 다른 DOMAIN_ID의 로봇에 action client 연결 실패
**해결**:
1. domain bridge 상태 확인: `ros2 topic list`
2. action 서비스 확인: `ros2 action list`
3. domain_bridge.yaml의 `/navigate_to_pose` 액션 설정 확인

---

## 성공 기준

### Phase 1: 설정 개선
- [ ] domain_bridge_improved.yaml 적용됨
- [ ] `ros2 topic list | grep pinky` 에서 로봇별 토픽 보임
- [ ] `/tf` 토픽 활성
- [ ] 모든 토픽 발행 주기 정상 (hz > 0)

### Phase 2: FMS Node 업데이트
- [ ] FMS Node 코드 컴파일 오류 없음
- [ ] FMS Node 시작 시 토픽 구독 성공 메시지 출력
- [ ] `ros2 topic echo /pinky1/amcl_pose` 데이터 정상 수신
- [ ] `ros2 topic echo /pinky3/amcl_pose` 데이터 정상 수신

### Phase 3: 통합 테스트
- [ ] FMS가 로봇 위치 정상 감지
- [ ] 배터리 상태 정상 수집
- [ ] 네비게이션 액션 정상 작동
- [ ] 여러 로봇 동시 제어 가능

---

## 참고 자료

### 문서
- **DOMAIN_BRIDGE_REVIEW.md**: 상세 분석 (600+ 줄)
- **CODE_FIXES_FOR_DOMAIN_BRIDGE.md**: 코드 수정 가이드
- **domain_bridge_improved.yaml**: 완전 개선 설정

### 관련 링크
- [ROS2 Domain Bridge](https://github.com/ros2/domain_bridge)
- [Nav2 네트워킹](https://navigation.ros.org/)
- [ROS2 QoS](https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html)

---

## FAQ

**Q. 기존 domain_bridge.yaml을 유지하면서 테스트할 수 있나?**
A. 네. domain_bridge_improved.yaml을 별도 파일로 두고 필요할 때 교체하세요.

**Q. 로봇 개수가 증가하면 어떻게 하나?**
A. domain_bridge_improved.yaml의 pinky1, pinky3 섹션을 복사하고 로봇명/도메인 ID 변경.

**Q. TF 네이밍 규칙은?**
A. 각 로봇이 발행하는 TF는 `base_link`, `odom` 등이지만, Main PC에서 여러 로봇 TF 구분이 필요하면 접두사 추가 (예: `pinky1_base_link`).

**Q. 설정 변경 후 로봇 재시작이 필요한가?**
A. Domain Bridge와 FMS Node 재시작만 필요. 각 로봇은 계속 실행 가능.

---

## 다음 단계

### 즉시 (이번 주)
- [ ] 이 문서 검토
- [ ] domain_bridge_improved.yaml 설정 검토
- [ ] 개발팀과 일정 논의

### 1주일 내
- [ ] 테스트 환경에서 개선 설정 적용
- [ ] 기본 기능 테스트

### 2주일 내
- [ ] FMS Node 코드 수정
- [ ] 통합 테스트

### 3주일 내
- [ ] 프로덕션 환경 배포
- [ ] 모니터링

---

**검토 완료**: 2026-02-25
**작성자**: ROS2 Navigation Specialist
**상태**: 준비 완료 (Implementation pending)
