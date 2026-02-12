builtin_interfaces/Time stamp

bool valid
int32 id

# base_link 기준 거리/각도 (권장)
# yaw_rad: “마커가 왼쪽/오른쪽에 있다”
float32 distance_m
float32 yaw_rad

# 카메라 좌표계 기준 위치, 디버그/고급제어용(선택적으로 사용)
float32 tx_m
float32 tz_m

# -------------------------
# [NEW] 정밀 정렬용 관측값
# -------------------------

# 화면 중심 대비 마커 중심 X 오차 (-1.0 ~ +1.0)
# center_x_err: “마커가 화면 중앙에서 얼마나 벗어났는가”
# -1.0 (왼쪽) ~ 0.0 (중앙) ~ +1.0 (오른쪽)
float32 center_x_err

# 마커 법선 기준 yaw 오차 (rad)
# pose_yaw_err: “마커가 나를 정면으로 보고 있는가”
float32 pose_yaw_err

# 품질(마커 픽셀 크기/신뢰도/재투영오차 등을 넣을 예정)
float32 quality
