import rclpy
from rclpy.node import Node
import time

class HelloWorldNode(Node):
    def __init__(self):
        # 调用基类 Node 的构造函数，设置节点名称
        super().__init__('hello_world_demo')

    def run(self):
        # 在 ROS2 系统正常运行的情况下执行循环
        while rclpy.ok():
            # 打印 "Hello World" 到节点的日志
            self.get_logger().info('Hello World')

            # 休眠 0.5 秒，控制循环时间
            time.sleep(0.5)

def main(args=None):
    # 初始化 ROS2 Python 接口
    rclpy.init(args=args)

    # 创建 HelloWorldNode 实例
    node = HelloWorldNode()

    try:
        # 运行节点的主循环
        node.run()
    except KeyboardInterrupt:
        pass
    finally:
        pass