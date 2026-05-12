import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    config_file_path = os.path.join(get_package_share_directory('launch_demo'), 'config', 'turtlesim.yaml')
    return LaunchDescription([
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            name='sim_node',
            namespace='turtlesim2',
            parameters=[config_file_path]
        )
    ])