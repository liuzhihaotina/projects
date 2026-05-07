import sys
import rclpy
from rclpy.node import Node
from demo_interfaces.srv import AddInts

class ServiceDemoClient(Node):
    def __init__(self):
        super().__init__('service_demo_client')
        self.cli = self.create_client(AddInts, 'add_two_ints')
        while not self.cli.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Service not available, waiting again...')

    def send_request(self, a, b):
        req = AddInts.Request()
        req.num1 = a
        req.num2 = b
        self.future = self.cli.call_async(req)

def main(args=None):
    if len(sys.argv) != 3:
        print("Usage: ros2 run service_demo service_client <int a> <int b>")
        return

    rclpy.init(args=args)
    service_demo_client = ServiceDemoClient()
    service_demo_client.send_request(int(sys.argv[1]), int(sys.argv[2]))
    rclpy.spin(service_demo_client)  # choice1 让节点持续运行，直到服务响应完成
    # rclpy.spin_until_future_complete(service_demo_client, service_demo_client.future)  # choice2 一次就停下
    try:
        response = service_demo_client.future.result()
        service_demo_client.get_logger().info(f'Result of {sys.argv[1]} + {sys.argv[2]} = {response.sum}')
    except Exception as e:
        service_demo_client.get_logger().error(f'Service call failed: {e}')
    finally:
        service_demo_client.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()