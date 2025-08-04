#!/usr/bin/env bash

set -ex

# Clean up previous runs
rm -rf /tmp/venv-investigate /tmp/venv-investigate-2

# 0. Reset app data
python3.12 -m virtualenv --reset-app-data /tmp/dummy-for-reset

# 1. Create a virtual environment
python3.12 -m virtualenv /tmp/venv-investigate

# 2. Check TCL_LIBRARY before activation
echo "TCL_LIBRARY before activation: '${TCL_LIBRARY:-}'"

# 3. Activate
. /tmp/venv-investigate/bin/activate

# 4. Check TCL_LIBRARY after activation
echo "TCL_LIBRARY after activation: '${TCL_LIBRARY:-}'"

# 5. Deactivate
deactivate

# 6. Check TCL_LIBRARY after deactivation
echo "TCL_LIBRARY after deactivation: '${TCL_LIBRARY:-}'"

# 7. Reset app data again
python3.12 -m virtualenv --reset-app-data /tmp/dummy-for-reset-2

# 8. Run virtualenv again and check TCL_LIBRARY in replacements
python3.12 -m virtualenv --verbose /tmp/venv-investigate-2

#9. Check TCL_LIBRARY after second virtualenv creation
echo "TCL_LIBRARY after second virtualenv creation: '${TCL_LIBRARY:-}'"