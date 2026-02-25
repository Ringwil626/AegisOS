#!/bin/bash
# AegisOS Quick Start Script
# Usage: ./start.sh [--cli|--demo|--no-discord|--jung]

set -e

echo "======================================"
echo "AegisOS - Quick Start"
echo "======================================"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p data logs projects/default evolution/proposals evolution/staging

# Check environment variables
echo ""
echo "Environment Check:"
if [ -z "$MOONSHOT_API_KEY" ]; then
    echo "  ⚠️  MOONSHOT_API_KEY not set (will use mock AI)"
else
    echo "  ✓ MOONSHOT_API_KEY is set"
fi

if [ -z "$DISCORD_TOKEN" ]; then
    echo "  ⚠️  DISCORD_TOKEN not set (Discord bot disabled)"
else
    echo "  ✓ DISCORD_TOKEN is set"
fi

echo ""
echo "Starting AegisOS..."
echo "======================================"

# Run based on arguments
if [ "$1" == "--cli" ]; then
    echo "Mode: CLI (interactive)"
    python main.py --cli
elif [ "$1" == "--jung" ]; then
    echo "Mode: Jung Interface (persona + AegisOS)"
    python jung_interface.py
elif [ "$1" == "--demo" ]; then
    echo "Mode: Demo (with sample tasks)"
    if [ -z "$DISCORD_TOKEN" ]; then
        python main.py --demo --no-discord
    else
        python main.py --demo
    fi
elif [ "$1" == "--no-discord" ]; then
    echo "Mode: Main loop only (no Discord)"
    python main.py --no-discord
else
    if [ -z "$DISCORD_TOKEN" ]; then
        echo "Mode: Jung Interface (default, Discord token not set)"
        echo "Run with --cli for plain CLI, --jung for persona mode, or --no-discord for main loop only"
        echo ""
        python jung_interface.py
    else
        echo "Mode: Full (with Discord)"
        python main.py
    fi
fi
