cmake_minimum_required(VERSION 3.8)
project(core_robotics_package)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Find ROS 2 dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclpy REQUIRED)
find_package(std_msgs REQUIRED)

# C++ Subscriber Executable
add_executable(simple_subscriber src/simple_subscriber.cpp)
ament_target_dependencies(simple_subscriber rclcpp std_msgs)
install(TARGETS
    simple_subscriber
  DESTINATION lib/${PROJECT_NAME}
)

# Python Publisher Executable
# Note: Add the shebang line '#!/usr/bin/env python3' to your python script
install(PROGRAMS
  core_robotics_package/simple_publisher.py
  DESTINATION lib/${PROJECT_NAME}
)

# Mark python script as executable
install(CODE "execute_process(COMMAND chmod +x ${CMAKE_INSTALL_PREFIX}/lib/${PROJECT_NAME}/simple_publisher.py)")


ament_package()