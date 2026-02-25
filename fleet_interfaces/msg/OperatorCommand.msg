# Operator command message for robot error recovery
# Sent from Admin GUI to FMS when operator takes action on error robots

string robot_id                 # Target robot ID (pinky1, pinky2, pinky3)
string command                  # RETRY, RETURN_HOME, EMERGENCY_STOP, CLEAR_ERROR
string order_id                 # Associated order ID (may be empty for some commands)
string reason                   # Reason for command (operator note)
builtin_interfaces/Time timestamp # When command was issued
