#!/bin/bash
# Script to install dependencies for performance testing

echo "Installing dependencies for ZVision performance testing..."

# Get the project root directory (two directories up from this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
echo "Project root: ${PROJECT_ROOT}"

# Change to project root
cd "${PROJECT_ROOT}"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Activated virtual environment"
fi

# Install required packages
pip install psutil requests

echo "Dependencies installed successfully!"
echo "You can now run the performance tests with: python tests/performance/test_performance.py" 