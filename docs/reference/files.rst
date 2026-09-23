#################
 Generated files
#################

Creating an environment writes files inside the destination folder and beside it. This page lists each one, what it
holds, and how to suppress it.

*******************************
 Inside the environment folder
*******************************

``pyvenv.cfg``
==============

Marks the folder as a virtual environment and points the interpreter at the Python it was built from, per `PEP 405
<https://peps.python.org/pep-0405/>`_. Deleting it breaks the environment.

.. code-block:: ini

    home = /usr/local/python-3.14/bin
    implementation = CPython
    python-version = 3.14
    version_info = 3.14.6.final.0
    version = 3.14.6
    executable = /usr/local/python-3.14/bin/python3.14
    command = /usr/bin/python3 -m virtualenv /home/user/env
    virtualenv = 21.7.6
    include-system-site-packages = false
    base-prefix = /usr/local/python-3.14
    base-exec-prefix = /usr/local/python-3.14
    base-executable = /usr/local/python-3.14/bin/python3.14

Three keys carry the version, and they differ in precision and in who should read them:

.. list-table::
    :header-rows: 1
    :widths: 25 30 45

    - - Key
      - Example
      - Read it when
    - - ``python-version``
      - ``3.14``
      - You want the feature release, which is what selects a wheel tag or a type-checker target. `PEP 838
        <https://peps.python.org/pep-0838/>`_ defines it and every tool creating an environment must write it.
    - - ``version``
      - ``3.14.6``
      - You need the patch level as well. PEP 838 discourages reading it in favor of ``python-version``.
    - - ``version_info``
      - ``3.14.6.final.0``
      - You need the release level and serial. Written by virtualenv rather than by any specification.

``prompt`` appears as an extra key when you pass ``--prompt``. The ``base-*`` keys come from the creator and vary by
creation method.

``CACHEDIR.TAG``
================

Marks the environment as regenerable cache content, following the `cache directory tagging specification
<https://bford.info/cachedir/>`_, so backup tools skip it. virtualenv leaves an existing file untouched.

``.gitignore``
==============

Holds ``*``, keeping the environment out of Git. Skip it with ``--no-vcs-ignore``. virtualenv leaves an existing file
untouched, and writes nothing for Mercurial, Bazaar or Subversion, none of which honor ignore files in a subdirectory.

``bin`` / ``Scripts``
=====================

The interpreter, the console scripts of any seeded package, and the activation scripts for each shell.
:doc:`environment-layout` lists the names the interpreter answers to, and :ref:`explanation:Activators` covers the
shells.

*******************************
 Beside the environment folder
*******************************

``.venv``
=========

A :PEP:`832` redirect file holding the destination folder name, which tells editors and type checkers which environment
of the parent folder to use. Skip it with ``--no-venv-redirect``.

.. warning::

    This file is provisional because PEP 832 is still a draft, and virtualenv follows the PEP as it changes. A minor or
    patch release may change this file and ``--no-venv-redirect`` in backward incompatible ways.

.. code-block:: text

    py314

Format rules virtualenv follows when it writes the file:

.. list-table::
    :header-rows: 1
    :widths: 30 70

    - - Rule
      - Behavior
    - - Encoding
      - UTF-8 without a byte order mark.
    - - Content
      - One line: the destination folder name, relative to the parent folder, followed by a newline.
    - - Target
      - The environment created last.
    - - ``.venv`` folder
      - Left alone, whether folder or symlink; virtualenv writes nothing when the destination itself is ``.venv``.
    - - Existing redirect
      - Replaced only when its target's ``pyvenv.cfg`` carries the ``virtualenv`` key; one written by another tool, or
        pointing at a missing folder, stays.
    - - Failure
      - Logged as a warning; the environment is still created.
