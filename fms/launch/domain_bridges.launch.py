#!/usr/bin/env python3
"""
Domain Bridge Launch File for Kitchmatics FMS

3개의 domain_bridge 프로세스를 실행하여 각 로봇(pinky1, pinky2, pinky3)과
메인 PC(FMS) 간의 통신을 브릿지합니다.

사용법:
    ROS_DOMAIN_ID=25 ros2 launch fms domain_bridges.launch.py

로봇 Domain ID 할당:
    - pinky1: DOMAIN_ID=11
    - pinky2: DOMAIN_ID=12
    - pinky3: DOMAIN_ID=13
    - Main PC (FMS): DOMAIN_ID=25
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # FMS 패키지 경로 (설치된 경우)
    try:
        fms_share_dir = get_package_share_directory('fms')
        config_dir = os.path.join(fms_share_dir, 'config')
    except Exception:
        # 개발 환경: 소스 디렉토리 사용
        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'config'
        )

    # 설정 파일 경로
    pinky1_config = os.path.join(config_dir, 'domain_bridge_pinky1.yaml')
    pinky2_config = os.path.join(config_dir, 'domain_bridge_pinky2.yaml')
    pinky3_config = os.path.join(config_dir, 'domain_bridge_pinky3.yaml')

    return LaunchDescription([
        # pinky1 Domain Bridge (Domain 11 <-> 25)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky1_bridge',
            arguments=[pinky1_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky2 Domain Bridge (Domain 12 <-> 25)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky2_bridge',
            arguments=[pinky2_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),

        # pinky3 Domain Bridge (Domain 13 <-> 25)
        Node(
            package='domain_bridge',
            executable='domain_bridge',
            name='pinky3_bridge',
            arguments=[pinky3_config],
            output='screen',
            respawn=True,
            respawn_delay=2.0,
        ),
    ])
