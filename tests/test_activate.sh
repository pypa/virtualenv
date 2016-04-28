#!/bin/sh
set -u
ROOT="$(dirname $0)/.."
VIRTUALENV="${ROOT}/virtualenv.py"
TESTENV="/tmp/test_virtualenv_activate.venv"

oneTimeSetUp(){
    rm -rf ${TESTENV}
    ${VIRTUALENV} ${TESTENV} | tee ${ROOT}/tests/test_activate_output.actual
    . ${TESTENV}/bin/activate
}

test_virtualenv_creation(){
    assertTrue "Failed to get expected output from ${VIRTUALENV}!" \
        "diff ${ROOT}/tests/test_activate_output.expected ${ROOT}/tests/test_activate_output.actual | grep '^>'"
}


test_value_of_VIRTUAL_ENV(){
    assertEquals "Expected \$VIRTUAL_ENV to be set to \"${TESTENV}\"; actual value: \"${VIRTUAL_ENV}\"!"\
        "${TESTENV}" "$VIRTUAL_ENV"
}


test_output_of_which_python(){
    assertEquals "Expected \$(which python) to return \"${TESTENV}/bin/python\"; actual value: \"$(which python)\"!"\
        "${TESTENV}/bin/python" "$(which python)"
}

test_output_of_which_pip(){
    assertEquals "Expected \$(which pip) to return \"${TESTENV}/bin/pip\"; actual value: \"$(which pip)\"!"\
        "${TESTENV}/bin/pip" "$(which pip)"
}

test_output_of_which_easy_install(){
    assertEquals "Expected \$(which easy_install) to return \"${TESTENV}/bin/easy_install\"; actual value: \"$(which easy_install)\"!"\
        "${TESTENV}/bin/easy_install" "$(which easy_install)"
}

test_simple_python_program(){
    TESTENV=${TESTENV} python <<__END__
import os, sys

expected_site_packages = os.path.join(os.environ['TESTENV'], 'lib','python%s' % sys.version[:3], 'site-packages')
site_packages = os.path.join(os.environ['VIRTUAL_ENV'], 'lib', 'python%s' % sys.version[:3], 'site-packages')

assert site_packages == expected_site_packages, 'site_packages did not have expected value; actual value: %r' % site_packages

open(os.path.join(site_packages, 'pydoc_test.py'), 'w').write('"""This is pydoc_test.py"""\n')
__END__

    assertEquals "Python script failed!" 0 "$?"
}

test_pydoc(){
    assertTrue "pydoc test failed!"\
        "PAGER=cat pydoc pydoc_test | grep 'This is pydoc_test.py'"
}

test_PATH_alteration(){
    assertFalse "'foobar' already in PATH, makes the test irrelevant, please modify alteration done to the PATH in $0 and relaunch the test" \
        "echo $PATH | grep 'foobar'"
    PATH="$PATH:foobar"
    assertTrue "echo $PATH | grep 'foobar'"

    deactivate

    assertTrue "PATH has been reseted!"\
        "echo $PATH | grep 'foobar'"

    . ${TESTENV}/bin/activate
}

oneTimeTearDown(){
    echo "Deactivating ${TESTENV}..." 1>&2
    deactivate
    echo "Deactivated ${TESTENV}." 1>&2
    rm -rf ${TESTENV}
}



# load shunit2
. ${ROOT}/tests/shunit2/src/shunit2
