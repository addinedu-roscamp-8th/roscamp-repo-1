"""
Launch file for Kitchmatic Main Server
"""

from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    """
    Generate launch description for Main Server

    This launches:
    - Main Server Node (ROS 2 + TCP + Database)
    """

    # Declare launch arguments
    # TODO: Add launch arguments for database config, TCP port, etc.

    return LaunchDescription([
        # Main Server Node
        Node(
            package='main_server',
            executable='main_server',
            name='main_server',
            output='screen',
            emulate_tty=True,
            parameters=[{
                # TODO: Add parameters from config file
            }]
        ),
    ])
