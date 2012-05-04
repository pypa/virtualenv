#!/bin/sh

ROOT="$(dirname $0)/.."
VIRTUALENV="${ROOT}/virtualenv.py"
TESTENV="/tmp/test_virtualenv_activate.venv"

rm -rf ${TESTENV}

echo "$0: Creating virtualenv ${TESTENV}..." 1>&2

${VIRTUALENV} ${TESTENV} | tee ${ROOT}/tests/test_activate_actual.output
if ! diff ${ROOT}/tests/test_activate_expected.output ${ROOT}/tests/test_activate_actual.output; then
    echo "$0: Failed to get expected output from ${VIRTUALENV}!" 1>&2
    exit 1
fi

echo "$0: Created virtualenv ${TESTENV}." 1>&2

echo "$0: Activating ${TESTENV}..." 1>&2
source ${TESTENV}/bin/activate
echo "$0: Activated ${TESTENV}." 1>&2

if [ "$VIRTUAL_ENV" != "${TESTENV}" ]; then
    echo "$0: Expected \$VIRTUAL_ENV to be set to \"${TESTENV}\"; actual value: \"${VIRTUAL_ENV}\"!" 1>&2
    exit 2
fi

if [ "$(which python)" != "${TESTENV}/bin/python" ]; then
    echo "$0: Expected \$(which python) to return \"${TESTENV}/bin/python\"; actual value: \"$(which python)\"!" 1>&2
    exit 3
fi

if [ "$(which pip)" != "${TESTENV}/bin/pip" ]; then
    echo "$0: Expected \$(which pip) to return \"${TESTENV}/bin/pip\"; actual value: \"$(which pip)\"!" 1>&2
    exit 4
fi

if [ "$(which easy_install)" != "${TESTENV}/bin/easy_install" ]; then
    echo "$0: Expected \$(which easy_install) to return \"${TESTENV}/bin/easy_install\"; actual value: \"$(which easy_install)\"!" 1>&2
    exit 5
fi

TESTENV=${TESTENV} python <<__END__
import os, sys

expected_site_packages = os.path.join(os.environ['TESTENV'], 'lib','python%s' % sys.version[:3], 'site-packages')
site_packages = os.path.join(os.environ['VIRTUAL_ENV'], 'lib', 'python%s' % sys.version[:3], 'site-packages')

assert site_packages == expected_site_packages, 'site_packages did not have expected value; actual value: %r' % site_packages

open(os.path.join(site_packages, 'pydoc_test.py'), 'w').write('"""This is pydoc_test.py"""\n')
__END__

if [ $? -ne 0 ]; then
    echo "$0: Python script failed!" 1>&2
    exit 6
fi

echo "$0: Testing pydoc..." 1>&2

if ! PAGER=cat pydoc pydoc_test | grep 'This is pydoc_test.py' > /dev/null; then
    echo "$0: pydoc test failed!" 1>&2
    exit 7
fi

echo "$0: pydoc is OK." 1>&2

echo "$0: Deactivating ${TESTENV}..." 1>&2
deactivate
echo "$0: Deactivated ${TESTENV}." 1>&2
echo "$0: OK!" 1>&2

rm -rf ${TESTENV}

