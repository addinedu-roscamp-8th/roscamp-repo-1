from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("server_url", default_value="http://192.168.0.27:5001"),
        DeclareLaunchArgument("interval_sec", default_value="1.0"),
        DeclareLaunchArgument("api_mode", default_value="image"),
        Node(
            package="yolo_analysis_client",
            executable="yolo_client_node",
            name="yolo_client_node",
            parameters=[{
                "server_url": LaunchConfiguration("server_url"),
                "interval_sec": LaunchConfiguration("interval_sec"),
                "api_mode": LaunchConfiguration("api_mode"),
            }],
        ),
    ])
