"""
演示一个 launch 文件里同时 include 多个其它 launch 文件的三种常见姿势：

1) 直接 include 一个带 LaunchArgument 的子 launch，并通过 launch_arguments 传参；
2) include 一个子 launch，放进 GroupAction + PushRosNamespace，
   给它内部的节点整体加命名空间前缀；
3) 复用同一个子 launch 多次，每次用不同 namespace，彼此隔离。

重要坑：PythonLaunchDescriptionSource 内部会缓存生成出来的 LaunchDescription，
如果把 source 保存到变量再被两个 IncludeLaunchDescription 复用，两次 include
会拿到同一个 Node 对象实例，触发:
    ExecuteLocal action "...": executed more than once
所以这里每个 IncludeLaunchDescription 都独立 new 一个 source。
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import PushRosNamespace


def generate_launch_description():
    pkg_share = get_package_share_directory("launch_demo")

    param_launch_path = os.path.join(pkg_share, "launch", "param.launch.py")
    param_yaml_launch_path = os.path.join(pkg_share, "launch", "param_yaml.launch.py")

    # 1) include + launch_arguments 传参：覆盖 param.launch.py 里的 LaunchArgument
    # 背景设为蓝色 (0, 0, 255)
    include_param = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(param_launch_path),
        launch_arguments={
            "background_r": "0",
            "background_g": "0",
            "background_b": "255",
        }.items(),
    )

    # 2) include + PushRosNamespace：子 launch 内部的节点被挂到 /sim1 下
    # 最终节点路径: /sim1/turtlesim2/sim_node
    # 对应 config/turtlesim.yaml 里 /sim1/turtlesim2/sim_node 的红色配置
    group_sim1 = GroupAction([
        PushRosNamespace("sim1"),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(param_yaml_launch_path)),
    ])

    # 3) 同一个子 launch 再复用一次，挂到 /sim2 下（绿色）
    group_sim2 = GroupAction([
        PushRosNamespace("sim2"),
        IncludeLaunchDescription(PythonLaunchDescriptionSource(param_yaml_launch_path)),
    ])

    return LaunchDescription([
        include_param,
        group_sim1,
        group_sim2,
    ])
