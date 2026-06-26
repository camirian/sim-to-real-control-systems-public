// Include the necessary ROS 2 C++ client library headers
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

// Include C++ standard libraries for time and string manipulation
#include <chrono>
#include <functional>
#include <memory>
#include <string>

// Use a 'using' declaration to make the code more readable
using namespace std::chrono_literals;

/* Create a class that inherits from rclcpp::Node. This is the C++ equivalent
of the Python class we created earlier. */
class MinimalPublisher : public rclcpp::Node
{
public:
  // Constructor for the class
  MinimalPublisher()
  : Node("minimal_publisher"), count_(0) // Initialize the node name and a counter
  {
    // Create a publisher of type std_msgs::msg::String on the "topic"
    // The queue size is 10.
    publisher_ = this->create_publisher<std_msgs::msg::String>("topic", 10);
    // Create a timer that calls the timer_callback function every 500ms
    timer_ = this->create_wall_timer(
      500ms, std::bind(&MinimalPublisher::timer_callback, this));
  }

private:
  void timer_callback()
  {
    // Create a String message
    auto message = std_msgs::msg::String();
    // Set the message data
    message.data = "Hello, world! " + std::to_string(count_++);
    // Log the message to the console
    RCLCPP_INFO(this->get_logger(), "Publishing: '%s'", message.data.c_str());
    // Publish the message
    publisher_->publish(message);
  }
  // Declare the timer, publisher, and counter member variables
  rclcpp::TimerBase::SharedPtr timer_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr publisher_;
  size_t count_;
};

// The main function, which is the entry point of the program
int main(int argc, char * argv[])
{
  // Initialize the ROS 2 C++ client library
  rclcpp::init(argc, argv);
  // "Spin" the node, which keeps it running and processing callbacks
  rclcpp::spin(std::make_shared<MinimalPublisher>());
  // Shut down the ROS 2 C++ client library
  rclcpp::shutdown();
  return 0;
}