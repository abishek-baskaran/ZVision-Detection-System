#!/bin/bash
# Install test dependencies

# Check if pip is installed
if ! [ -x "$(command -v pip)" ]; then
  echo 'Error: pip is not installed.' >&2
  exit 1
fi

# Install test dependencies
echo "Installing test dependencies..."
pip install pytest pytest-cov pytest-mock mock psutil matplotlib numpy

echo "Dependencies installed successfully." 