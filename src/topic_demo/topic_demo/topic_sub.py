import rclpy
from rclpy.node import Node
# from std_msgs.msg import String
from demo_interfaces.msg import String

class TopicDemoSubscriber(Node):
    def __init__(self):
        super().__init__('topic_demo_subscriber')
        self.subscription = self.create_subscription(
            String,
            'topic_demo',
            self.listener_callback,
            10)
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        self.get_logger().info(f'I heard: "{msg.data}"')

def main(args=None):
    rclpy.init(args=args)
    topic_demo_subscriber = TopicDemoSubscriber()
    try:
        rclpy.spin(topic_demo_subscriber)
    except KeyboardInterrupt:
        pass
    finally:
        topic_demo_subscriber.destroy_node()
        rclpy.shutdown()
