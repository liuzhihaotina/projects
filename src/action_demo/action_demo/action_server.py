import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer
from demo_interfaces.action import FileDownload
import random
import time

class FileDownloadActionServer(Node):
    def __init__(self):
        super().__init__('file_download_action_server')
        self._action_server = ActionServer(
            self,
            FileDownload,
            'file_download',
            self.execute_callback)

    def execute_callback(self, goal_handle):
        file_size = goal_handle.request.file_size
        self.get_logger().info(f'Starting file download for: {file_size} bytes...')
        feedback_msg = FileDownload.Feedback()
        current_size = 0
        while current_size < file_size:
            # Simulate downloading by incrementing current_size randomly
            increment = random.randint(1, 100)  # Simulate download speed
            current_size += increment
            if current_size > file_size:
                current_size = file_size

            feedback_msg.completion_percentage = (current_size / file_size) * 100
            goal_handle.publish_feedback(feedback_msg)
            self.get_logger().info(f'Current download progress: {feedback_msg.completion_percentage:.2f}%')
            time.sleep(0.5)  # Simulate time delay for downloading

        goal_handle.succeed()
        result = FileDownload.Result()
        result.current_size = current_size
        self.get_logger().info('File download completed successfully!')
        return result

def main(args=None):
    rclpy.init(args=args)
    file_download_action_server = FileDownloadActionServer()
    try:
        file_download_action_server.get_logger().info('Starting File Download Action Server...')
        rclpy.spin(file_download_action_server)
    except KeyboardInterrupt:
        pass
    finally:
        file_download_action_server.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
