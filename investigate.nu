#!/usr/bin/env nu

# Clean up previous runs
rm -rf /tmp/venv-investigate /tmp/venv-investigate-2

# 1. Create a virtual environment
python3.12 -m virtualenv /tmp/venv-investigate

# 2. Check TCL_LIBRARY before activation
echo $"TCL_LIBRARY before activation: '($env | get -i TCL_LIBRARY)'"

# 3. Activate and check TCL_LIBRARY
nu -c "
overlay use /tmp/venv-investigate/bin/activate.nu
echo 'TCL_LIBRARY after activation: ($env | get -i TCL_LIBRARY)'
deactivate
echo 'TCL_LIBRARY after deactivation: ($env | get -i TCL_LIBRARY)'
"

# 4. Create another virtual environment
python3.12 -m virtualenv /tmp/venv-investigate2