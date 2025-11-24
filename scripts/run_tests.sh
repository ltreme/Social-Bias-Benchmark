#!/bin/bash
# Quick test script for Docker-based testing

set -e

echo "🧪 Social Bias Benchmark - Test Runner (Docker)"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Parse arguments
TEST_TYPE="${1:-all}"

case $TEST_TYPE in
    unit)
        print_status "Running Unit Tests in Docker..."
        docker compose -f docker-compose.test.yml run --rm test-runner \
            pytest apps/backend/tests/unit/ -v
        ;;
    
    integration)
        print_status "Running Integration Tests in Docker..."
        docker compose -f docker-compose.test.yml run --rm test-runner \
            pytest apps/backend/tests/integration/ -v
        ;;
    
    critical)
        print_status "Running Critical Tests (vor GPU-Run!)..."
        docker compose -f docker-compose.test.yml run --rm test-runner bash -c "
            echo '1️⃣  Testing Prompt Factory...' && \
            pytest apps/backend/tests/unit/benchmarking/test_prompt_factory.py -v && \
            echo '' && \
            echo '2️⃣  Testing PostProcessor...' && \
            pytest apps/backend/tests/unit/benchmarking/test_postprocessor_likert.py -v && \
            echo '' && \
            echo '3️⃣  Testing Resume Logic...' && \
            pytest apps/backend/tests/integration/test_resume_logic.py -v
        "
        ;;
    
    cov)
        print_status "Running Tests with Coverage..."
        docker compose -f docker-compose.test.yml run --rm test-runner \
            pytest apps/backend/tests/ --cov=apps/backend/src --cov-report=html --cov-report=term
        print_status "Coverage report generated in htmlcov/"
        ;;
    
    fast)
        print_status "Running Fast Tests (skip slow ones)..."
        docker compose -f docker-compose.test.yml run --rm test-runner \
            pytest apps/backend/tests/ -v -m "not slow"
        ;;
    
    shell)
        print_status "Opening shell in test container..."
        docker compose -f docker-compose.test.yml run --rm test-runner bash
        ;;
    
    clean)
        print_status "Cleaning up test containers..."
        docker compose -f docker-compose.test.yml down -v
        ;;
    
    all)
        print_status "Running All Tests in Docker..."
        docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from test-runner
        ;;
    
    *)
        echo "Usage: $0 {unit|integration|critical|cov|fast|shell|clean|all}"
        echo ""
        echo "Test types:"
        echo "  unit         - Run only unit tests (fast)"
        echo "  integration  - Run integration tests (with DB)"
        echo "  critical     - Run critical tests before GPU runs"
        echo "  cov          - Run tests with coverage report"
        echo "  fast         - Run fast tests (skip slow ones)"
        echo "  shell        - Open shell in test container"
        echo "  clean        - Remove test containers"
        echo "  all          - Run all tests (default)"
        echo ""
        echo "Examples:"
        echo "  $0 critical    # Before expensive GPU runs"
        echo "  $0 unit        # Quick feedback during development"
        echo "  $0 cov         # Check test coverage"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    print_status "Tests completed successfully! ✨"
else
    echo ""
    print_error "Tests failed! ❌"
    exit 1
fi
