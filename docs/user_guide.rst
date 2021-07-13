User Guide
==========

Introduction
------------

Virtualenv has one basic command:

.. code-block:: console

    virtualenv venv

This will create a python virtual environment of the same version as virtualenv, installed into the subdirectory
``venv``. The command line tool has quite a few of flags that modify the tool's behaviour, for a
full list make sure to check out :ref:`cli_flags`.

The tool works in two phases:

- **Phase 1** discovers a python interpreter to create a virtual environment from (by default this is the same python
  as the one ``virtualenv`` is running from, however we can change this via the :option:`p` option).
- **Phase 2** creates a virtual environment at the specified destination (:option:`dest`), this can be broken down into
  four further sub-steps:

  - create a python that matches the target python interpreter from phase 1,
  - install (bootstrap) seed packages (one or more of :pypi:`pip`, :pypi:`setuptools`, :pypi:`wheel`) in the created
    virtual environment,
  - install activation scripts into the binary directory of the virtual environment (these will allow end users to
    *activate* the virtual environment from various shells).
  - create files that mark the virtual environment as to be ignored by version control systems (currently we support
    Git only, as Mercurial, Bazaar or SVN do not support ignore files in subdirectories). This step can be skipped
    with the :option:`no-vcs-ignore` option.


The python in your new virtualenv is effectively isolated from the python that was used to create it.

Python discovery
----------------

The first thing we need to be able to create a virtual environment is a python interpreter. This will describe to the
tool what type of virtual environment you would like to create, think of it as: version, architecture, implementation.

``virtualenv`` being a python application has always at least one such available, the one ``virtualenv`` itself is
using, and as such this is the default discovered element. This means that if you install ``virtualenv`` under
python ``3.8``, virtualenv will by default create virtual environments that are also of version ``3.8``.

Created python virtual environments are usually not self-contained. A complete python packaging is usually made up of
thousands of files, so it's not efficient to install the entire python again into a new folder. Instead virtual
environments are mere shells, that contain little within themselves, and borrow most from the system python (this is what
you installed, when you installed python itself). This does mean that if you upgrade your system python your virtual
environments *might* break, so watch out. The upside of this, referring to the system python, is that creating virtual
environments can be fast.

Here we'll describe the built-in mechanism (note this can be extended though by plugins). The CLI flag :option:`p` or
:option:`python` allows you to specify a python specifier for what type of virtual environment you would like, the
format is either:

- a relative/absolute path to a Python interpreter,

- a specifier identifying the Python implementation, version, architecture in the following format:

    .. code-block::

       {python implementation name}{version}{architecture}

    We have the following restrictions:

    - the python implementation is all alphabetic characters (``python`` means any implementation, and if is missing it
      defaults to ``python``),
    - the version is a dot separated version number,
    - the architecture is either ``-64`` or ``-32`` (missing means ``any``).

    For example:

    - ``python3.8.1`` means any python implementation having the version ``3.8.1``,
    - ``3`` means any python implementation having the major version ``3``,
    - ``cpython3`` means a ``CPython`` implementation having the version ``3``,
    - ``pypy2`` means a python interpreter with the ``PyPy`` implementation and major version ``2``.

  Given the specifier ``virtualenv`` will apply the following strategy to discover/find the system executable:

   - If we're on Windows look into the Windows registry, and check if we see any registered Python implementations that
     match the specification. This is in line with expectation laid out inside
     `PEP-514 <https://www.python.org/dev/peps/pep-0514/>`_
   - Try to discover a matching python executable within the folders enumerated on the ``PATH`` environment variable.
     In this case we'll try to find an executable that has a name roughly similar to the specification (for exact logic,
     please see the implementation code).

.. warning::

   As detailed above, virtual environments usually just borrow things from the system Python, they don't actually contain
   all the data from the system Python. The version of the python executable is hardcoded within the python exe itself.
   Therefore, if you upgrade your system Python, your virtual environment will still report the version before the
   upgrade, even though now other than the executable all additional content (standard library, binary libs, etc) are
   of the new version.

   Barring any major incompatibilities (rarely the case) the virtual environment will continue working, but other than
   the content embedded within the python executable it will behave like the upgraded version. If such a virtual
   environment python is specified as the target python interpreter, we will create virtual environments that match the
   new system Python version, not the version reported by the virtual environment.

Creators
--------

These are what actually setup the virtual environment, usually as a reference against the system python. virtualenv
at the moment has two types of virtual environments:

- ``venv`` - this delegates the creation process towards the ``venv`` module, as described in
  `PEP 405 <https://www.python.org/dev/peps/pep-0405>`_. This is only available on Python interpreters having version
  ``3.5`` or later, and also has the downside that virtualenv **must** create a process to invoke that module (unless
  virtualenv is installed in the system python), which can be an expensive operation (especially true on Windows).

- ``builtin`` - this means ``virtualenv`` is able to do the creation operation itself (by knowing exactly what files to
  create and what system files need to be referenced). The creator with name ``builtin`` is an alias on the first
  creator that's of this type (we provide creators for various target environments, that all differ in actual create
  operations, such as CPython 2 on Windows, PyPy2 on Windows, CPython3 on Posix, PyPy3 on Posix, and so on; for a full
  list see :option:`creator`).

Seeders
-------
These will install for you some seed packages (one or more of: :pypi:`pip`, :pypi:`setuptools`, :pypi:`wheel`) that
enables you to install additional python packages into the created virtual environment (by invoking pip). There are two
main seed mechanism available:

- ``pip`` - this method uses the bundled pip with virtualenv to install the seed packages (note, a new child process
  needs to be created to do this, which can be expensive especially on Windows).
- ``app-data`` - this method uses the user application data directory to create install images. These images are needed
  to be created only once, and subsequent virtual environments can just link/copy those images into their pure python
  library path (the ``site-packages`` folder). This allows all but the first virtual environment creation to be blazing
  fast (a ``pip`` mechanism takes usually 98% of the virtualenv creation time, so by creating this install image that
  we can just link into the virtual environments install directory we can achieve speedups of shaving the initial
  1 minute and 10 seconds down to just 8 seconds in case of a copy, or ``0.8`` seconds in case symlinks are available -
  this is on Windows, Linux/macOS with symlinks this can be as low as ``100ms`` from 3+ seconds).
  To override the filesystem location of the seed cache, one can use the
  ``VIRTUALENV_OVERRIDE_APP_DATA`` environment variable.

.. _wheels:

Wheels
~~~~~~

To install a seed package via either ``pip`` or ``app-data`` method virtualenv needs to acquire a wheel of the target
package. These wheels may be acquired from multiple locations as follows:

- ``virtualenv`` ships out of box with a set of embed ``wheels`` for all three seed packages (:pypi:`pip`,
  :pypi:`setuptools`, :pypi:`wheel`). These are packaged together with the virtualenv source files, and only change upon
  upgrading virtualenv. Different Python versions require different versions of these, and because virtualenv supports a
  wide range of Python versions, the number of embedded wheels out of box is greater than 3. Whenever newer versions of
  these embedded packages are released upstream ``virtualenv`` project upgrades them, and does a new release. Therefore,
  upgrading virtualenv periodically will also upgrade the version of the seed packages.
- However, end users might not be able to upgrade virtualenv at the same speed as we do new releases. Therefore, a user
  might request to upgrade the list of embedded wheels by invoking virtualenv with the :option:`upgrade-embed-wheels`
  flag. If the operation is triggered in such a manual way subsequent runs of virtualenv will always use the upgraded
  embed wheels.

  The operation can trigger automatically too, as a background process upon invocation of virtualenv, if no such upgrade
  has been performed in the last 14 days. It will only start using automatically upgraded wheel if they have been
  released for more than 28 days, and the automatic upgrade finished at least an hour ago:

  - the 28 days period should guarantee end users are not pulling in automatically releases that have known bugs within,
  - the one hour period after the automatic upgrade finished is implemented so that continuous integration services do
    not start using a new embedded versions half way through.


  The automatic behaviour might be disabled via the :option:`no-periodic-update` configuration flag/option. To acquire
  the release date of a package virtualenv will perform the following:

  - lookup ``https://pypi.org/pypi/<distribution>/json`` (primary truth source),
  - save the date the version was first discovered, and wait until 28 days passed.
- Users can specify a set of local paths containing additional wheels by using the :option:`extra-search-dir` command
  line argument flag.

When searching for a wheel to use virtualenv performs lookup in the following order:

- embedded wheels,
- upgraded embedded wheels,
- extra search dir.

Bundled wheels are all three above together. If neither of the locations contain the requested wheel version or
:option:`download` option is set will use ``pip`` download to load the latest version available from the index server.

.. _distribution_wheels:

Embed wheels for distributions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Custom distributions often want to use their own set of wheel versions to distribute instead of the one virtualenv
releases on PyPi. The reason for this is trying to keep the system versions of those packages in sync with what
virtualenv uses. In such cases they should patch the module `virtualenv.seed.wheels.embed
<https://github.com/pypa/virtualenv/tree/main/src/virtualenv/seed/wheels/embed>`_, making sure to provide the function
``get_embed_wheel`` (which returns the wheel to use given a distribution/python version). The ``BUNDLE_FOLDER``,
``BUNDLE_SUPPORT`` and ``MAX`` variables are needed if they want to use virtualenv's test suite to validate.

Furthermore, they might want to disable the periodic update by patching the
`virtualenv.seed.embed.base_embed.PERIODIC_UPDATE_ON_BY_DEFAULT
<https://github.com/pypa/virtualenv/tree/main/src/virtualenv/seed/embed/base_embed.py>`_
to ``False``, and letting the system update mechanism to handle this. Note in this case the user might still request an
upgrade of the embedded wheels by invoking virtualenv via :option:`upgrade-embed-wheels`, but no longer happens
automatically, and will not alter the OS provided wheels.

Activators
----------
These are activation scripts that will mangle with your shell's settings to ensure that commands from within the python
virtual environment take priority over your system paths. For example, if invoking ``pip`` from your shell returned the
system python's pip before activation, once you do the activation this should refer to the virtual environments ``pip``.
Note, though that all we do is change priority; so, if your virtual environments ``bin``/``Scripts`` folder does not
contain some executable, this will still resolve to the same executable it would have resolved before the activation.

For a list of shells we provide activators see :option:`activators`. The location of these is right alongside the python
executables ( usually ``Scripts`` folder on Windows, ``bin`` on POSIX), and are named as ``activate`` (and some
extension that's specific per activator; no extension is bash). You can invoke them, usually by source-ing (the source
command might vary by shell - e.g. bash is ``.``):

.. code-block:: console

   source bin/activate

This is all it does; it's purely a convenience of prepending the virtual environment's binary folder onto the ``PATH``
environment variable. Note you don't have to activate a virtual environment to use it. In this case though you would
need to type out the path to the executables, rather than relying on your shell to resolve them to your virtual
environment.

The ``activate`` script will also modify your shell prompt to indicate which environment is currently active. The script
also provisions a ``deactivate`` command that will allow you to undo the operation:

.. code-block:: console

   deactivate


.. note::

    If using Powershell, the ``activate`` script is subject to the
    `execution policies <http://technet.microsoft.com/en-us/library/dd347641.aspx>`_ on the system. By default, Windows
    7 and later, the system's execution policy is set to ``Restricted``, meaning no scripts like the ``activate`` script
    are allowed to be executed.

    However, that can't stop us from changing that slightly to allow it to be executed. You may relax the system
    execution policy to allow running of local scripts without verifying the code signature using the following:

    .. code-block:: powershell

       Set-ExecutionPolicy RemoteSigned

    Since the ``activate.ps1`` script is generated locally for each virtualenv, it is not considered a remote script and
    can then be executed.

A longer explanation of this can be found within Allison Kaptur's 2013 blog post: `There's no magic: virtualenv
edition <https://www.recurse.com/blog/14-there-is-no-magic-virtualenv-edition>`_ explains how virtualenv uses bash and
Python and ``PATH`` and ``PYTHONHOME`` to isolate virtual environments' paths.

.. _programmatic_api:

Programmatic API
----------------

At the moment ``virtualenv`` offers only CLI level interface. If you want to trigger invocation of Python environments
from within Python you should be using the ``virtualenv.cli_run`` method; this takes an ``args`` argument where you can
pass the options the same way you would from the command line. The run will return a session object containing data
about the created virtual environment.

.. code-block:: python

   from virtualenv import cli_run

   cli_run(["venv"])

.. automodule:: virtualenv
   :members:

.. currentmodule:: virtualenv.run.session

.. autoclass:: Session
    :members:
