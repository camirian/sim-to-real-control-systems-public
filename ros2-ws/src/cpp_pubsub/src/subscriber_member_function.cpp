// Include the necessary ROS 2 C++ client library headers
#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"

// Include C++ standard libraries for memory management and binding
#include <memory>
#include <functional>

// Use a 'using' declaration for placeholder arguments
using std::placeholders::_1;

/* Create a class that inherits from rclcpp::Node. */
class MinimalSubscriber : public rclcpp::Node
{
public:
  // Constructor for the class
  MinimalSubscriber()
  : Node("minimal_subscriber") // Initialize the node name
  {
    // Create a subscription to the "topic".
    // The message type is std_msgs::msg::String.
    // When a message is received, the topic_callback function is called.
    subscription_ = this->create_subscription<std_msgs::msg::String>(
      "topic", 10, std::bind(&MinimalSubscriber::topic_callback, this, _1));
  }

private:
  // This is the callback function that runs every time a message is received.
  void topic_callback(const std_msgs::msg::String & msg) const
  {
    // Log the received message to the console.
    RCLCPP_INFO(this->get_logger(), "I heard: '%s'", msg.data.c_str());
  }
  // Declare the subscription member variable.
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr subscription_;
};

// The main function, which is the entry point of the program
int main(int argc, char * argv[])
{
  // Initialize the ROS 2 C++ client library
  rclcpp::init(argc, argv);
  // "Spin" the node, which keeps it running and processing callbacks
  rclcpp::spin(std::make_shared<MinimalSubscriber>());
  // Shut down the ROS 2 C++ client library
  rclcpp::shutdown();
  return 0;
}