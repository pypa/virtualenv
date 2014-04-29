import os
import re
import shutil
import sys

try:
    from setuptools import setup
    using_setuptools = True
except ImportError:
    from distutils.core import setup
    using_setuptools = False

if using_setuptools:
    from setuptools.command.test import test as TestCommand

    class PyTest(TestCommand):
        def finalize_options(self):
            TestCommand.finalize_options(self)
            self.test_args = []
            self.test_suite = True

        def run_tests(self):
            # import here, because outside the eggs aren't loaded
            import pytest
            errno = pytest.main(self.test_args)
            sys.exit(errno)

    setup_params = {
        'entry_points': {
            'console_scripts': [
                'virtualenv=virtualenv:main',
                'virtualenv-%s.%s=virtualenv:main' % sys.version_info[:2]
            ],
        },
        'zip_safe': False,
        'tests_require': ['pytest', 'Mock'],
        'cmdclass': {'test': PyTest},
    }
else:
    if sys.platform == 'win32':
        print('Note: without Setuptools installed you will'
              'have to use "python -m virtualenv ENV"')
        setup_params = {}
    else:
        script = 'scripts/virtualenv'
        script_ver = script + '-%s.%s' % sys.version_info[:2]
        shutil.copy(script, script_ver)
        setup_params = {'scripts': [script, script_ver]}


here = os.path.dirname(os.path.abspath(__file__))


def read_file(*paths):
    file_path = os.path.join(*([here] + list(paths)))
    f = open(file_path)
    contents = f.read().strip()
    f.close()

    return contents

index = read_file('docs', 'index.rst')
news = read_file('docs', 'news.rst')

long_description = index.split('split here', 1)[0] + '\n\n' + news


def get_version():
    version_file = read_file('virtualenv.py')
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
    name='virtualenv',
    version=get_version(),
    description="Virtual Python Environment builder",
    long_description=long_description,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.5',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.1',
        'Programming Language :: Python :: 3.2',
    ],
    keywords='setuptools deployment installation distutils',
    author='Ian Bicking',
    author_email='ianb@colorstudy.com',
    maintainer='Jannis Leidel, Carl Meyer and Brian Rosner',
    maintainer_email='python-virtualenv@groups.google.com',
    url='http://www.virtualenv.org',
    license='MIT',
    py_modules=['virtualenv'],
    packages=['virtualenv_support'],
    package_data={'virtualenv_support': ['*.whl']},
    **setup_params)
