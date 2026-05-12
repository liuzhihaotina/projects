from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, TextSubstitution

def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'background_r',
            default_value=TextSubstitution(text='10'),
            description='Red component of background color (0-255)'
        ),
        DeclareLaunchArgument(
            'background_g',
            default_value=TextSubstitution(text='255'),
            description='Green component of background color (0-255)'
        ),
        DeclareLaunchArgument(
            'background_b',
            default_value=TextSubstitution(text='255'),
            description='Blue component of background color (0-255)'
        ),
        Node(
            package='turtlesim',
            executable='turtlesim_node',
            name='sim_node',
            parameters=[{
                'background_r': LaunchConfiguration('background_r'),
                'background_g': LaunchConfiguration('background_g'),
                'background_b': LaunchConfiguration('background_b'),
            }]
        )
    ])