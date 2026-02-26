from setuptools import setup
from glob import glob
import os

package_name = "mycobot_kitchen_nodes"

setup(
    name=package_name,
    version="0.0.1",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        # launch / config 설치
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer='jetcobot',
    maintainer_email='jetcobot@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
        extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'arm_driver = mycobot_kitchen_nodes.arm_driver_node:main',
            'bias_provider = mycobot_kitchen_nodes.bias_provider_node:main',
            'inventory_manager = mycobot_kitchen_nodes.inven_manager_node:main',
            'recipe_executor = mycobot_kitchen_nodes.recipe_executor_node:main',
            'refill_executor = mycobot_kitchen_nodes.refill_executor_node:main',
            'fms_command_interface = mycobot_kitchen_nodes.fms_command_interface_node:main',
            'cooking_interface = mycobot_kitchen_nodes.cooking_interface_node:main',
        ],
    },
)

