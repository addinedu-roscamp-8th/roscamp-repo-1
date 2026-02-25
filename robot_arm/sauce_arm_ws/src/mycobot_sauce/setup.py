from setuptools import find_packages, setup
import os
from glob import glob

package_name = "mycobot_sauce"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "config"), glob("config/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="jetcobot",
    maintainer_email="jetcobot@todo.todo",
    description="TODO: Package description",
    license="TODO: License declaration",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "arm_driver = mycobot_sauce.arm_driver_node:main",
            "bias_provider = mycobot_sauce.bias_provider_node:main",
            "pour_sauce = mycobot_sauce.pour_sauce_node:main",
            'trash_or_delivery = mycobot_sauce.trash_or_delivery_node:main',
        ],
    },
)
