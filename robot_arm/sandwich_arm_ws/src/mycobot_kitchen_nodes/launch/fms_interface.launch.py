#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FMS Interface Launch File

FMS 통합 인터페이스를 실행합니다.

Usage:
    # Mock 모드 (실제 로봇팔 없이 테스트)
    ros2 launch mycobot_kitchen_nodes fms_interface.launch.py mock_mode:=true

    # 실제 로봇팔 연동
    ros2 launch mycobot_kitchen_nodes fms_interface.launch.py mock_mode:=false
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    # Launch Arguments
    mock_mode_arg = DeclareLaunchArgument(
        'mock_mode',
        default_value='true',
        description='Enable mock mode (no real arm required)'
    )

    status_rate_arg = DeclareLaunchArgument(
        'status_publish_rate',
        default_value='2.0',
        description='Status publish rate in Hz'
    )

    # Node
    fms_interface_node = Node(
        package='mycobot_kitchen_nodes',
        executable='fms_command_interface',
        name='fms_command_interface',
        output='screen',
        parameters=[{
            'mock_mode': LaunchConfiguration('mock_mode'),
            'status_publish_rate': LaunchConfiguration('status_publish_rate'),
        }]
    )

    return LaunchDescription([
        mock_mode_arg,
        status_rate_arg,
        fms_interface_node,
    ])
