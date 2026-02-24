#!/usr/bin/env python3
"""
Kitchmatics - Multi-Robot Navigation Launch File

로봇에서 직접 실행:
  ros2 launch ~/roscamp-repo-1/mobile_robot/launch/bringup_launch.py namespace:=pinky1 map:=~/real.yaml

핵심 기능:
  - RewrittenYaml을 사용하여 frame 이름에 namespace prefix 자동 추가
  - 하나의 nav2_params.yaml로 pinky1, pinky2, pinky3 모두 지원
  - roscamp-repo-1의 params 파일 사용 (로봇 내장 코드 수정 불필요)
"""

import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, PushRosNamespace
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    # roscamp-repo-1 경로 (이 파일 기준으로 계산)
    launch_dir = Path(__file__).parent
    repo_dir = launch_dir.parent.parent  # roscamp-repo-1
    params_dir = launch_dir.parent / 'params'

    # 기본 params 파일 경로
    default_params_file = str(params_dir / 'nav2_params.yaml')

    # 홈 디렉토리
    home_dir = Path.home()
    default_map_file = str(home_dir / 'real.yaml')

    # Launch arguments
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='pinky1',
        description='Robot namespace (pinky1, pinky2, pinky3)'
    )

    map_arg = DeclareLaunchArgument(
        'map',
        default_value=default_map_file,
        description='Full path to map yaml file'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Use simulation time'
    )

    autostart_arg = DeclareLaunchArgument(
        'autostart',
        default_value='true',
        description='Automatically start lifecycle nodes'
    )

    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=default_params_file,
        description='Nav2 parameters file'
    )

    # Get launch configurations
    namespace = LaunchConfiguration('namespace')
    map_file = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')

    # Frame substitutions - 로봇이 namespace prefix 없이 TF 발행하므로 그대로 사용
    # 로봇 TF: odom -> base_footprint (prefix 없음)
    param_substitutions = {
        'use_sim_time': use_sim_time,
        # AMCL frames - prefix 없음
        'base_frame_id': 'base_footprint',
        'odom_frame_id': 'odom',
        # Costmap frames - prefix 없음
        'robot_base_frame': 'base_footprint',
        'global_frame': 'map',
        # Behavior server
        'local_frame': 'odom',
        # Topics - namespace 내에서 상대 경로
        'odom_topic': 'odom',
        'scan_topic': '/scan',
    }

    # RewrittenYaml - params 파일의 값을 동적으로 치환
    configured_params = RewrittenYaml(
        source_file=params_file,
        root_key=namespace,
        param_rewrites=param_substitutions,
        convert_types=True
    )

    # Lifecycle nodes
    lifecycle_nodes_localization = ['map_server', 'amcl']
    lifecycle_nodes_navigation = [
        'controller_server',
        'planner_server',
        'behavior_server',
        'bt_navigator',
        'waypoint_follower',
        'velocity_smoother'
    ]

    # Map Server Node
    map_server_node = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[
            configured_params,
            {'yaml_filename': map_file}
        ],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # AMCL Node
    amcl_node = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # Controller Server
    controller_server_node = Node(
        package='nav2_controller',
        executable='controller_server',
        name='controller_server',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static'),
            ('cmd_vel', 'cmd_vel_nav')
        ]
    )

    # Planner Server
    planner_server_node = Node(
        package='nav2_planner',
        executable='planner_server',
        name='planner_server',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # Behavior Server
    behavior_server_node = Node(
        package='nav2_behaviors',
        executable='behavior_server',
        name='behavior_server',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # BT Navigator
    bt_navigator_node = Node(
        package='nav2_bt_navigator',
        executable='bt_navigator',
        name='bt_navigator',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # Waypoint Follower
    waypoint_follower_node = Node(
        package='nav2_waypoint_follower',
        executable='waypoint_follower',
        name='waypoint_follower',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static')
        ]
    )

    # Velocity Smoother
    velocity_smoother_node = Node(
        package='nav2_velocity_smoother',
        executable='velocity_smoother',
        name='velocity_smoother',
        output='screen',
        parameters=[configured_params],
        remappings=[
            ('/tf', 'tf'),
            ('/tf_static', 'tf_static'),
            ('cmd_vel', 'cmd_vel_nav'),
            ('cmd_vel_smoothed', 'cmd_vel')
        ]
    )

    # Lifecycle Manager - Localization
    lifecycle_manager_localization = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_localization',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': autostart},
            {'node_names': lifecycle_nodes_localization}
        ]
    )

    # Lifecycle Manager - Navigation
    lifecycle_manager_navigation = Node(
        package='nav2_lifecycle_manager',
        executable='lifecycle_manager',
        name='lifecycle_manager_navigation',
        output='screen',
        parameters=[
            {'use_sim_time': use_sim_time},
            {'autostart': autostart},
            {'node_names': lifecycle_nodes_navigation}
        ]
    )

    # All nodes in namespace group
    namespaced_nodes = GroupAction(
        actions=[
            PushRosNamespace(namespace),
            map_server_node,
            amcl_node,
            controller_server_node,
            planner_server_node,
            behavior_server_node,
            bt_navigator_node,
            waypoint_follower_node,
            velocity_smoother_node,
            lifecycle_manager_localization,
            lifecycle_manager_navigation,
        ]
    )

    return LaunchDescription([
        # Environment
        SetEnvironmentVariable('RCUTILS_LOGGING_BUFFERED_STREAM', '1'),

        # Arguments
        namespace_arg,
        map_arg,
        use_sim_time_arg,
        autostart_arg,
        params_file_arg,

        # Nodes
        namespaced_nodes,
    ])
