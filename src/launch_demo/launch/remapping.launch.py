from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='DDS_qos_demo',
            executable='dds_qos_pub_node',
            name='dds_qos_publisher_node',
            remappings=[('qos_demo_topic', 'remapped_qos_demo_topic')]
        ),
        Node(
            package='DDS_qos_demo',
            executable='dds_qos_sub_node',
            name='dds_qos_subscriber_node',
            remappings=[('qos_demo_topic', 'remapped_qos_demo_topic')]
        )
    ])