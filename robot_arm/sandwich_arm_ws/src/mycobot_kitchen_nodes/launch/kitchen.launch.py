from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare("mycobot_kitchen_nodes")

    poses_yaml = PathJoinSubstitution([pkg_share, "config", "poses.yaml"])
    recipes_yaml = PathJoinSubstitution([pkg_share, "config", "recipes.yaml"])
    bias_csv = PathJoinSubstitution([pkg_share, "config", "bias_err.csv"])

    # env (주의: ROS_DOMAIN_ID를 여기서 고정하면 터미널 export보다 이게 우선됨)
    env = [
        SetEnvironmentVariable("PGHOST", "192.168.0.27"),
        SetEnvironmentVariable("PGPORT", "5432"),
        SetEnvironmentVariable("PGDATABASE", "pinky_robot_store"),
        SetEnvironmentVariable("PGUSER", "deepdive"),
        SetEnvironmentVariable("PGPASSWORD", "deepdive_team123!#"),
        SetEnvironmentVariable("PGSSLMODE", "disable"),
    ]

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
            # suction
            {"suction_gpio": 23},
            {"suction_active_high": False},
            {"pump_on_delay": 1.5},
            {"pump_off_delay": 0.5},
            # gripper
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
        parameters=[{"poses_yaml": poses_yaml}],
    )

    inv_table = DeclareLaunchArgument(
        "inv_table",
        default_value="inventory_item",
        description="Postgres inventory table name",
    )

    inv_node = Node(
        package="mycobot_kitchen_nodes", 
        executable="inventory_manager",
        name="inventory_manager_node",
        output="screen",
        parameters=[{"table_name": LaunchConfiguration("inv_table")}],
    )

    return LaunchDescription([
        *env,
        bias_provider,
        arm_driver,
        recipe_executor,
        refill_executor,
        inv_table,
        inv_node,
    ])