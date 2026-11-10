Write the wheel and zipapp SBOMs with `python-sbom <https://github.com/tox-dev/python-sbom>`_ instead of virtualenv's
own generator. Each bundled seed wheel is now identified by its path inside the wheel rather than by its PyPI purl, so
the wheel's and the zipapp's SBOMs name it alike; the metadata also names the SBOM file and its repository, and the
build tools include python-sbom and virtualenv's content provider.
