import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'sandwich_coordinator'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),

        # launch 폴더 추가
        (os.path.join('share', package_name, 'launch'),
        glob('launch/*.launch.py')),

        # domain_bridge yaml 같이 설치하려면
        (os.path.join('share', package_name, 'config'),
        glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='addinedu',
    maintainer_email='addinedu@todo.todo',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
    'console_scripts': [
        'sandwich_coordinator = sandwich_coordinator.coordinator_node:main',
        ],
    },
)
