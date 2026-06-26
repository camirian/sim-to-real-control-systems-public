# Set the minimum required version of CMake
cmake_minimum_required(VERSION 3.8)

# Name the project (must match the package.xml name)
project(cpp_pubsub)

# Find necessary ROS 2 packages and C++ libraries
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)

# --- Add the Publisher Executable ---
# This tells CMake to create an executable named "talker"
# from the source file "publisher_member_function.cpp"
add_executable(talker src/publisher_member_function.cpp)

# This links the "talker" executable against the required libraries
ament_target_dependencies(talker rclcpp std_msgs)

# --- Add the Subscriber Executable ---
# This tells CMake to create an executable named "listener"
# from the source file "subscriber_member_function.cpp"
add_executable(listener src/subscriber_member_function.cpp)

# This links the "listener" executable against the required libraries
ament_target_dependencies(listener rclcpp std_msgs)

# --- Install Section ---
# This tells colcon where to install the final executables so that
# the "ros2 run" command can find them.
install(TARGETS
  talker
  listener
  DESTINATION lib/${PROJECT_NAME}
)

# This is a required function call for ament packages
ament_package()