###################
 Release artifacts
###################

A maintainer runs the `pre-release workflow <https://github.com/pypa/virtualenv/actions/workflows/pre-release.yaml>`_,
which writes the changelog, commits the release and pushes the version tag. That tag starts the `release workflow
<https://github.com/pypa/virtualenv/actions/workflows/release.yaml>`_, which builds and publishes every file below.
``{version}`` stands for the release version, such as ``21.10.0``. :doc:`../how-to/verify-release` shows how to check
each file, and :ref:`release-integrity` explains what the checks prove.

*******
 Files
*******

.. list-table::
    :header-rows: 1

    - - File
      - Where
      - Contents
    - - ``virtualenv-{version}-py3-none-any.whl``
      - `PyPI <https://pypi.org/project/virtualenv/>`_
      - the package, with its CycloneDX SBOM under ``.dist-info/sboms``
    - - ``virtualenv-{version}.tar.gz``
      - PyPI
      - the source distribution
    - - ``virtualenv.pyz``
      - `GitHub release <https://github.com/pypa/virtualenv/releases>`_
      - the zipapp: virtualenv and its runtime dependencies for every supported Python, with its own SBOM at the archive
        root
    - - ``virtualenv.pyz.intoto.jsonl``
      - GitHub release
      - the Sigstore bundle holding the zipapp's SLSA provenance
    - - ``virtualenv.pyz.cdx.json``
      - GitHub release
      - the zipapp's CycloneDX SBOM, the same file the zipapp carries
    - - ``virtualenv.cdx.json``
      - GitHub release
      - the wheel's CycloneDX SBOM, the same file the wheel carries
    - - ``virtualenv.spdx.json``
      - GitHub release
      - the wheel's SBOM rendered as SPDX 2.3
    - - ``virtualenv.pyz``
      - ``https://bootstrap.pypa.io/virtualenv.pyz``
      - the latest release's zipapp
    - - ``virtualenv.pyz`` for Python ``{x.y}``
      - ``https://bootstrap.pypa.io/virtualenv/{x.y}/virtualenv.pyz``
      - the zipapp for Python ``{x.y}``

The bootstrap copies come from the ``public`` directory of `pypa/get-virtualenv
<https://github.com/pypa/get-virtualenv>`_, which the release workflow updates, and can trail the latest release.
Releases published before an asset existed do not have it; ``gh release view {version} --repo pypa/virtualenv`` lists
what a release carries. Immutable releases are enabled on the repository, so assets cannot change after publication.

**************
 Attestations
**************

.. list-table::
    :header-rows: 1

    - - Attestation
      - Subject
      - Stored at
    - - PyPI publish attestation (`PEP 740 <https://peps.python.org/pep-0740/>`_), predicate
        ``https://docs.pypi.org/attestations/publish/v1``
      - wheel, sdist
      - ``https://pypi.org/integrity/virtualenv/{version}/{file}/provenance``
    - - SLSA provenance, predicate ``https://slsa.dev/provenance/v1``
      - ``virtualenv.pyz``
      - GitHub attestations API and ``virtualenv.pyz.intoto.jsonl``
    - - CycloneDX SBOM, predicate ``https://cyclonedx.org/bom``
      - wheel, sdist
      - GitHub attestations API, predicate equal to ``virtualenv.cdx.json``
    - - SPDX SBOM, predicate ``https://spdx.dev/Document/v2.3``
      - wheel, sdist
      - GitHub attestations API, predicate equal to ``virtualenv.spdx.json``
    - - CycloneDX SBOM, predicate ``https://cyclonedx.org/bom``
      - ``virtualenv.pyz``
      - GitHub attestations API, predicate equal to ``virtualenv.pyz.cdx.json``

The release workflow signs every attestation through `Sigstore <https://www.sigstore.dev>`_ with the identity
``https://github.com/pypa/virtualenv/.github/workflows/release.yaml@refs/tags/{version}``.

*******
 SBOMs
*******

Wheel SBOM
==========

- Format: CycloneDX 1.6 JSON.
- Location in the wheel: ``virtualenv-{version}.dist-info/sboms/virtualenv.cdx.json``, following `PEP 770
  <https://peps.python.org/pep-0770/>`_. Installers copy it into the installed ``.dist-info`` directory. The sdist does
  not carry one.
- Components: every wheel bundled under ``virtualenv/seed/wheels/embed``, with its SHA-256, license, the packages it
  vendors, and a ``virtualenv:seeded-for-python`` property per Python version that receives it; plus the runtime
  dependencies declared in the wheel metadata, without versions, since the installer resolves those.
- Build record: the Python version and build backend packages that produced the wheel, the source commit, and the
  ``SOURCE_DATE_EPOCH`` used for timestamps. Releases up to 21.10.0 also recorded the operating system, architecture and
  interpreter build of the build machine.
- First release carrying it: 21.8.1.

SPDX rendering
==============

``virtualenv.spdx.json`` is the wheel SBOM rendered as SPDX 2.3 JSON for tools that read only SPDX. It keeps the
packages, SHA-256 hashes, declared licenses, purls and the containment, dependency and build tool relationships. It
leaves out the per-file hashes, because SPDX 2.3 requires a SHA-1 for every file and wheel ``RECORD`` files hold
SHA-256, and the build record, which SPDX 2.3 has no field for. Its document namespace ends in the CycloneDX serial
number, so both documents name the same build.

Zipapp SBOM
===========

- Format: CycloneDX 1.6 JSON, at ``virtualenv.pyz.cdx.json`` in the zipapp's root and as a release asset.
- Root component: ``pkg:generic/virtualenv.pyz@{version}``.
- Components: virtualenv, with a SHA-256 per file and the embedded ``pip`` and ``setuptools`` wheels by purl and
  SHA-256; and each bundled distribution, such as ``filelock`` or ``platformdirs``, with its version, license, a
  ``virtualenv:loaded-for-python`` property per Python version that imports it, and a SHA-256 per file. Every file in
  the archive other than the SBOM appears in it.
- Build record: the Python version and packages of the environment that built the zipapp, and the ``SOURCE_DATE_EPOCH``
  used for timestamps. Packages installed from platform-specific wheels appear without their files, which differ per
  operating system and architecture.

***************************
 Embedded wheel advisories
***************************

Only Python 3.9 environments receive the embedded ``pip`` 26.0.1 and ``setuptools`` 82.0.1, and both versions have
published advisories that a scanner reading the SBOMs reports. ``pip`` 26.1 and ``setuptools`` 83 and later require
Python 3.10, so ``--pip`` and ``--setuptools`` cannot pick a fixed version for Python 3.9; create environments for
Python 3.10 or newer to avoid them.

***********************
 Build reproducibility
***********************

The release sets ``SOURCE_DATE_EPOCH`` to the commit time of the tag (``git log -1 --pretty=%ct``). Rebuilding the tag
with the same value reproduces the sdist byte for byte.

The wheel, whose SBOM `hatch_build.py <https://github.com/pypa/virtualenv/blob/main/hatch_build.py>`_ writes, reproduces
byte for byte on any operating system and architecture when these inputs match the release:

- the source tree, as a git checkout of the tag, since the SBOM records the commit;
- ``SOURCE_DATE_EPOCH``;
- the Python patch version, which the SBOM records;
- the versions of the build backend and its dependencies, which the SBOM lists.

Any build frontend works, since the SBOM leaves out the installer metadata a frontend writes into the build environment.

Wheels up to 21.10.0 recorded the build machine in their SBOM, so a rebuild of those differs in the SBOM and in
``RECORD``, which holds the SBOM's hash.

The zipapp, built by `tasks/make_zipapp.py <https://github.com/pypa/virtualenv/blob/main/tasks/make_zipapp.py>`_, needs
the same inputs, and its entries carry ``SOURCE_DATE_EPOCH`` as their timestamp and fixed permissions. Its build also
downloads the distributions it bundles and the backend for the wheel inside it from PyPI without pinning them, so a
rebuild matches only while those resolve to the versions the release used.
