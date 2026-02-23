# Loading complete signal from Robot Arm to Main Server/FMS
string order_id
bool success
string robot_id         # Which serving robot received the food (pinky1/2/3)
string message          # Error message if success=false
builtin_interfaces/Time completed_at
