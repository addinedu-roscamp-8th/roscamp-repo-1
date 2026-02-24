#!/usr/bin/env python3
"""
Kitchmatics - Pinky Navigation Launch File
이 파일을 로봇의 ~/pinky_pro/src/pinky_pro/pinky_navigation/launch/에 오버라이드

로봇별 namespace 설정:
  - pinky_b4bc → namespace: pinky1
  - pinky_e2a8 → namespace: pinky2
  - pinky_d29d → namespace: pinky3

사용법:
  ros2 launch pinky_navigation pinky_navigation.launch.py robot_name:=pinky_b4bc
  ros2 launch pinky_navigation pinky_navigation.launch.py robot_name:=pinky_e2a8
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node, PushRosNamespace


# 로봇 이름 → namespace 매핑
ROBOT_NAMESPACE_MAP = {
    'pinky_b4bc': 'pinky1',
    'pinky_e2a8': 'pinky2',
    'pinky_d29d': 'pinky3',
}


def generate_launch_description():
    # Launch arguments
    robot_name_arg = DeclareLaunchArgument(
        'robot_name',
        default_value='pinky_b4bc',
        description='Robot name (pinky_b4bc, pinky_e2a8, pinky_d29d)'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    # 로봇 이름으로 namespace 결정
    robot_name = LaunchConfiguration('robot_name')
    use_sim_time = LaunchConfiguration('use_sim_time')

    # Package directories
    pkg_dir = get_package_share_directory('pinky_navigation')

    # Nav2 params file
    nav2_params_file = os.path.join(pkg_dir, 'params', 'nav2_params.yaml')

    # Map file
    map_file = os.path.join(pkg_dir, 'maps', 'map.yaml')

    # Nav2 bringup launch file
    nav2_bringup_dir = get_package_share_directory('nav2_bringup')
    nav2_launch_file = os.path.join(nav2_bringup_dir, 'launch', 'bringup_launch.py')

    # pinky_b4bc (pinky1) 그룹
    pinky1_group = GroupAction(
        condition=IfCondition(
            PythonExpression(["'", robot_name, "' == 'pinky_b4bc'"])
        ),
        actions=[
            PushRosNamespace('pinky1'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch_file),
                launch_arguments={
                    'namespace': 'pinky1',
                    'use_namespace': 'true',
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'map': map_file,
                    'autostart': 'true',
                }.items()
            ),
        ]
    )

    # pinky_e2a8 (pinky2) 그룹
    pinky2_group = GroupAction(
        condition=IfCondition(
            PythonExpression(["'", robot_name, "' == 'pinky_e2a8'"])
        ),
        actions=[
            PushRosNamespace('pinky2'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch_file),
                launch_arguments={
                    'namespace': 'pinky2',
                    'use_namespace': 'true',
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'map': map_file,
                    'autostart': 'true',
                }.items()
            ),
        ]
    )

    # pinky_d29d (pinky3) 그룹
    pinky3_group = GroupAction(
        condition=IfCondition(
            PythonExpression(["'", robot_name, "' == 'pinky_d29d'"])
        ),
        actions=[
            PushRosNamespace('pinky3'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_launch_file),
                launch_arguments={
                    'namespace': 'pinky3',
                    'use_namespace': 'true',
                    'use_sim_time': use_sim_time,
                    'params_file': nav2_params_file,
                    'map': map_file,
                    'autostart': 'true',
                }.items()
            ),
        ]
    )

    return LaunchDescription([
        robot_name_arg,
        use_sim_time_arg,
        pinky1_group,
        pinky2_group,
        pinky3_group,
    ])
