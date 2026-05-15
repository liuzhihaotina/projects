"""启动 robot_state_publisher + joint_state_publisher + RViz2 显示 URDF。

运行：
    ros2 launch urdf_demo rviz_view.launch.py
    # 拖关节滑块
    ros2 launch urdf_demo rviz_view.launch.py use_gui:=true
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('urdf_demo')

    # URDF 内容（robot_state_publisher 需要 XML 字符串而不是路径）
    urdf_path = os.path.join(pkg_share, 'urdf', 'simple_demo.urdf')
    with open(urdf_path, 'r') as f:
        robot_description = f.read()

    # RViz 预置配置（包含 Fixed Frame=base_link + RobotModel 显示项）
    rviz_config = os.path.join(pkg_share, 'rviz', 'urdf.rviz')

    use_gui = LaunchConfiguration('use_gui')
    declare_use_gui = DeclareLaunchArgument(
        'use_gui',
        default_value='false',
        description='If true, run joint_state_publisher_gui (sliders).',
    )

    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description}],
    )

    jsp_node = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        output='screen',
        condition=UnlessCondition(use_gui),
    )

    jsp_gui_node = Node(
        package='joint_state_publisher_gui',
        executable='joint_state_publisher_gui',
        name='joint_state_publisher_gui',
        output='screen',
        condition=IfCondition(use_gui),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        # -d 加载配置：直接出现 RobotModel + Fixed Frame=base_link
        arguments=['-d', rviz_config],
    )

    return LaunchDescription([
        declare_use_gui,
        rsp_node,
        jsp_node,
        jsp_gui_node,
        rviz_node,
    ])
