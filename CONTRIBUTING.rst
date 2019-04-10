virtualenv
==========

See docs/index.rst for user documentation.

Contributor notes
-----------------

* virtualenv is designed to work on python 2 and 3 with a single code base.
  Use Python 3 print-function syntax, and always ``use sys.exc_info()[1]``
  inside the ``except`` block to get at exception objects.

* Pull requests should be made against ``master`` branch, which is also our
  latest stable version.

* All changes to files inside virtualenv_embedded must be integrated to
  ``virtualenv.py`` with ``tox -e embed``. The tox run will report failure
  when changes are integrated, as a flag for CI.

* The codebase must be linted with ``tox -e fix_lint`` before being merged.
  The tox run will report failure when the linters revise code, as a flag
  for CI.

.. _git-flow: https://github.com/nvie/gitflow
.. _coordinate development: http://nvie.com/posts/a-successful-git-branching-model/
