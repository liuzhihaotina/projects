import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from demo_interfaces.action import FileDownload

class FileDownloadActionClient(Node):
    def __init__(self):
        super().__init__('file_download_action_client')
        self._action_client = ActionClient(self, FileDownload, 'file_download')

    def send_goal(self, file_size):
        goal_msg = FileDownload.Goal()
        goal_msg.file_size = file_size

        self.get_logger().info(f'Sending file download goal for {file_size} bytes...')

        self._action_client.wait_for_server()
        self.get_logger().info('Sending file download request...')
        self._send_goal_future = self._action_client.send_goal_async(goal_msg, feedback_callback=self.feedback_callback)
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().info('Goal rejected :(')
            return

        self.get_logger().info('Goal accepted :)')
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def feedback_callback(self, feedback_msg):
        feedback = feedback_msg.feedback
        self.get_logger().info(f'Received feedback: {feedback.completion_percentage:.2f}% complete')

    def get_result_callback(self, future):
        result = future.result().result
        self.get_logger().info(f'File download completed with final size: {result.current_size} bytes')

def main(args=None):
    rclpy.init(args=args)
    file_download_action_client = FileDownloadActionClient()
    file_download_action_client.send_goal(1000)  # Request to download a file of 1000 bytes
    try:
        rclpy.spin(file_download_action_client)
    except KeyboardInterrupt:
        pass
    finally:
        file_download_action_client.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()