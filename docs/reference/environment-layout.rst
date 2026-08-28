####################
 Environment layout
####################

The interpreter in a created environment answers to more than one name, so a script or tool that hard-codes any of them
keeps working. The names below are what the builtin creators write for CPython; PyPy, GraalPy and RustPython follow the
same shape under their own executable names.

``{minor}`` stands for the target interpreter's minor version, so ``python3.{minor}`` reads as ``python3.14`` for a
CPython 3.14 target.

*******
 POSIX
*******

``bin`` holds one real reference to the host interpreter and links the rest to it:

==================== ======================================================================
Name                 Notes
==================== ======================================================================
``python``           References the host interpreter.
``python3``          Alias.
``python3.{minor}``  Alias carrying the target's minor version.
``python3.{minor}t`` Free-threaded builds only.
host executable name Appears when the host carries another name, such as ``pypy3.{minor}``.
==================== ======================================================================

*********
 Windows
*********

``Scripts`` holds copies rather than links, since symlinking the interpreter is unreliable there (`bpo-42013
<https://bugs.python.org/issue42013>`_):

========================= =====================================================================
Name                      Notes
========================= =====================================================================
``python.exe``            References the host interpreter.
``python3.exe``           Alias.
``python3``               Alias without the extension.
``python3.{minor}t.exe``  Free-threaded builds only.
``pythonw.exe``           Runs without opening a console window.
``pythonw3.exe``          Alias for ``pythonw.exe``.
``pythonw3.{minor}t.exe`` Free-threaded builds only.
host executable name      Appears when the host carries another name, such as ``python_d.exe``.
========================= =====================================================================

On CPython 3.13 and later ``python.exe`` holds a copy of the ``venvlauncher.exe`` redirector from the host's standard
library rather than the interpreter binary, and ``pythonw.exe`` comes from ``venvwlauncher.exe``. The redirector reads
``pyvenv.cfg`` and hands off to the interpreter in the base prefix, which is why the environment needs no copy of the
DLLs. Its own file name stays out of ``Scripts``, matching what the standard library's ``venv`` writes.

.. note::

    ``--copies`` makes the POSIX layout use copies instead of links. The set of names does not change.
