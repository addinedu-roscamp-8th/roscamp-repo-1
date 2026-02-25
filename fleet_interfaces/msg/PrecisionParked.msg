# Precision parking complete notification from Precision Control Team to FMS
# Sent when robot is precisely positioned at pickup_spot for robot arm loading

string robot_id         # Robot that completed parking (pinky1/2/3)
string order_id         # Associated order
bool success            # True if parking succeeded
geometry_msgs/Pose final_pose    # Final precise pose
string message          # Error message if success=false
builtin_interfaces/Time completed_at
