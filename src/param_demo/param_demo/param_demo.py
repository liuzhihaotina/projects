import rclpy
from rclpy.node import Node
from rclpy.parameter import Parameter

class ParamDemo(Node):
    def __init__(self):
        super().__init__('param_demo_node')
        self.declare_parameter('my_param', 'default_value')
        self.get_logger().info(f"Initial parameter value: {self.get_parameter('my_param').value}")
        self.create_timer(5.0, self.timer_callback)

    def timer_callback(self):
        param_value = self.get_parameter('my_param').value
        self.get_logger().info(f"Current parameter value: {param_value}")

def main(args=None):
    rclpy.init(args=args)
    param_demo = ParamDemo()
    rclpy.spin(param_demo)
    param_demo.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

