#!/bin/bash
set -e

# Setup environment for building and packaging the application
# Parameters:
# $1: Python version (e.g., 3.11)

PYTHON_VERSION=${1:-3.11}
export PATH=$HOME/.local/bin:$PATH

echo "Setting up environment with Python version: ${PYTHON_VERSION}"

sudo apt-get update
sudo apt-get install -y curl jq python${PYTHON_VERSION} pipx
sudo apt-get clean
pipx install poetry==1.8.*

echo "Environment setup complete"

