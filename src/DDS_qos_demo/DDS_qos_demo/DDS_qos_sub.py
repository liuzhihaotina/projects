import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy, QoSDurabilityPolicy

class DDSQoSSubscriber(Node):
    def __init__(self):
        super().__init__('dds_qos_subscriber_node')
        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE
        )
        self.subscription = self.create_subscription(
            String,
            'qos_demo_topic',
            self.listener_callback,
            qos_profile
        )
        self.subscription  # prevent unused variable warning

    def listener_callback(self, msg):
        self.get_logger().info(f'Received: {msg.data}')

def main(args=None):
    rclpy.init(args=args)
    dds_qos_subscriber = DDSQoSSubscriber()
    rclpy.spin(dds_qos_subscriber)
    dds_qos_subscriber.destroy_node()
    rclpy.shutdown()