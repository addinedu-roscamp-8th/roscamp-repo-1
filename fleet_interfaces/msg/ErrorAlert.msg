# Robot serving error alert message
# Used to notify operators about robot errors requiring human intervention

string robot_id                 # Robot ID (pinky1, pinky2, pinky3)
string error_type               # NAV_FAILED, COMM_LOST, LOW_BATTERY, TIMEOUT, OBSTACLE
string error_message            # Human-readable error description
geometry_msgs/Pose current_pose # Robot's current position when error occurred
float32 battery_voltage         # Battery voltage at time of error
builtin_interfaces/Time timestamp # When error occurred
