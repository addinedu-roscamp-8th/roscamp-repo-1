#!/usr/bin/env python3
"""
Kitchmatics FMS - Closed Network Launch File

This launch file starts the FMS system with TCP communication
for the closed network (WiFi: kitchmatics)

Robots:
  Mobile Robots (PinkyPro):
    - pinky1 (pinky_b4bc): 192.168.1.7 - Domain ID 11
    - pinky2 (pinky_e2a8): 192.168.1.6 - Domain ID 12
    - pinky3 (pinky_d29d): 192.168.1.x - Domain ID 13

  Cobot Arms (JetCobot):
    - jetcobot_aa1f: 192.168.0.56
    - jetcobot_aa85: 192.168.0.59

  Main PC (FMS): Domain ID 25

Usage:
  ROS_DOMAIN_ID=25 ros2 launch fms fms_closed_network.launch.py
  ROS_DOMAIN_ID=25 ros2 launch fms fms_closed_network.launch.py use_sim:=true
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    # Package directory
    pkg_dir = get_package_share_directory('fms')

    # Launch arguments
    use_sim = LaunchConfiguration('use_sim', default='false')
    tcp_port = LaunchConfiguration('tcp_port', default='9000')

    # Config file paths
    fms_config_file = os.path.join(pkg_dir, 'config', 'fms_config.yaml')
    network_config_file = os.path.join(pkg_dir, 'config', 'network_config.yaml')

    # Domain Bridge config file paths
    bridge_pinky1_config = os.path.join(pkg_dir, 'config', 'bridge_pinky1.yaml')
    bridge_pinky1_reverse_config = os.path.join(pkg_dir, 'config', 'bridge_pinky1_reverse.yaml')
    bridge_pinky2_config = os.path.join(pkg_dir, 'config', 'bridge_pinky2.yaml')
    bridge_pinky2_reverse_config = os.path.join(pkg_dir, 'config', 'bridge_pinky2_reverse.yaml')
    bridge_pinky3_config = os.path.join(pkg_dir, 'config', 'bridge_pinky3.yaml')
    bridge_pinky3_reverse_config = os.path.join(pkg_dir, 'config', 'bridge_pinky3_reverse.yaml')

    # Robot Arms domain bridge config
    bridge_arms_config = os.path.join(pkg_dir, 'config', 'domain_bridge_arms.yaml')

    return LaunchDescription([
        # Declare launch arguments
        DeclareLaunchArgument(
            'use_sim',
            default_value='false',
            description='Use simulation time'
        ),
        DeclareLaunchArgument(
            'tcp_port',
            default_value='9000',
            description='FMS TCP Server port (used by fms_node gui_tcp_server)'
        ),

        # CRITICAL FIX: Removed fms_tcp_node to avoid port 9000 conflict
        # fms_tcp_node was for robot TCP communication (old architecture)
        # fms_node has embedded gui_tcp_server for GUI communication (current architecture)
        # Having both causes "No handler for message type: new_order" warnings

        # FMS Node with embedded GUI TCP Server (port 9000)
        Node(
            package='fms',
            executable='fms_node',
            name='fms_node',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim},
                {'config_file': fms_config_file},
            ]
        ),

        # ============================================================
        # Domain Bridges for Mobile Robots (pinky1, pinky2, pinky3)
        # ============================================================

        # pinky1 Domain Bridge: Domain 11 -> Domain 25 (Robot to FMS)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky1_bridge',
            arguments=[bridge_pinky1_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky1 Reverse Domain Bridge: Domain 25 -> Domain 11 (FMS to Robot)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky1_reverse_bridge',
            arguments=[bridge_pinky1_reverse_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky2 Domain Bridge: Domain 12 -> Domain 25 (Robot to FMS)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky2_bridge',
            arguments=[bridge_pinky2_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky2 Reverse Domain Bridge: Domain 25 -> Domain 12 (FMS to Robot)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky2_reverse_bridge',
            arguments=[bridge_pinky2_reverse_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky3 Domain Bridge: Domain 13 -> Domain 25 (Robot to FMS)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky3_bridge',
            arguments=[bridge_pinky3_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky3 Reverse Domain Bridge: Domain 25 -> Domain 13 (FMS to Robot)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky3_reverse_bridge',
            arguments=[bridge_pinky3_reverse_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # ============================================================
        # Domain Bridge for Robot Arms (armA, armB)
        # ============================================================

        # Robot Arms Domain Bridge: Domain 20, 21 <-> Domain 25
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='arms_bridge',
            arguments=[bridge_arms_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
    ])
