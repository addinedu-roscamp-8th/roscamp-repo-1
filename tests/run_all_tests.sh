#!/bin/bash
#
# Kitchmatics FMS - Complete Test Suite Runner
#
# This script runs all tests for the FMS system.
# Tests are organized by type: unit, integration, e2e
#
# Usage:
#   ./run_all_tests.sh          # Run all tests
#   ./run_all_tests.sh unit     # Run only unit tests
#   ./run_all_tests.sh int      # Run only integration tests
#   ./run_all_tests.sh e2e      # Run only e2e tests
#   ./run_all_tests.sh tcp      # Run TCP communication tests
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT"

# Print header
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Kitchmatics FMS - Test Suite${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo "Project Root: $PROJECT_ROOT"
echo "Python: $(which python3)"
echo "Date: $(date)"
echo ""

# Check for pytest
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Install with: pip3 install pytest"
    exit 1
fi

# Initialize counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run tests and track results
run_test_suite() {
    local suite_name="$1"
    local test_path="$2"
    local test_args="${3:-}"

    echo -e "\n${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Running: $suite_name${NC}"
    echo -e "${YELLOW}========================================${NC}"

    if [ -f "$test_path" ] || [ -d "$test_path" ]; then
        if python3 -m pytest "$test_path" $test_args -v --tb=short 2>&1; then
            echo -e "${GREEN}$suite_name: PASSED${NC}"
            ((PASSED_TESTS++))
        else
            echo -e "${RED}$suite_name: FAILED${NC}"
            ((FAILED_TESTS++))
        fi
        ((TOTAL_TESTS++))
    else
        echo -e "${YELLOW}Skipping: $test_path (not found)${NC}"
    fi
}

# Function to run Python script tests
run_script_test() {
    local suite_name="$1"
    local script_path="$2"

    echo -e "\n${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Running: $suite_name${NC}"
    echo -e "${YELLOW}========================================${NC}"

    if [ -f "$script_path" ]; then
        if python3 "$script_path" 2>&1; then
            echo -e "${GREEN}$suite_name: PASSED${NC}"
            ((PASSED_TESTS++))
        else
            echo -e "${RED}$suite_name: FAILED${NC}"
            ((FAILED_TESTS++))
        fi
        ((TOTAL_TESTS++))
    else
        echo -e "${YELLOW}Skipping: $script_path (not found)${NC}"
    fi
}

# Parse command line argument
TEST_TYPE="${1:-all}"

case "$TEST_TYPE" in
    "unit")
        echo -e "${BLUE}Running Unit Tests Only${NC}"
        run_test_suite "FMS Unit Tests" "tests/test_fms_unit.py"
        run_test_suite "Zone Manager Tests" "fms/tests/test_zone_manager_reservation.py"
        run_test_suite "Collision Avoidance Tests" "fms/fms/tests/test_collision_avoidance.py"
        ;;

    "int"|"integration")
        echo -e "${BLUE}Running Integration Tests Only${NC}"
        run_test_suite "Multi-Robot Tests" "tests/test_multi_robot.py"
        run_test_suite "Requirements Integration" "tests/test_requirements_integration.py"
        run_script_test "Integration Scenarios" "fms/fms/test_integration_scenarios.py"
        ;;

    "e2e")
        echo -e "${BLUE}Running E2E Tests Only${NC}"
        run_test_suite "E2E Skip Mode Tests" "tests/test_e2e_skip_mode.py"
        ;;

    "tcp")
        echo -e "${BLUE}Running TCP Communication Tests Only${NC}"
        echo -e "${YELLOW}Note: FMS must be running for these tests${NC}"
        run_script_test "TCP Protocol Test" "test_tcp_protocol.py"
        run_script_test "FMS Communication Test" "test_fms_communication.py"
        run_script_test "TCP Communication Suite" "fms/scripts/test_tcp_communication.py"
        ;;

    "quick")
        echo -e "${BLUE}Running Quick Tests (Unit + Requirements)${NC}"
        run_test_suite "FMS Unit Tests" "tests/test_fms_unit.py"
        run_test_suite "Requirements Integration" "tests/test_requirements_integration.py"
        ;;

    "all")
        echo -e "${BLUE}Running All Tests${NC}"

        # Unit Tests
        echo -e "\n${BLUE}=== PHASE 1: Unit Tests ===${NC}"
        run_test_suite "FMS Unit Tests" "tests/test_fms_unit.py"
        run_test_suite "Zone Manager Tests" "fms/tests/test_zone_manager_reservation.py"
        run_test_suite "Collision Avoidance Tests" "fms/fms/tests/test_collision_avoidance.py"

        # Integration Tests
        echo -e "\n${BLUE}=== PHASE 2: Integration Tests ===${NC}"
        run_test_suite "Multi-Robot Tests" "tests/test_multi_robot.py"
        run_test_suite "Requirements Integration" "tests/test_requirements_integration.py"
        run_script_test "Integration Scenarios" "fms/fms/test_integration_scenarios.py"

        # E2E Tests
        echo -e "\n${BLUE}=== PHASE 3: E2E Tests ===${NC}"
        run_test_suite "E2E Skip Mode Tests" "tests/test_e2e_skip_mode.py"
        ;;

    *)
        echo "Usage: $0 [unit|int|e2e|tcp|quick|all]"
        echo ""
        echo "Options:"
        echo "  unit   - Run unit tests only"
        echo "  int    - Run integration tests only"
        echo "  e2e    - Run end-to-end tests only"
        echo "  tcp    - Run TCP communication tests (requires FMS running)"
        echo "  quick  - Run quick tests (unit + requirements)"
        echo "  all    - Run all tests (default)"
        exit 1
        ;;
esac

# Print summary
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}======================================${NC}"
echo -e "Total Test Suites: $TOTAL_TESTS"
echo -e "Passed: ${GREEN}$PASSED_TESTS${NC}"
echo -e "Failed: ${RED}$FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}All test suites passed!${NC}"
    exit 0
else
    echo -e "${RED}$FAILED_TESTS test suite(s) failed.${NC}"
    exit 1
fi
