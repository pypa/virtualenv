from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(name='virtualenv',
      version=version,
      description="Virtual Python Environment builder",
      long_description="""\
""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='Ian Bicking',
      author_email='ianb@colorstudy.com',
      url='',
      license='MIT',
      modules=['virtualenv'],
      include_package_data=True,
      zip_safe=False,
      entry_points="""
      [console_scripts]
      virtualenv = virtualenv:main
      """,
      )
