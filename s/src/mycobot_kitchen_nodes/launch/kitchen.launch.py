from launch import LaunchDescription
from launch_ros.actions import Node
from launch.substitutions import PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("mycobot_kitchen_nodes")

    poses_yaml = PathJoinSubstitution([pkg_share, "config", "poses.yaml"])
    recipes_yaml = PathJoinSubstitution([pkg_share, "config", "recipes.yaml"])
    bias_csv = PathJoinSubstitution([pkg_share, "config", "bias_err.csv"])
    inventory_yaml = PathJoinSubstitution([pkg_share, "config", "inventory.yaml"])

    # ---- Nodes ----
    bias_provider = Node(
        package="mycobot_kitchen_nodes",
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

    inventory_manager = Node(
        package="mycobot_kitchen_nodes",
        executable="inventory_manager",
        name="inventory_manager_node",
        output="screen",
        parameters=[
            {"inventory_yaml": inventory_yaml},  # YAML 기반 초기/운영 (DB는 나중)
        ],
    )

    arm_driver = Node(
        package="mycobot_kitchen_nodes",
        executable="arm_driver",
        name="arm_driver_node",
        output="screen",
        parameters=[
            {"port": "/dev/ttyJETCOBOT"},
            {"baud": 1000000},
            {"default_speed": 50},
            {"default_mode": 1},
            {"default_settle_sec": 1.5},

            # suction (통합 driver에 포함된 경우만 의미 있음)
            {"suction_gpio": 23},
            {"suction_active_high": False},
            {"pump_on_delay": 1.5},
            {"pump_off_delay": 0.5},

            # gripper (통합 driver에 포함된 경우만)
            {"gripper_wait_sec": 1.0},
        ],
    )

    recipe_executor = Node(
        package="mycobot_kitchen_nodes",
        executable="recipe_executor",
        name="recipe_executor_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_yaml},
            {"recipes_yaml": recipes_yaml},
            {"item_thickness_mm": 5.0},
        ],
    )

    refill_executor = Node(
        package="mycobot_kitchen_nodes",
        executable="refill_executor",
        name="refill_executor_node",
        output="screen",
        parameters=[
            {"poses_yaml": poses_yaml},
        ],
    )

    return LaunchDescription([
        bias_provider,
        inventory_manager,
        arm_driver,
        recipe_executor,
        refill_executor,
    ])
