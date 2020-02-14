from setuptools import __version__, setup

if int(__version__.split(".")[0]) < 42:
    raise RuntimeError("setuptools >= 42 required to build")

setup(
    use_scm_version={"write_to": "src/virtualenv/version.py", "write_to_template": '__version__ = "{version}"'},
    setup_requires=["setuptools_scm >= 2"],
)
