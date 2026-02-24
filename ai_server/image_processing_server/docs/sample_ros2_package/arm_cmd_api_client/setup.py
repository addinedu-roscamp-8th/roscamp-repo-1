from setuptools import setup

package_name = 'arm_cmd_api_client'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='GueHoJung88',
    maintainer_email='emotionalmachine88@gmail.com',
    description='Calls /analyze/arm_cmd API and optionally verifies /verify/cmd topic',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'arm_cmd_api_client_node = arm_cmd_api_client.arm_cmd_api_client_node:main',
            'arm_cmd_echo_test = arm_cmd_api_client.arm_cmd_echo_test:main',
        ],
    },
)
