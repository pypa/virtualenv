Reseeding an environment with ``--symlink-app-data`` no longer fails with ``FileExistsError`` and leaves it without
``pip`` when ``pip`` was upgraded or reinstalled by ``pip`` itself, including bytecode written after that install.
