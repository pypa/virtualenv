#!/usr/bin/env csh

# Clean up previous runs
rm -rf /tmp/venv-investigate /tmp/venv-investigate-2

# 1. Create a virtual environment
python3.12 -m virtualenv /tmp/venv-investigate

# 2. Check TCL_LIBRARY before activation
echo "TCL_LIBRARY before activation:"
if ( $?TCL_LIBRARY ) then
    echo $TCL_LIBRARY
else
    echo "not set"
endif

# 3. Activate
source /tmp/venv-investigate/bin/activate.csh

# 4. Check TCL_LIBRARY after activation
echo "TCL_LIBRARY after activation:"
if ( $?TCL_LIBRARY ) then
    echo $TCL_LIBRARY
else
    echo "not set"
endif

# 5. Deactivate
deactivate

# 6. Check TCL_LIBRARY after deactivation
echo "TCL_LIBRARY after deactivation:"
if ( $?TCL_LIBRARY ) then
    echo $TCL_LIBRARY
else
    echo "not set"
endif

# 7. Create another virtual environment
python3.12 -m virtualenv /tmp/venv-investigate2