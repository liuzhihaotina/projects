import rclpy
from rclpy.node import Node
from demo_interfaces.srv import AddInts

class ServiceDemoServer(Node):
    def __init__(self):
        super().__init__('service_demo_server')
        self.srv = self.create_service(AddInts, 'add_two_ints', self.add_two_ints_callback)

    def add_two_ints_callback(self, request, response):
        response.sum = request.num1 + request.num2
        self.get_logger().info(f'Incoming request: num1={request.num1}, num2={request.num2}, sum={response.sum}')
        return response
    
def main(args=None):
    rclpy.init(args=args)
    service_demo_server = ServiceDemoServer()
    try:
        rclpy.spin(service_demo_server)
    except KeyboardInterrupt:
        pass
    finally:
        service_demo_server.destroy_node()
        rclpy.shutdown()