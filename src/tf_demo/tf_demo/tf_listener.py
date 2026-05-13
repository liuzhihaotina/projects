#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""TF 监听节点：周期性查询两个坐标系之间的相对变换并打印。

用法示例：
    # 使用默认参数 (source_frame=world, target_frame=base_link, period=1.0s)
    ros2 run tf_demo tf_listener

    # 运行时指定坐标系
    ros2 run tf_demo tf_listener --ros-args \
        -p source_frame:=world -p target_frame:=base_link -p timer_period:=0.5
"""

import rclpy
from rclpy.node import Node
from rclpy.time import Time

import tf_transformations
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener


class TFListener(Node):
    """实时监测指定坐标系间的动态转换关系。"""

    def __init__(self):
        super().__init__('tf_listener')

        # 动态参数：源坐标系、目标坐标系、查询周期（秒）
        self.declare_parameter('source_frame', 'world')
        self.declare_parameter('target_frame', 'base_link')
        self.declare_parameter('timer_period', 1.0)

        # TF 缓冲区 + 监听器；监听器会在后台订阅 /tf 与 /tf_static，
        # 把收到的变换写进 buffer，lookup_transform 从 buffer 查。
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        period = self.get_parameter('timer_period').get_parameter_value().double_value
        # 兜底：避免传 0 导致定时器异常
        if period <= 0.0:
            period = 1.0
        self.timer = self.create_timer(period, self.on_timer)

        self.get_logger().info(
            f'TFListener started: {self._source()} -> {self._target()}, period={period:.2f}s'
        )

    # ---- 参数读取放成方法，支持运行时通过 ros2 param set 动态切换 ----
    def _source(self) -> str:
        return self.get_parameter('source_frame').get_parameter_value().string_value

    def _target(self) -> str:
        return self.get_parameter('target_frame').get_parameter_value().string_value

    def on_timer(self):
        source_frame = self._source()
        target_frame = self._target()

        try:
            # Time() 表示“拿最新可用的那一帧变换”
            transform = self.tf_buffer.lookup_transform(
                source_frame,
                target_frame,
                Time(),
            )
        except TransformException as ex:
            # 典型异常：LookupException / ConnectivityException / ExtrapolationException
            # 都是 TransformException 的子类，统一在这里降级为 warn
            self.get_logger().warn(
                f'Could not transform {source_frame} -> {target_frame}: {ex}'
            )
            return

        t = transform.transform.translation
        q = transform.transform.rotation
        roll, pitch, yaw = tf_transformations.euler_from_quaternion(
            [q.x, q.y, q.z, q.w]
        )

        self.get_logger().info(
            f'[{source_frame} -> {target_frame}] '
            f'T=({t.x:.3f}, {t.y:.3f}, {t.z:.3f})  '
            f'Q=({q.x:.3f}, {q.y:.3f}, {q.z:.3f}, {q.w:.3f})  '
            f'RPY=({roll:.3f}, {pitch:.3f}, {yaw:.3f}) rad'
        )


def main(args=None):
    rclpy.init(args=args)
    node = TFListener()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
