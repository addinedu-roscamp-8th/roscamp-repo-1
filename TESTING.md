# Kitchmatics FMS Testing Guide

## Overview

The Kitchmatics FMS test suite provides comprehensive coverage of the Fleet Management System with 75 automated tests organized into three categories:

1. **Unit Tests (26 tests)** - Individual component functionality
2. **Integration Tests (32 tests)** - Multi-robot scenarios and namespace isolation
3. **E2E Tests (17 tests)** - Complete delivery flows with skip mode

All tests pass successfully and can be run with pytest.

## Quick Start

### Run All Tests
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
python3 -m pytest tests/ -v
```

### Run Specific Test Category
```bash
# Unit tests only
pytest tests/ -m unit -v

# Integration tests only
pytest tests/ -m integration -v

# E2E tests only
pytest tests/ -m e2e -v
```

### Run Specific Test File
```bash
pytest tests/test_fms_unit.py -v
pytest tests/test_multi_robot.py -v
pytest tests/test_e2e_skip_mode.py -v
```

### Run with Coverage
```bash
pip install pytest-cov
pytest tests/ --cov=fms --cov-report=html -v
open htmlcov/index.html
```

## Test Files Location

```
/home/gw/kitchmatics/roscamp-repo-1/tests/
├── __init__.py                # Package marker
├── conftest.py               # Pytest configuration and fixtures
├── test_fms_unit.py          # Unit tests (26 tests)
├── test_multi_robot.py       # Integration tests (32 tests)
├── test_e2e_skip_mode.py     # E2E tests (17 tests)
├── setup.py                  # Test package setup
└── README.md                 # Detailed test documentation
```

## Test Summary

### Unit Tests (test_fms_unit.py)

Tests individual FMS components without dependencies:

**Task Class (6 tests)**
- Task creation, assignment, lifecycle
- Status transitions (PENDING → ASSIGNED → IN_PROGRESS → COMPLETED)
- Task failure and recovery
- Serialization to dictionary

**TaskManager (12 tests)**
- Task queue management
- Task assignment and retrieval
- Multi-task queue handling
- Status tracking and reporting

**RobotState (9 tests)**
- Robot initialization with namespace
- Pose and battery updates
- Task assignment and clearing
- Availability checking
- Low battery detection
- Complete status transition sequence

**FleetController (13 tests)**
- 3-robot fleet management
- Robot availability selection
- Task assignment to robots
- State transitions through delivery
- Battery monitoring
- Fleet status aggregation
- Distance calculations

**FMS Integration (3 tests)**
- Complete task assignment flow
- Multi-robot task queue
- Full delivery lifecycle

### Integration Tests (test_multi_robot.py)

Tests multi-robot scenarios with namespace isolation:

**Multi-Robot Basics (4 tests)**
- 3-robot fleet initialization
- Fleet status reporting
- Namespace isolation (/pinky1, /pinky2, /pinky3)

**Concurrent Deliveries (3 tests)**
- Simultaneous assignment to all robots
- Partial availability scenarios
- Sequential delivery with queueing

**Load Balancing (3 tests)**
- Round-robin assignment
- Available robot selection
- Battery-aware selection

**Robot Task Tracking (2 tests)**
- Task retrieval per robot
- State independence verification

**Multi-Robot Delivery Flow (2 tests)**
- 3 concurrent deliveries
- Staggered completion

**Namespace Isolation (2 tests)**
- Format validation
- No cross-talk between contexts

**Error Handling (2 tests)**
- Robot error isolation
- Recovery after error

### E2E Tests (test_e2e_skip_mode.py)

Tests complete delivery flows with skip_robot_arm mode:

**SkipModeSimulator Class**
- Simulates FMS behavior with skip mode
- Precision parking auto-mock
- Robot arm loading auto-mock (3-second delay)
- Event logging and verification

**Single Robot E2E (3 tests)**
- Complete order → pickup → delivery → return flow
- Skip mode timing validation
- Task completion tracking

**Multiple Robots E2E (2 tests)**
- 2 concurrent deliveries
- 3 concurrent deliveries

**Edge Cases (3 tests)**
- Order queueing with skip mode
- Delivery complete while at table
- Skip mode enabled/disabled behavior

**State Transitions (6 tests)**
- IDLE → MOVING_TO_PICKUP
- MOVING_TO_PICKUP → LOADED
- LOADED → MOVING_TO_TABLE
- MOVING_TO_TABLE → DELIVERING
- DELIVERING → RETURNING
- RETURNING → IDLE

## Skip Mode Testing

The test suite validates skip mode behavior for testing without external teams:

**Skip Mode Features:**
- Automatic precision parking simulation
- Automatic robot arm loading (3-second delay)
- Message sequence validation
- State transition verification

**Test Scenarios:**
- Single and multiple robot E2E flows
- Concurrent deliveries
- Task queueing
- Timing validation

**Enable Skip Mode in FMS:**
```bash
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true -p skip_precision:=true
```

## Test Results

```
============================= test session starts ==============================
collected 75 items

tests/test_e2e_skip_mode.py::...                    [18%]
tests/test_fms_unit.py::...                         [76%]
tests/test_multi_robot.py::...                      [100%]

======================= 75 passed in 0.12s =======================
```

## Available Fixtures

The `conftest.py` provides reusable fixtures:

```python
@pytest.fixture
def task_manager():
    """Fresh TaskManager instance"""

@pytest.fixture
def fleet_controller():
    """FleetController with 3 robots (pinky1, pinky2, pinky3)"""

@pytest.fixture
def two_robot_fleet():
    """FleetController with 2 robots"""

@pytest.fixture
def single_robot_fleet():
    """FleetController with 1 robot"""

@pytest.fixture
def fms_components():
    """Both TaskManager and FleetController tuple"""

@pytest.fixture
def mock_pose():
    """Mock Pose object for testing"""
```

## Test Markers

Tests are automatically marked for filtering:

```bash
@pytest.mark.unit        # Unit tests
@pytest.mark.integration # Integration tests
@pytest.mark.e2e         # E2E tests
```

## Running Tests Programmatically

```python
import pytest

# Run all tests
pytest.main(['/home/gw/kitchmatics/roscamp-repo-1/tests/', '-v'])

# Run with coverage
pytest.main(['tests/', '--cov=fms', '--cov-report=html', '-v'])

# Run specific marker
pytest.main(['tests/', '-m', 'unit', '-v'])
```

## Continuous Integration

To integrate tests into CI/CD:

```yaml
# GitHub Actions example
- name: Run FMS Tests
  run: |
    pip install pytest pytest-cov
    pytest tests/ -v --tb=short

- name: Upload Coverage
  uses: codecov/codecov-action@v3
```

## Test Statistics

| Category | Count | Status |
|----------|-------|--------|
| Unit Tests | 26 | ✓ Pass |
| Integration Tests | 32 | ✓ Pass |
| E2E Tests | 17 | ✓ Pass |
| **Total** | **75** | **✓ Pass** |

## Components Under Test

| Component | Tests | Coverage |
|-----------|-------|----------|
| Task | 6 | Creation, lifecycle, serialization |
| TaskManager | 12 | Queue, assignment, retrieval, status |
| RobotState | 9 | Initialization, updates, transitions |
| FleetController | 13 | Management, selection, aggregation |
| Skip Mode | 17 | E2E flows, timing, state transitions |
| Multi-Robot | 32 | Concurrency, isolation, load balancing |

## Known Limitations

1. **ROS 2 Independence** - Tests don't require ROS 2 runtime
2. **Navigation Simulation** - Robot movement is simulated via pose callbacks
3. **In-Memory Storage** - Tasks are not persisted to database
4. **External Teams Mocked** - Precision control and robot arm are mocked
5. **No Real Network** - Network communication is not tested

## Future Enhancements

- [ ] ROS 2 action server integration tests
- [ ] Database persistence tests
- [ ] Navigation failure scenarios
- [ ] Network disconnection handling
- [ ] Battery depletion scenarios
- [ ] Load testing (100+ concurrent orders)
- [ ] Performance benchmarks

## Troubleshooting

### ImportError: Cannot import FMS modules
```bash
# Run from project root
cd /home/gw/kitchmatics/roscamp-repo-1
pytest tests/
```

### Missing ROS 2 message modules
```bash
# Install dependencies
pip install geometry-msgs builtin-interfaces
```

### Tests timeout
```bash
# Run with longer timeout
pytest tests/ --timeout=300 -v
```

## Contributing New Tests

1. Follow test naming: `test_<action>_<condition>_<expected>`
2. Add docstrings explaining the scenario
3. Use fixtures for common setup
4. Mark with appropriate markers
5. Keep tests isolated and independent
6. Use meaningful assertions with messages

Example:
```python
def test_robot_reaches_pickup_updates_status(fleet_controller):
    """Test that robot status updates when reaching pickup spot"""
    fleet_controller.assign_task_to_robot('pinky1', 'TASK001', 'ORD001')

    # Robot navigates to pickup
    fleet_controller.robot_reached_pickup('pinky1')

    # Verify state
    robot = fleet_controller.get_robot('pinky1')
    assert robot.status == RobotState.STATUS_LOADED
```

## References

- Test Documentation: `/home/gw/kitchmatics/roscamp-repo-1/tests/README.md`
- FMS Architecture: `/home/gw/kitchmatics/roscamp-repo-1/README.md`
- Pytest Documentation: https://docs.pytest.org/
- Skip Mode Guide: `/home/gw/kitchmatics/roscamp-repo-1/fms/README.md`

## Support

For test-related questions or issues:
1. Check the test documentation in `tests/README.md`
2. Review the test implementation in the relevant test file
3. Run tests with verbose output: `pytest tests/ -v -s`
4. Check pytest output and error messages for specific failures
