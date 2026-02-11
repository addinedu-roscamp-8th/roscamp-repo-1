from setuptools import find_packages, setup

package_name = 'mycobot_kitchen_nodes'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
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
        ],
    },
)


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
        "console_scripts": [
            "arm_driver = nodes.arm_driver_node:main",
            "bias_provider = nodes.bias_provider_node:main",
            "inventory_manager = nodes.inventory_manager_node:main",
            "recipe_executor = nodes.recipe_executor_node:main",
            "refill_executor = nodes.refill_executor_node:main",
        ],
    },
)
