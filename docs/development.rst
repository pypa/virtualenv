Development
===========

Getting started
---------------


``virtualenv`` is a volunteer maintained open source project and we welcome contributions of all forms. The sections
below will help you get started with development, testing, and documentation. We’re pleased that you are interested in
working on virtualenv. This document is meant to get you setup to work on virtualenv and to act as a guide and reference
to the development setup. If you face any issues during this process, please
`open an issue <https://github.com/pypa/virtualenv/issues/new?title=Trouble+with+development+environment>`_ about it on
the issue tracker.

Setup
~~~~~

virtualenv is a command line application written in Python. To work on it, you'll need:

- **Source code**: available on `GitHub <https://github.com/pypa/virtualenv>`_. You can use ``git`` to clone the
    repository:

  .. code-block:: console

      git clone https://github.com/pypa/virtualenv
      cd virtualenv

- **Python interpreter**: We recommend using ``CPython``. You can use
  `this guide <https://realpython.com/installing-python/>`_ to set it up.

- :pypi:`tox`: to automatically get the projects development dependencies and run the test suite. We recommend
  installing it using `pipx <https://pipxproject.github.io/pipx/>`_.

Running from source tree
~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to do this is to generate the development tox environment, and then invoke virtualenv from under the
``.tox/dev`` folder

.. code-block:: console

    tox -e dev
    .tox/dev/bin/virtualenv  # on Linux
    .tox/dev/Scripts/virtualenv  # on Windows

Running tests
~~~~~~~~~~~~~

virtualenv's tests are written using the :pypi:`pytest` test framework. :pypi:`tox` is used to automate the setup
and execution of virtualenv's tests.

To run tests locally execute:

.. code-block:: console

    tox -e py

This will run the test suite for the same Python version as under which ``tox`` is installed. Alternatively you can
specify a specific version of python by using the ``pyNN`` format, such as: ``py38``, ``pypy3``, etc.

``tox`` has been configured to forward any additional arguments it is given to ``pytest``.
This enables the use of pytest's
`rich CLI <https://docs.pytest.org/en/latest/usage.html#specifying-tests-selecting-tests>`_. As an example, you can
select tests using the various ways that pytest provides:

.. code-block:: console

    # Using markers
    tox -e py -- -m "not slow"
    # Using keywords
    tox -e py -- -k "test_extra"

Some tests require additional dependencies to be run, such is the various shell activators (``bash``, ``fish``,
``powershell``, etc). These tests will automatically be skipped if these are not present, note however that in CI
all tests are run; so even if all tests succeed locally for you, they may still fail in the CI.

Running linters
~~~~~~~~~~~~~~~

virtualenv uses :pypi:`pre-commit` for managing linting of the codebase. ``pre-commit`` performs various checks on all
files in virtualenv and uses tools that help follow a consistent code style within the codebase. To use linters locally,
run:

.. code-block:: console

    tox -e fix_lint

.. note::

    Avoid using ``# noqa`` comments to suppress linter warnings - wherever possible, warnings should be fixed instead.
    ``# noqa`` comments are reserved for rare cases where the recommended style causes severe readability problems.

Building documentation
~~~~~~~~~~~~~~~~~~~~~~

virtualenv's documentation is built using :pypi:`Sphinx`. The documentation is written in reStructuredText. To build it
locally, run:

.. code-block:: console

    tox -e docs

The built documentation can be found in the ``.tox/docs_out`` folder and may be viewed by opening ``index.html`` within
that folder.

Release
~~~~~~~

virtualenv's release schedule is tied to ``pip``, ``setuptools`` and ``wheel``. We bundle the latest version of these
libraries so each time there's a new version of any of these, there will be a new virtualenv release shortly afterwards
(we usually wait just a few days to avoid pulling in any broken releases).

Contributing
-------------

Submitting pull requests
~~~~~~~~~~~~~~~~~~~~~~~~

Submit pull requests against the ``main`` branch, providing a good description of what you're doing and why. You must
have legal permission to distribute any code you contribute to virtualenv and it must be available under the MIT
License. Provide tests that cover your changes and run the tests locally first. virtualenv
:ref:`supports <compatibility-requirements>` multiple Python versions and operating systems. Any pull request must
consider and work on all these platforms.

Pull Requests should be small to facilitate review. Keep them self-contained, and limited in scope. `Studies have shown
<https://www.kessler.de/prd/smartbear/BestPracticesForPeerCodeReview.pdf>`_ that review quality falls off as patch size
grows. Sometimes this will result in many small PRs to land a single large feature. In particular, pull requests must
not be treated as "feature branches", with ongoing development work happening within the PR. Instead, the feature should
be broken up into smaller, independent parts which can be reviewed and merged individually.

Additionally, avoid including "cosmetic" changes to code that is unrelated to your change, as these make reviewing the
PR more difficult. Examples include re-flowing text in comments or documentation, or addition or removal of blank lines
or whitespace within lines. Such changes can be made separately, as a "formatting cleanup" PR, if needed.

Automated testing
~~~~~~~~~~~~~~~~~

All pull requests and merges to 'main' branch are tested using
`Azure Pipelines <https://azure.microsoft.com/en-gb/services/devops/pipelines/>`_ (configured by
``azure-pipelines.yml`` file at the root of the repository). You can find the status and results to the CI runs for your
PR on GitHub's Web UI for the pull request. You can also find links to the CI services' pages for the specific builds in
the form of "Details" links, in case the CI run fails and you wish to view the output.

To trigger CI to run again for a pull request, you can close and open the pull request or submit another change to the
pull request. If needed, project maintainers can manually trigger a restart of a job/build.

NEWS entries
~~~~~~~~~~~~

The ``changelog.rst`` file is managed using :pypi:`towncrier` and all non trivial changes must be accompanied by a news
entry. To add an entry to the news file, first you need to have created an issue describing the change you want to
make. A Pull Request itself *may* function as such, but it is preferred to have a dedicated issue (for example, in case
the PR ends up rejected due to code quality reasons).

Once you have an issue or pull request, you take the number and you create a file inside of the ``docs/changelog``
directory named after that issue number with an extension of:

- ``feature.rst``,
- ``bugfix.rst``,
- ``doc.rst``,
- ``removal.rst``,
- ``misc.rst``.

Thus if your issue or PR number is ``1234`` and this change is fixing a bug, then you would create a file
``docs/changelog/1234.bugfix.rst``. PRs can span multiple categories by creating multiple files (for instance, if you
added a feature and deprecated/removed the old feature at the same time, you would create
``docs/changelog/1234.bugfix.rst`` and ``docs/changelog/1234.remove.rst``). Likewise if a PR touches multiple issues/PRs
you may create a file for each of them with the same contents and :pypi:`towncrier` will deduplicate them.

Contents of a NEWS entry
^^^^^^^^^^^^^^^^^^^^^^^^

The contents of this file are reStructuredText formatted text that will be used as the content of the news file entry.
You do not need to reference the issue or PR numbers here as towncrier will automatically add a reference to all of
the affected issues when rendering the news file.

In order to maintain a consistent style in the ``changelog.rst`` file, it is preferred to keep the news entry to the
point, in sentence case, shorter than 120 characters and in an imperative tone -- an entry should complete the sentence
``This change will …``. In rare cases, where one line is not enough, use a summary line in an imperative tone followed
by a blank line separating it from a description of the feature/change in one or more paragraphs, each wrapped
at 120 characters. Remember that a news entry is meant for end users and should only contain details relevant to an end
user.

Choosing the type of NEWS entry
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

A trivial change is anything that does not warrant an entry in the news file. Some examples are: code refactors that
don't change anything as far as the public is concerned, typo fixes, white space modification, etc. To mark a PR
as trivial a contributor simply needs to add a randomly named, empty file to the ``news/`` directory with the extension
of ``.trivial``.

Becoming a maintainer
~~~~~~~~~~~~~~~~~~~~~

If you want to become an official maintainer, start by helping out. As a first step, we welcome you to triage issues on
virtualenv's issue tracker. virtualenv maintainers provide triage abilities to contributors once they have been around
for some time and contributed positively to the project. This is optional and highly recommended for becoming a
virtualenv maintainer. Later, when you think you're ready, get in touch with one of the maintainers and they will
initiate a vote among the existing maintainers.

.. note::

    Upon becoming a maintainer, a person should be given access to various virtualenv-related tooling across
    multiple platforms. These are noted here for future reference by the maintainers:

    - GitHub Push Access
    - PyPI Publishing Access
    - CI Administration capabilities
    - ReadTheDocs Administration capabilities
