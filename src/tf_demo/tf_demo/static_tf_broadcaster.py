#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
import tf_transformations
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster

class StaticTfBroadcaster(Node):
    def __init__(self):
        super().__init__('static_tf_broadcaster')
        self.broadcaster = StaticTransformBroadcaster(self)
        self.timer = self.create_timer(0.1, self.broadcast_static_transform)

    def broadcast_static_transform(self):
        static_transform = TransformStamped()
        static_transform.header.stamp = self.get_clock().now().to_msg()
        static_transform.header.frame_id = 'world'
        static_transform.child_frame_id = 'base_link'
        static_transform.transform.translation.x = 1.0
        static_transform.transform.translation.y = 0.0
        static_transform.transform.translation.z = 0.0
        quat = tf_transformations.quaternion_from_euler(0.0, 0.0, 0.0)
        static_transform.transform.rotation.x = quat[0]
        static_transform.transform.rotation.y = quat[1]
        static_transform.transform.rotation.z = quat[2]
        static_transform.transform.rotation.w = quat[3]
        
        self.broadcaster.sendTransform(static_transform)

def main(args=None):
    rclpy.init(args=args)
    node = StaticTfBroadcaster()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()