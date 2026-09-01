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

``.python-envs``
================

Lists the environments of the parent folder, one per line, with the last line naming the default one, per `PEP 832
<https://peps.python.org/pep-0832/>`_. Skip it with ``--no-python-envs``.

.. code-block:: text

    py313
    py314

Format rules virtualenv follows when it rewrites the file:

.. list-table::
    :header-rows: 1
    :widths: 30 70

    - - Rule
      - Behavior
    - - Encoding
      - UTF-8.
    - - Entry
      - The destination folder name, since the file sits in the destination's parent. Absolute entries written by other
        tools are read and preserved.
    - - Default
      - The last line. A new environment goes last, and an entry already pointing at it moves there rather than
        repeating.
    - - ``.venv``
      - Never written, because PEP 832 counts a ``.venv`` folder beside the file as its implicit last line.
    - - Blank lines
      - Dropped on rewrite.
    - - Failure
      - Logged as a warning; the environment is still created.

``.python-envs.lock``
=====================

An empty lock file serializing concurrent rewrites of ``.python-envs``. It carries no content. On Windows it disappears
as the lock releases; on other platforms it stays behind, and you can delete it while no virtualenv is running.
Suppressed by ``--no-python-envs`` along with the file it guards, and worth adding to your VCS ignore list.
