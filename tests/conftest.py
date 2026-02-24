"""
Pytest Configuration and Fixtures for Kitchmatics FMS Tests

Provides:
- Common fixtures for task manager, fleet controller
- Test configuration
- Logging setup
"""

import pytest
import logging
import sys
import os

# Add FMS module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fms'))

from fms.task_manager import TaskManager
from fms.fleet_controller import FleetController


# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)


@pytest.fixture
def task_manager():
    """Provide a fresh TaskManager instance"""
    return TaskManager()


@pytest.fixture
def fleet_controller():
    """Provide a fresh FleetController with 3 robots"""
    robot_configs = [
        {'robot_id': 'pinky1', 'namespace': '/pinky1'},
        {'robot_id': 'pinky2', 'namespace': '/pinky2'},
        {'robot_id': 'pinky3', 'namespace': '/pinky3'}
    ]
    return FleetController(robot_configs)


@pytest.fixture
def two_robot_fleet():
    """Provide a FleetController with 2 robots"""
    robot_configs = [
        {'robot_id': 'pinky1', 'namespace': '/pinky1'},
        {'robot_id': 'pinky2', 'namespace': '/pinky2'}
    ]
    return FleetController(robot_configs)


@pytest.fixture
def single_robot_fleet():
    """Provide a FleetController with 1 robot"""
    robot_configs = [
        {'robot_id': 'pinky1', 'namespace': '/pinky1'}
    ]
    return FleetController(robot_configs)


@pytest.fixture
def fms_components():
    """Provide both TaskManager and FleetController"""
    manager = TaskManager()
    robot_configs = [
        {'robot_id': 'pinky1', 'namespace': '/pinky1'},
        {'robot_id': 'pinky2', 'namespace': '/pinky2'},
        {'robot_id': 'pinky3', 'namespace': '/pinky3'}
    ]
    fleet = FleetController(robot_configs)
    return {
        'task_manager': manager,
        'fleet_controller': fleet
    }


@pytest.fixture
def mock_pose():
    """Provide a mock Pose object"""
    from geometry_msgs.msg import Pose, Point, Quaternion

    pose = Pose()
    pose.position = Point(x=0.0, y=0.0, z=0.0)
    pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
    return pose


def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on their filename"""
    for item in items:
        if "test_fms_unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "test_multi_robot" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "test_e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
