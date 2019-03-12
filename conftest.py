from __future__ import absolute_import, unicode_literals


def pytest_addoption(parser):
    parser.addoption("--xonsh-prompt", action="store_true", help="Run (do not skip) xonsh prompt behavior tests")
