#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("sandwich_coordinator")

    bridge_a_path = PathJoinSubstitution([pkg_share, "config", "bridge_a.yaml"])
    bridge_b_path = PathJoinSubstitution([pkg_share, "config", "bridge_b.yaml"])

    bridge_a = Node(
        package="domain_bridge",
        executable="domain_bridge",
        name="bridge_a",
        output="screen",
        arguments=[
            bridge_a_path,
        ],
    )

    bridge_b = Node(
        package="domain_bridge",
        executable="domain_bridge",
        name="bridge_b",
        output="screen",
        arguments=[
            bridge_b_path,
        ],
    )

    coordinator_node = Node(
        package="sandwich_coordinator",
        executable="sandwich_coordinator",
        name="coordinator_node",
        output="screen",
    )

    return LaunchDescription([
        bridge_a,
        bridge_b,
        coordinator_node,
    ])