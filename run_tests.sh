#!/bin/bash
# Kitchmatics FMS Test Runner Script
#
# Usage:
#   ./run_tests.sh                    # Run all tests
#   ./run_tests.sh unit               # Run unit tests only
#   ./run_tests.sh integration        # Run integration tests only
#   ./run_tests.sh e2e                # Run E2E tests only
#   ./run_tests.sh coverage           # Run with coverage report
#   ./run_tests.sh <test_file>        # Run specific test file

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install with: pip install pytest pytest-cov"
    exit 1
fi

# Function to print header
print_header() {
    echo -e "\n${GREEN}================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}================================${NC}\n"
}

# Function to print info
print_info() {
    echo -e "${YELLOW}$1${NC}"
}

# Default: run all tests
test_type=${1:-all}

case $test_type in
    unit)
        print_header "Running Unit Tests"
        pytest tests/ -m unit -v --tb=short
        ;;
    integration)
        print_header "Running Integration Tests"
        pytest tests/ -m integration -v --tb=short
        ;;
    e2e)
        print_header "Running E2E Tests with Skip Mode"
        pytest tests/ -m e2e -v --tb=short
        ;;
    coverage)
        print_header "Running Tests with Coverage Report"
        if ! python3 -c "import pytest_cov" 2>/dev/null; then
            print_info "Installing pytest-cov..."
            pip install pytest-cov
        fi
        pytest tests/ --cov=fms --cov-report=term-missing --cov-report=html -v --tb=short
        print_info "Coverage report generated: htmlcov/index.html"
        ;;
    all)
        print_header "Running All Tests"
        pytest tests/ -v --tb=short
        ;;
    *)
        # If argument is a file, run it
        if [[ -f "tests/$test_type" ]] || [[ -f "$test_type" ]]; then
            print_header "Running: $test_type"
            pytest "$test_type" -v --tb=short
        else
            # Try as test class or function
            print_header "Running Tests Matching: $test_type"
            pytest tests/ -k "$test_type" -v --tb=short
        fi
        ;;
esac

# Print summary
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}Test Execution Complete${NC}"
echo -e "${GREEN}================================${NC}\n"
