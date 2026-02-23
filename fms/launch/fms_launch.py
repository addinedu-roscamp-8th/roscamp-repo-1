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

    return LaunchDescription([
        config_arg,

        # FMS Node
        Node(
            package='fms',
            executable='fms_node',
            name='fms_node',
            output='screen',
            emulate_tty=True,
            parameters=[LaunchConfiguration('config_file')]
        ),
    ])
