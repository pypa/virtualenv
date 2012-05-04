#!/bin/sh

if [ "$(basename $0)" != "roundup" ]; then
    exec $(dirname $0)/roundup $0
fi

ROOT="$(dirname $1)/../.."
VIRTUALENV="${ROOT}/virtualenv.py"
TESTENV="/tmp/test_virtualenv_activate.venv"

rm -rf ${TESTENV}


describe "virtualenv"

it_displays_usage() {
    usage=$(${ROOT}/virtualenv.py --help | head -n 1)
    test "$usage" = "Usage: virtualenv.py [OPTIONS] DEST_DIR"
}

it_creates_a_virtualenv() {
    output=$(${VIRTUALENV} ${TESTENV})
    expected_output=$(cat ${ROOT}/tests/test_activate_expected.output)
    test "$output" = "$expected_output"
}

it_sets_VIRTUAL_ENV() {
    source ${TESTENV}/bin/activate
    test "$VIRTUAL_ENV" = "$TESTENV"
}

it_creates_directories() {
    source ${TESTENV}/bin/activate
    test -d ${VIRTUAL_ENV}
    test -d ${VIRTUAL_ENV}/bin
    test -d ${VIRTUAL_ENV}/include
    test -d ${VIRTUAL_ENV}/lib
}

it_picks_up_right_python() {
    source ${TESTENV}/bin/activate
    test "$(which python)" = "${TESTENV}/bin/python"
}

it_picks_up_right_pip() {
    source ${TESTENV}/bin/activate
    test "$(which pip)" = "${TESTENV}/bin/pip"
}

it_picks_up_right_easy_install() {
    source ${TESTENV}/bin/activate
    test "$(which easy_install)" = "${TESTENV}/bin/easy_install"
}

it_populate_sys_executable_correctly() {
    source ${TESTENV}/bin/activate
    output=$(python -c "import sys; print(sys.executable)")
    test "$output" = "${TESTENV}/bin/python"
}

it_can_run_pydoc_on_a_module_in_the_virtualenv() {
    source ${TESTENV}/bin/activate

    TESTENV=${TESTENV} python <<__END__
import os, sys

expected_site_packages = os.path.join(os.environ['TESTENV'], 'lib','python%s' % sys.version[:3], 'site-packages')
site_packages = os.path.join(os.environ['VIRTUAL_ENV'], 'lib', 'python%s' % sys.version[:3], 'site-packages')

assert site_packages == expected_site_packages, 'site_packages did not have expected value; actual value: %r' % site_packages

open(os.path.join(site_packages, 'pydoc_test.py'), 'w').write('"""This is pydoc_test.py"""\n')
__END__

    [[ "$(pydoc pydoc_test)" == *"pydoc_test - This is pydoc_test.py"* ]]
}

it_creates_deactivate_function() {
    source ${TESTENV}/bin/activate
    test "$(type -t deactivate)" = "function"
}

it_can_deactivate() {
    source ${TESTENV}/bin/activate
    test "$VIRTUAL_ENV" = "$TESTENV"
    deactivate
    test "$VIRTUAL_ENV" = ""
}

