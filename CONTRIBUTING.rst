virtualenv
==========

See docs/index.rst for user documentation.

Contributor notes
-----------------

* virtualenv is designed to work on python 2 and 3 with a single code base.
  Use Python 3 print-function syntax, and always ``use sys.exc_info()[1]``
  inside the ``except`` block to get at exception objects.

* Pull requests should be made against `master` branch, which is also our
  latest stable version.

* All changes to files inside virtualenv_embedded should be integrated to
  ``virtualenv.py`` with ``bin/rebuild-script.py``.

.. _git-flow: https://github.com/nvie/gitflow
.. _coordinate development: http://nvie.com/posts/a-successful-git-branching-model/
