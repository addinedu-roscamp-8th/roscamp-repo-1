"""
Launch file for Kitchmatic Fleet Management System (FMS)
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    """
    Generate launch description for FMS

    This launches:
    - FMS Node (Fleet Management System)
    """

    # Get package directory
    pkg_fms = get_package_share_directory('fms')

    # Config file path
    config_file = PathJoinSubstitution([
        FindPackageShare('fms'),
        'config',
        'fms_config.yaml'
    ])

    # Declare launch arguments
    config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to FMS configuration file'
    )

    # Declare active robot argument
    active_robot_arg = DeclareLaunchArgument(
        'active_robot',
        default_value='pinky1',
        description='Active robot for cmd_vel relay'
    )

    return LaunchDescription([
        config_arg,
        active_robot_arg,

        # FMS Node
        Node(
            package='fms',
            executable='fms_node',
            name='fms_node',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'config_file': LaunchConfiguration('config_file'),
                'skip_robot_arm': True
            }]
        ),

        # cmd_vel Relay Node
        Node(
            package='fms',
            executable='cmd_vel_relay',
            name='cmd_vel_relay',
            output='screen',
            parameters=[{
                'robot_namespaces': ['pinky1', 'pinky2', 'pinky3'],
                'active_robot': LaunchConfiguration('active_robot')
            }]
        ),
    ])
