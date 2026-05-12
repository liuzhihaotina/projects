import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, GroupAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import PushRosNamespace


def generate_launch_description():
    sub_launch_path = os.path.join(
        get_package_share_directory('launch_demo'),
        'launch',
        'param_yaml.launch.py',
    )

    # 注意：PythonLaunchDescriptionSource 会缓存生成出来的 LaunchDescription，
    # 复用同一个 source 会让两次 include 拿到同一个 Node 对象，
    # 触发 "executed more than once" 错误。
    # 所以每个 IncludeLaunchDescription 都要用独立的 source 实例。
    group_sim1 = GroupAction([
        PushRosNamespace('sim1'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(sub_launch_path)),
    ])

    group_sim2 = GroupAction([
        PushRosNamespace('sim2'),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(sub_launch_path)),
    ])

    # 最终节点路径:
    #   /sim1/turtlesim2/sim_node   (红色背景)
    #   /sim2/turtlesim2/sim_node   (绿色背景)
    return LaunchDescription([
        group_sim1,
        group_sim2,
    ])
