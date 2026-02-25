#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sandwich Coordinator Launch File

Usage:
    # 테스트 모드 (기본값) - 로봇팔 팀 디버깅용
    ros2 launch sandwich_coordinator coordinator_all.launch.py

    # 테스트 모드 - 다른 메뉴/소스 테스트
    ros2 launch sandwich_coordinator coordinator_all.launch.py test_recipe:=mushroom test_sauce:=ketchup

    # 프로덕션 모드 - FMS 연동
    ros2 launch sandwich_coordinator coordinator_all.launch.py test_mode:=false
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("sandwich_coordinator")

    bridge_a_path = PathJoinSubstitution([pkg_share, "config", "bridge_a.yaml"])
    bridge_b_path = PathJoinSubstitution([pkg_share, "config", "bridge_b.yaml"])

    # ===== Launch Arguments =====
    test_mode_arg = DeclareLaunchArgument(
        'test_mode',
        default_value='true',
        description='테스트 모드 (true: 하드코딩 주문 실행, false: FMS 주문 대기)'
    )

    test_recipe_arg = DeclareLaunchArgument(
        'test_recipe',
        default_value='ham_cheese',
        description='테스트 레시피 (ham_cheese, mushroom, all_in_one)'
    )

    test_sauce_arg = DeclareLaunchArgument(
        'test_sauce',
        default_value='mustard',
        description='테스트 소스 (mayo, mustard, ketchup, 또는 빈 문자열)'
    )

    test_pause_arg = DeclareLaunchArgument(
        'test_pause_before_last',
        default_value='1',
        description='마지막 재료 전 대기 시간'
    )

    # ===== Nodes =====
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
        parameters=[{
            'test_mode': LaunchConfiguration('test_mode'),
            'test_recipe': LaunchConfiguration('test_recipe'),
            'test_sauce': LaunchConfiguration('test_sauce'),
            'test_pause_before_last': LaunchConfiguration('test_pause_before_last'),
        }],
    )

    return LaunchDescription([
        # Launch arguments
        test_mode_arg,
        test_recipe_arg,
        test_sauce_arg,
        test_pause_arg,
        # Nodes
        bridge_a,
        bridge_b,
        coordinator_node,
    ])