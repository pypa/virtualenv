#!/usr/bin/env fish
set -x

# Clean up previous runs
rm -rf /tmp/venv-investigate /tmp/venv-investigate-2

# 1. Create a virtual environment
python3.12 -m virtualenv /tmp/venv-investigate

# 2. Check TCL_LIBRARY before activation
echo "TCL_LIBRARY before activation: '$TCL_LIBRARY'"

# 3. Activate
source /tmp/venv-investigate/bin/activate.fish

# 4. Check TCL_LIBRARY after activation
echo "TCL_LIBRARY after activation: '$TCL_LIBRARY'"

# 5. Deactivate
deactivate

# 6. Check TCL_LIBRARY after deactivation
echo "TCL_LIBRARY after deactivation: '$TCL_LIBRARY'"

# 7. Create another virtual environment
python3.12 -m virtualenv /tmp/venv-investigate2