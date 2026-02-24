from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("mycobot_sauce")

    poses_sauce = PathJoinSubstitution([pkg_share, "config", "poses_sauce.yaml"])
    poses_tray = PathJoinSubstitution([pkg_share, "config", "poses_tray.yaml"])
    bias_csv = PathJoinSubstitution([pkg_share, "config", "sauce_err.csv"])

    arm_driver = Node(
        package="mycobot_sauce",
        executable="arm_driver",         
        name="arm_driver_node",
        output="screen",
        parameters=[
            {"port": "/dev/ttyJETCOBOT"},
            {"baud": 1000000},
            {"default_speed": 50},
            {"default_mode": 1},
            {"gripper_wait_sec": 1.0},
        ],
    )

    bias_provider = Node(
        package="mycobot_sauce",
        executable="bias_provider",       
        name="bias_provider_node",
        output="screen",
        parameters=[
            {"bias_csv": bias_csv},
            {"max_xyz_mm": 80.0},
            {"max_r_deg": 35.0},
            {"max_corr_mm": 25.0},
            {"max_corr_deg": 12.0},
            {"w_r_deg": 1.0},
        ],
    )

    pour_sauce = Node(
        package="mycobot_sauce",
        executable="pour_sauce",         
        name="pour_sauce_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_sauce},
        ],
    )

    send_frame = Node(
        package="mycobot_sauce",
        executable="send_frame",         
        name="send_frame_node",
        output="screen",
        parameters=[
        ],
    )

    handle_tray = Node(
        package="mycobot_sauce",
        executable="handle_tray",        
        name="handle_tray_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_tray},
            {"enable_bias": True},
            {"z_approach_mm": 30.0},
            {"z_offset_mm": 10.0},
            {"release_at_verify": False},
            {"gripper_open_value": 100},
            {"gripper_close_value": 0},
            {"gripper_speed": 50},
            {"speed_move": 50},
            {"speed_z": 30},
            {"mode": 1},
            {"settle_sec": 0.3},
        ],
    )

    verify_executor = Node(
        package="mycobot_sauce",
        executable="verify_executor",     
        name="verify_executor_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_tray}, 
            {"enable_bias": True},
        ],
    )

    trash_or_delivery = Node(
        package="mycobot_sauce",
        executable="trash_or_delivery",   
        name="trash_or_delivery_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_tray},
            {"enable_bias": True},
        ],
    )

    return LaunchDescription([
        arm_driver,
        bias_provider,
        pour_sauce,
        send_frame,
        handle_tray,
        verify_executor,
        trash_or_delivery,
    ])