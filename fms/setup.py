from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'fms'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py') + glob('launch/*_launch.py')),
        ('share/' + package_name + '/maps', glob('maps/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Kitchmatic Team',
    maintainer_email='team@kitchmatic.com',
    description='Fleet Management System for Kitchmatic Serving Robots',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fms_node = fms.fms_node:main',
            'fms_tcp_node = fms.fms_tcp_node:main',
        ],
    },
)
