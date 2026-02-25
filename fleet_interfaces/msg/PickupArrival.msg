# Pickup spot arrival notification from FMS to Precision Control Team
# Sent when robot reaches point13 (kitchen pickup area)

string robot_id         # Robot that arrived (pinky1/2/3)
string order_id         # Associated order
geometry_msgs/Pose current_pose  # Current robot pose at point13
builtin_interfaces/Time arrived_at
