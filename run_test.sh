#!/bin/bash
# Run the prototype test. Usage: ./run_test.sh [number_of_tickets]
# Loads ANTHROPIC_API_KEY from .env if not already set.

if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "ERROR: ANTHROPIC_API_KEY is not set."
  echo "Copy .env.example to .env and add your key."
  exit 1
fi

venv/bin/python tests/test_prototype.py "${1:-5}"
