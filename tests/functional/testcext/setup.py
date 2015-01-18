from setuptools import setup
from distutils.core import Extension


setup(
    name="test-cext",
    version="1.0",
    ext_modules=[Extension("test_cext", sources=["test_cext.c"])]
)
