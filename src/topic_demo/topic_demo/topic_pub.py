import rclpy
from rclpy.node import Node
# from std_msgs.msg import String
from demo_interfaces.msg import String

class TopicDemoPublisher(Node):
    def __init__(self):
        super().__init__('topic_demo_publisher')
        self.publisher_ = self.create_publisher(String, 'topic_demo', 10)
        timer_period = 1.0  # seconds
        self.timer = self.create_timer(timer_period, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = f'Hello, this is message number {self.i}'
        self.publisher_.publish(msg)
        self.get_logger().info(f'Publishing: "{msg.data}"')
        self.i += 1

def main(args=None):
    rclpy.init(args=args)
    topic_demo_publisher = TopicDemoPublisher()
    try:
        rclpy.spin(topic_demo_publisher)
    except KeyboardInterrupt:
        pass
    finally:
        topic_demo_publisher.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()