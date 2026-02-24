cmake_minimum_required(VERSION 3.5)
project(mobile_robot)

find_package(ament_cmake REQUIRED)

# Install launch files
install(DIRECTORY
  launch
  params
  maps
  config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
