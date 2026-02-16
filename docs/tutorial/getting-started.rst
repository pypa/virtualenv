#################
 Getting started
#################

This tutorial will teach you the basics of virtualenv through hands-on practice. You'll create your first virtual
environment, install packages, and learn how to manage project dependencies.

***************
 Prerequisites
***************

Before starting this tutorial, you need:

- Python 3.8 or later installed on your system.
- virtualenv installed (see :doc:`../how-to/install`).

***************************************
 Create your first virtual environment
***************************************

Let's create a virtual environment called ``myproject``:

.. code-block:: console

    $ virtualenv myproject
    created virtual environment CPython3.13.2.final.0-64 in 200ms
      creator CPython3Posix(dest=/home/user/myproject, clear=False, no_vcs_ignore=False, global=False)
      seeder FromAppData(download=False, pip=bundle, setuptools=bundle, via=copy, app_data_dir=/home/user/.cache/virtualenv)
      activators BashActivator,CShellActivator,FishActivator,NushellActivator,PowerShellActivator,PythonActivator

This creates a new directory called ``myproject`` containing a complete, isolated Python environment with its own copy
of Python, pip, and other tools.

**************************
 Activate the environment
**************************

To use your virtual environment, you can activate it. The activation command differs by platform:

.. tab:: Linux/macOS

    .. code-block:: console

        $ source myproject/bin/activate

.. tab:: Windows (PowerShell)

    .. code-block:: console

        PS> .\myproject\Scripts\Activate.ps1

.. tab:: Windows (CMD)

    .. code-block:: console

        C:\> .\myproject\Scripts\activate.bat

After activation, your prompt changes to show the active environment:

.. code-block:: console

    (myproject) $

You can verify that Python is now running from inside the virtual environment:

.. tab:: Linux/macOS

    .. code-block:: console

        (myproject) $ which python
        /home/user/myproject/bin/python

.. tab:: Windows (PowerShell)

    .. code-block:: console

        (myproject) PS> where.exe python
        C:\Users\user\myproject\Scripts\python.exe

.. tab:: Windows (CMD)

    .. code-block:: console

        (myproject) C:\> where.exe python
        C:\Users\user\myproject\Scripts\python.exe

*******************
 Install a package
*******************

With the environment activated, install a package using pip:

.. code-block:: console

    (myproject) $ pip install requests
    Collecting requests
      Using cached requests-2.32.3-py3-none-any.whl (64 kB)
    Installing collected packages: requests
    Successfully installed requests-2.32.3

Verify that the package is installed only inside your virtual environment:

.. code-block:: console

    (myproject) $ python -c "import requests; print(requests.__file__)"
    /home/user/myproject/lib/python3.13/site-packages/requests/__init__.py

The path shows that ``requests`` is installed in the virtual environment, not in your system Python.

************
 Deactivate
************

When you're done working in the virtual environment, deactivate it:

.. code-block:: console

    (myproject) $ deactivate
    $

The prompt returns to normal, and Python commands now use your system Python again.

************************
 Use without activation
************************

Activation is a convenience, not a requirement. You can run any executable from the virtual environment directly by
using its full path:

.. tab:: Linux/macOS

    .. code-block:: console

        $ myproject/bin/python -c "import sys; print(sys.prefix)"
        /home/user/myproject

        $ myproject/bin/pip install httpx

.. tab:: Windows (PowerShell)

    .. code-block:: console

        PS> .\myproject\Scripts\python.exe -c "import sys; print(sys.prefix)"
        C:\Users\user\myproject

        PS> .\myproject\Scripts\pip.exe install httpx

.. tab:: Windows (CMD)

    .. code-block:: console

        C:\> .\myproject\Scripts\python.exe -c "import sys; print(sys.prefix)"
        C:\Users\user\myproject

        C:\> .\myproject\Scripts\pip.exe install httpx

This is especially useful in scripts, CI pipelines, and automation where modifying the shell environment is unnecessary.

***********************
 Set up a real project
***********************

Now let's apply what you've learned to a real project workflow:

.. code-block:: console

    $ mkdir myapp && cd myapp
    $ virtualenv venv
    $ source venv/bin/activate  # or use the appropriate command for your platform
    (venv) $ pip install flask requests
    (venv) $ pip freeze > requirements.txt

The ``requirements.txt`` file now contains your project's dependencies:

.. code-block:: text

    blinker==1.9.0
    certifi==2025.1.31
    charset-normalizer==3.4.1
    click==8.1.8
    flask==3.1.0
    idna==3.10
    itsdangerous==2.2.0
    Jinja2==3.1.5
    MarkupSafe==3.0.2
    requests==2.32.3
    urllib3==2.3.0
    werkzeug==3.1.3

This file lets you recreate the exact environment later. Let's test this:

.. code-block:: console

    (venv) $ deactivate
    $ rm -rf venv
    $ virtualenv venv
    $ source venv/bin/activate
    (venv) $ pip install -r requirements.txt

All packages are reinstalled exactly as before. Here's the complete workflow:

.. mermaid::

    graph TD
        A[Create virtual environment] --> B[Activate]
        B --> C[Install packages]
        C --> D[Freeze to requirements.txt]
        D --> E[Deactivate & clean up]
        E --> F[Recreate virtual environment]
        F --> G[Install from requirements.txt]
        G --> H[Ready to work]

        style A fill:#2563eb,stroke:#1d4ed8,color:#fff
        style B fill:#6366f1,stroke:#4f46e5,color:#fff
        style C fill:#6366f1,stroke:#4f46e5,color:#fff
        style D fill:#6366f1,stroke:#4f46e5,color:#fff
        style E fill:#d97706,stroke:#b45309,color:#fff
        style F fill:#6366f1,stroke:#4f46e5,color:#fff
        style G fill:#6366f1,stroke:#4f46e5,color:#fff
        style H fill:#16a34a,stroke:#15803d,color:#fff

******************
 What you learned
******************

In this tutorial, you learned how to:

- Create a virtual environment with ``virtualenv``.
- Activate and deactivate virtual environments on different platforms.
- Install packages in isolation from your system Python.
- Save project dependencies with ``pip freeze``.
- Reproduce environments using ``requirements.txt``.

************
 Next steps
************

Now that you understand the basics, explore these topics:

- :doc:`../how-to/usage` for selecting specific Python versions, configuring defaults, and advanced usage patterns.
- :doc:`../explanation` for understanding how virtualenv works under the hood and how it compares to ``venv``.
- :doc:`../reference/cli` for all available command line options and flags.
