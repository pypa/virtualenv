import os.path

import pytest


@pytest.yield_fixture
def tmpdir(request, tmpdir):
    try:
        yield tmpdir
    finally:
        tmpdir.remove(ignore_errors=True)


def pytest_collection_modifyitems(items):
    for item in items:
        module_path = os.path.relpath(
            item.module.__file__,
            os.path.commonprefix([__file__, item.module.__file__]),
        )

        module_root_dir = module_path.split(os.sep)[0]
        if module_root_dir == "functional":
            item.add_marker(pytest.mark.functional)
        elif module_root_dir == "unit":
            item.add_marker(pytest.mark.unit)
        else:
            raise RuntimeError(
                "Unknown test type (filename = {0})".format(module_path)
            )
