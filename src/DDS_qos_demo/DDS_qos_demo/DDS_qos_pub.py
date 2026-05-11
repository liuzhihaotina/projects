import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from rclpy.qos import QoSProfile, QoSHistoryPolicy, QoSReliabilityPolicy, QoSDurabilityPolicy

class DDSQoSPublisher(Node):
    def __init__(self):
        super().__init__('dds_qos_publisher_node')
        qos_profile = QoSProfile(
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.VOLATILE
        )
        self.publisher_ = self.create_publisher(String, 'qos_demo_topic', qos_profile)
        self.timer = self.create_timer(1.0, self.timer_callback)
        self.i = 0

    def timer_callback(self):
        msg = String()
        msg.data = 'Hello, DDS QoS! %d' % self.i
        self.publisher_.publish(msg)
        self.get_logger().info(f'Published: {msg.data}')
        self.i += 1

def main(args=None):
    rclpy.init(args=args)
    dds_qos_publisher = DDSQoSPublisher()
    rclpy.spin(dds_qos_publisher)
    dds_qos_publisher.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()