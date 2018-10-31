Installation
============

.. warning::

    We advise installing virtualenv-1.9 or greater. Prior to version 1.9, the
    pip included in virtualenv did not download from PyPI over SSL.

.. warning::

    When using pip to install virtualenv, we advise using pip 1.3 or greater.
    Prior to version 1.3, pip did not download from PyPI over SSL.

.. warning::

    We advise against using easy_install to install virtualenv when using
    setuptools < 0.9.7, because easy_install didn't download from PyPI over SSL
    and was broken in some subtle ways.

To install globally with ``pip`` (if you have pip 1.3 or greater installed globally):

::

 $ [sudo] pip install virtualenv

To install locally (to ~/bin and ~/lib) with ``pip`` (if you have pip 1.3 or greater installed globally):

::

 $ export PYTHONUSERBASE=$HOME
 $ pip install --user virtualenv

Note: This assumes you have $HOME/bin in your $PATH for later usage of virtualenv.

Or to get the latest unreleased dev version:

::

 $ [sudo] pip install https://github.com/pypa/virtualenv/tarball/master


To install version ``X.X.X`` globally from source:

::

 $ [sudo] pip install https://github.com/pypa/virtualenv/tarball/X.X.X

To *use* locally from source:

::

 $ curl --location --output virtualenv-X.X.X.tar.gz https://github.com/pypa/virtualenv/tarball/X.X.X
 $ tar xvfz virtualenv-X.X.X.tar.gz
 $ cd pypa-virtualenv-YYYYYY
 $ python virtualenv.py myVE

.. note::

    The ``virtualenv.py`` script is *not* supported if run without the
    necessary pip/setuptools/virtualenv distributions available locally. All
    of the installation methods above include a ``virtualenv_support``
    directory alongside ``virtualenv.py`` which contains a complete set of
    pip and setuptools distributions, and so are fully supported.
