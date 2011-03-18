import sys, os
try:
    from setuptools import setup
    kw = {'entry_points':
          """[console_scripts]\nvirtualenv = virtualenv:main\n""",
          'zip_safe': False}
except ImportError:
    from distutils.core import setup
    if sys.platform == 'win32':
        print('Note: without Setuptools installed you will have to use "python -m virtualenv ENV"')
        kw = {}
    else:
        kw = {'scripts': ['scripts/virtualenv']}
import re

here = os.path.dirname(os.path.abspath(__file__))

## Get long_description from index.txt:
f = open(os.path.join(here, 'docs', 'index.txt'))
long_description = f.read().strip()
long_description = long_description.split('split here', 1)[1]
f.close()
f = open(os.path.join(here, 'docs', 'news.txt'))
long_description += "\n\n" + f.read()
f.close()

setup(name='virtualenv',
      # If you change the version here, change it in virtualenv.py and 
      # docs/conf.py as well
      version="1.5.2.post1",
      description="Virtual Python Environment builder",
      long_description=long_description,
      classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
      ],
      keywords='setuptools deployment installation distutils',
      author='Ian Bicking',
      author_email='ianb@colorstudy.com',
      url='http://www.virtualenv.org',
      license='MIT',
      py_modules=['virtualenv'],
      packages=['virtualenv_support'],
      package_data={'virtualenv_support': ['*-py%s.egg' % sys.version[:3], '*.tar.gz']},
      **kw
      )
