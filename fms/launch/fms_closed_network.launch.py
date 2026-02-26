#!/usr/bin/env python3
"""
Kitchmatics FMS - Closed Network Launch File

This launch file starts the FMS system with TCP communication
for the closed network (WiFi: kitchmatics)

Robots:
  Mobile Robots (PinkyPro):
    - pinky_b4bc: 192.168.1.7
    - pinky_e2a8: 192.168.1.6
    - pinky_d29d: 보류 (disabled)

  Cobot Arms (JetCobot):
    - jetcobot_aa1f: 192.168.0.56
    - jetcobot_aa85: 192.168.0.59

Usage:
  ros2 launch fms fms_closed_network.launch.py
  ros2 launch fms fms_closed_network.launch.py use_sim:=true
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
    ])
