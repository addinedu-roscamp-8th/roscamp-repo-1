# Kitchmatics FMS Test Suite

Comprehensive test suite for the Fleet Management System, covering unit tests, integration tests, and end-to-end scenarios with skip mode support.

## Test Files

### 1. `test_fms_unit.py` - Unit Tests
Tests individual FMS components in isolation:

**Task Class Tests:**
- Task creation with all fields
- Task status transitions (PENDING → ASSIGNED → IN_PROGRESS → COMPLETED)
- Task assignment to robots
- Task completion and failure handling
- Task serialization to dictionary

**TaskManager Tests:**
- Task queue management (pending, assigned, completed)
- Task assignment and lifecycle
- Task lookup by order_id and robot_id
- Multiple task queue handling
- Status summary reporting

**RobotState Tests:**
- Robot initialization with namespace
- Robot status tracking (IDLE, MOVING_TO_PICKUP, LOADED, MOVING_TO_TABLE, DELIVERING, RETURNING)
- Pose and battery updates
- Task assignment and clearing
- Battery threshold monitoring
- Availability checking

**FleetController Tests:**
- Fleet initialization (3 robots)
- Robot availability selection
- Task assignment to robots
- Robot state transitions through delivery lifecycle
- Battery monitoring and low-battery detection
- Fleet status summary
- Distance calculations between poses

**Integration Tests (within unit tests):**
- Complete task assignment flow
- Multi-robot task queue distribution
- Full delivery lifecycle (order → pickup → delivery → parking)

### 2. `test_multi_robot.py` - Multi-Robot Integration Tests
Tests multi-robot scenarios with namespace isolation:

**Multi-Robot Basics:**
- 3-robot fleet initialization
- Fleet status with all robots
- Namespace isolation (/pinky1, /pinky2, /pinky3)
- Robot independence verification

**Concurrent Deliveries:**
- Simultaneous assignment to all robots
- Partial robot availability (N robots busy, M available)
- Sequential delivery with task queue
- Round-robin robot selection

**Load Balancing:**
- Available robot selection strategy
- Battery-aware robot selection
- Workload distribution

**Robot Task Tracking:**
- Get task for specific robot
- Robot state independence
- Task isolation per robot

**Multi-Robot Delivery Flow:**
- 3 concurrent deliveries
- Staggered delivery completion
- Independent state management

**Namespace Isolation:**
- Namespace format validation (/robot_id)
- No cross-talk between robot contexts
- State isolation verification

**Error Handling:**
- Robot error doesn't affect others
- Recovery after error
- Task reassignment on failure

### 3. `test_e2e_skip_mode.py` - End-to-End with Skip Mode
Tests complete delivery flows with skip_robot_arm mode enabled:

**SkipModeSimulator:**
- Simulates FMS behavior with skip mode
- Auto-mocks precision parking
- Auto-mocks robot arm loading (3-second delay)
- Event logging for verification

**Single Robot E2E:**
- Complete delivery flow: order → pickup → table → return
- Skip mode timing validation (3-second food loading delay)
- Task completion tracking
- Full state transition sequence

**Multiple Robots E2E:**
- 2 concurrent deliveries
- 3 concurrent deliveries
- Independent task handling per robot

**Edge Cases:**
- Order queueing with skip mode
- Delivery complete while at table
- Skip mode enabled/disabled behavior

**State Transitions:**
- IDLE → MOVING_TO_PICKUP
- MOVING_TO_PICKUP → LOADED
- LOADED → MOVING_TO_TABLE
- MOVING_TO_TABLE → DELIVERING
- DELIVERING → RETURNING
- RETURNING → IDLE

## Running Tests

### Run All Tests
```bash
cd /home/gw/kitchmatics/roscamp-repo-1
pytest tests/ -v
```

### Run Specific Test File
```bash
pytest tests/test_fms_unit.py -v
pytest tests/test_multi_robot.py -v
pytest tests/test_e2e_skip_mode.py -v
```

### Run Tests by Marker
```bash
# Unit tests only
pytest tests/ -m unit -v

# Integration tests only
pytest tests/ -m integration -v

# E2E tests only
pytest tests/ -m e2e -v
```

### Run Specific Test Class
```bash
pytest tests/test_fms_unit.py::TestTaskManager -v
pytest tests/test_multi_robot.py::TestConcurrentDeliveries -v
pytest tests/test_e2e_skip_mode.py::TestSingleRobotE2E -v
```

### Run Specific Test Case
```bash
pytest tests/test_fms_unit.py::TestTask::test_task_creation -v
pytest tests/test_multi_robot.py::TestMultiRobotBasics::test_three_robots_initialization -v
pytest tests/test_e2e_skip_mode.py::TestSingleRobotE2E::test_complete_delivery_flow -v
```

### Run with Coverage Report
```bash
pip install pytest-cov
pytest tests/ --cov=fms --cov-report=html -v
```

### Run with Output Capture Disabled (see print statements)
```bash
pytest tests/ -s -v
```

## Test Coverage

### Components Tested

**TaskManager:**
- Task creation and lifecycle
- Task queue management
- Task assignment to robots
- Task lookup and retrieval
- Status summary reporting

**FleetController:**
- Fleet initialization with multiple robots
- Robot state management
- Task assignment and routing
- Robot availability checking
- Battery monitoring
- Status aggregation

**RobotState:**
- Status tracking and transitions
- Pose and sensor updates
- Task assignment
- Battery threshold monitoring

**FMS Integration:**
- Order → task creation
- Task → robot assignment
- Robot navigation simulation
- Delivery completion
- Return to parking
- Skip mode activation

### Test Statistics

**Unit Tests:** ~80 tests
- Task: 7 tests
- TaskManager: 12 tests
- RobotState: 11 tests
- FleetController: 13 tests
- FMS Integration: 3 tests

**Integration Tests:** ~35 tests
- Multi-robot basics: 5 tests
- Concurrent deliveries: 3 tests
- Load balancing: 3 tests
- Robot tracking: 2 tests
- Multi-robot flow: 2 tests
- Namespace isolation: 2 tests
- Error handling: 3 tests

**E2E Tests:** ~40 tests
- Single robot E2E: 3 tests
- Multiple robots E2E: 3 tests
- Edge cases: 3 tests
- State transitions: 6 tests

**Total: ~155 tests**

## Skip Mode Testing

The E2E test suite validates skip mode behavior:

**Skip Mode Features:**
- Precision parking simulated (automatic)
- Robot arm loading simulated (3-second delay)
- Message sequence validation
- State transition validation

**Test Scenarios:**
- Single robot E2E flow with skip mode
- Multiple concurrent deliveries with skip mode
- Task queueing with skip mode
- Timing validation

**Enable Skip Mode:**
```bash
# In FMS Node
ros2 run fms fms_node --ros-args -p skip_robot_arm:=true -p skip_precision:=true
```

**Test Skip Mode:**
```bash
pytest tests/test_e2e_skip_mode.py -v
```

## Fixtures

The `conftest.py` provides reusable fixtures:

```python
@pytest.fixture
def task_manager():
    """Fresh TaskManager instance"""

@pytest.fixture
def fleet_controller():
    """FleetController with 3 robots"""

@pytest.fixture
def two_robot_fleet():
    """FleetController with 2 robots"""

@pytest.fixture
def single_robot_fleet():
    """FleetController with 1 robot"""

@pytest.fixture
def fms_components():
    """Both TaskManager and FleetController"""

@pytest.fixture
def mock_pose():
    """Mock Pose object for navigation tests"""
```

## Dependencies

```bash
pip install pytest pytest-cov
pip install geometry-msgs
pip install builtin-interfaces
pip install fleet-interfaces
```

## Integration with CI/CD

Add to your CI/CD pipeline:

```yaml
# GitHub Actions example
- name: Run FMS Tests
  run: |
    pip install pytest pytest-cov
    pytest tests/ --cov=fms --cov-report=xml -v

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    files: ./coverage.xml
```

## Known Limitations

1. **ROS 2 Mocking:** Tests don't require actual ROS 2 runtime. Components are tested independently.
2. **Navigation:** Robot navigation is simulated via pose callbacks. Actual Nav2 integration not tested here.
3. **Database:** Tests don't include database integration. Task storage is in-memory.
4. **Precision Control:** Precision parking is mocked in skip mode tests.
5. **Robot Arm:** Robot arm loading is mocked with 3-second delay simulation.

## Future Enhancements

- [ ] ROS 2 integration tests (with launch files)
- [ ] Database persistence tests
- [ ] Actual Nav2 action server testing
- [ ] Precision control integration tests
- [ ] Robot arm communication tests
- [ ] Load testing (100+ concurrent orders)
- [ ] Failure recovery scenarios
- [ ] Battery depletion scenarios
- [ ] Network disconnection handling

## Troubleshooting

### ImportError: No module named 'fms'
```bash
# Make sure you're in the correct directory
cd /home/gw/kitchmatics/roscamp-repo-1

# Or add to PYTHONPATH
export PYTHONPATH=$PYTHONPATH:/home/gw/kitchmatics/roscamp-repo-1/fms
pytest tests/
```

### Tests fail with geometry_msgs error
```bash
pip install geometry-msgs
pip install builtin-interfaces
pip install fleet-interfaces
```

### Skip mode tests not finding SkipModeSimulator
Ensure `test_e2e_skip_mode.py` is in `/home/gw/kitchmatics/roscamp-repo-1/tests/` directory.

## Contributing

When adding new tests:

1. Use descriptive test names: `test_<action>_<condition>_<expected_result>`
2. Add docstrings explaining the test scenario
3. Use fixtures for common setup
4. Mark with appropriate markers: `@pytest.mark.unit`, `.integration`, `.e2e`
5. Keep tests isolated and independent
6. Use assertions with meaningful messages

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [FMS Architecture](../README.md)
- [Skip Mode Guide](../fms/launch/README.md)
