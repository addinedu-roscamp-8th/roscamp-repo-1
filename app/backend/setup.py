from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'main_server'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*_launch.py')),
    ],
    install_requires=[
        'setuptools',
        'sqlalchemy>=1.4',
        'psycopg2-binary>=2.9',
    ],
    zip_safe=True,
    maintainer='Kitchmatic Team',
    maintainer_email='team@kitchmatic.com',
    description='Main Server for Kitchmatic Fleet Management System',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'main_server = main_server.main_server_node:main',
        ],
    },
)
