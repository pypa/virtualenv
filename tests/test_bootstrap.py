import inspect

import virtualenv

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


def bootstrap():
    from os.path import join, exists
    from os import makedirs
    import subprocess

    def after_install(options, home_dir):
        etc = join(home_dir, "etc")
        if not exists(etc):
            makedirs(etc)
        subprocess.call([join(home_dir, "bin", "easy_install"), "BlogApplication"])
        subprocess.call([join(home_dir, "bin", "paster"), "make-config", "BlogApplication", join(etc, "blog.ini")])
        subprocess.call([join(home_dir, "bin", "paster"), "setup-app", join(etc, "blog.ini")])


def test_bootstrap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = virtualenv.create_bootstrap_script(inspect.getsource(bootstrap))
    (tmp_path / "blog-bootstrap.py").write(output)
    assert output
