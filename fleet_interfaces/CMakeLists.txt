cmake_minimum_required(VERSION 3.8)
project(fleet_interfaces)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

# Generate interfaces
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/OrderRequest.msg"
  "msg/CookingOrder.msg"
  "msg/LoadingComplete.msg"
  "msg/RobotStatus.msg"
  "msg/FleetStatus.msg"
  "msg/DeliveryComplete.msg"
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

ament_package()
