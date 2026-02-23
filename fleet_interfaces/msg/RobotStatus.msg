# Serving robot status
string robot_id         # pinky1, pinky2, pinky3
string status           # IDLE, MOVING_TO_PICKUP, LOADED, MOVING_TO_TABLE, DELIVERING, RETURNING, ERROR
geometry_msgs/Pose current_pose
float32 battery_voltage
bool battery_present
builtin_interfaces/Time timestamp
