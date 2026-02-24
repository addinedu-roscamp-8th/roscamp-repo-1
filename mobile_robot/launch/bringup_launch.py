#!/usr/bin/env python3
"""
Kitchmatics - Multi-Robot Navigation Launch File with Frame Prefix Support

이 파일을 로봇의 ~/pinky_pro/src/pinky_pro/pinky_navigation/launch/bringup_launch.py에 오버라이드

핵심 기능:
  - RewrittenYaml을 사용하여 frame 이름에 namespace prefix 자동 추가
  - 하나의 nav2_params.yaml로 pinky1, pinky2, pinky3 모두 지원

사용법 (로봇에서):
  ros2 launch pinky_navigation bringup_launch.py namespace:=pinky1 map:=real.yaml
  ros2 launch pinky_navigation bringup_launch.py namespace:=pinky2 map:=real.yaml
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, PushRosNamespace
from launch_ros.substitutions import FindPackageShare
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    # Package directories
    pkg_nav = get_package_share_directory('pinky_navigation')

    # Launch arguments
    namespace_arg = DeclareLaunchArgument(
        'namespace',
        default_value='',
        description='Robot namespace (pinky1, pinky2, pinky3)'
    )

    map_arg = DeclareLaunchArgument(
        'map',
        default_value='map.yaml',
        description='Map file name (will look in home directory)'
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
        default_value=os.path.join(pkg_nav, 'params', 'nav2_params.yaml'),
        description='Nav2 parameters file'
    )

    # Get launch configurations
    namespace = LaunchConfiguration('namespace')
    map_file = LaunchConfiguration('map')
    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')

    # Frame substitutions - namespace를 frame 이름 앞에 추가
    # 예: base_footprint -> pinky1/base_footprint
    param_substitutions = {
        'use_sim_time': use_sim_time,
        # AMCL frames
        'base_frame_id': [namespace, '/base_footprint'],
        'odom_frame_id': [namespace, '/odom'],
        # Costmap frames
        'robot_base_frame': [namespace, '/base_footprint'],
        'global_frame': 'map',  # map frame은 공유
        # Behavior server
        'local_frame': [namespace, '/odom'],
        # Topics
        'odom_topic': [namespace, '/odom'],
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
