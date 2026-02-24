cmake_minimum_required(VERSION 3.8)
project(mycobot_sauce_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

set(action_files
  "action/MoveToPose.action"
  "action/HandleTray.action"
  "action/PourSauce.action"
)

set(srv_files
  "srv/SetGripper.srv"
  "srv/SendFrame.srv"
  "srv/GetCorrectedPose.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${action_files}
  ${srv_files}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
