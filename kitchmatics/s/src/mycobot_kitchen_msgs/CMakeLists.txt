cmake_minimum_required(VERSION 3.8)
project(mycobot_kitchen_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)

set(action_files
  "action/MoveToPose.action"
  "action/ExecuteRecipe.action"
  "action/RefillStock.action"
)

set(srv_files
  "srv/GetCorrectedPose.srv"
  "srv/SetSuction.srv"
  "srv/SetGripper.srv"
  "srv/ConsumeInventory.srv"
  "srv/GetInventory.srv"
  "srv/SetInventory.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${action_files}
  ${srv_files}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()