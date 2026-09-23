#############################
 Verify a virtualenv release
#############################

The ``release.yaml`` workflow in `pypa/virtualenv <https://github.com/pypa/virtualenv>`_ builds and publishes every
release. The steps below check that a file you downloaded came out of that workflow, and show you what the release
bundles. The examples use release ``21.10.0``; replace it with the version you have.
:doc:`../reference/release-artifacts` lists every file a release publishes, and :ref:`release-integrity` covers what
these checks prove.

You need `uv <https://docs.astral.sh/uv/>`_, whose ``uvx`` runs ``pip`` and `pypi-attestations
<https://pypi.org/project/pypi-attestations/>`_ without installing them, the `GitHub CLI <https://cli.github.com>`_ for
the GitHub release assets and attestations, and `jq <https://jqlang.org>`_ to read the SBOMs.

***********************************
 Verify a wheel or sdist from PyPI
***********************************

Download the wheel and the sdist without installing them:

.. code-block:: console

    $ uvx pip download virtualenv==21.10.0 --no-deps --dest .
    $ uvx pip download virtualenv==21.10.0 --no-deps --no-binary :all: --dest .

Check each file against the attestation PyPI stores for it, one file per call:

.. code-block:: console

    $ uvx pypi-attestations verify pypi --repository https://github.com/pypa/virtualenv virtualenv-21.10.0-py3-none-any.whl
    OK: virtualenv-21.10.0-py3-none-any.whl
    $ uvx pypi-attestations verify pypi --repository https://github.com/pypa/virtualenv virtualenv-21.10.0.tar.gz
    OK: virtualenv-21.10.0.tar.gz

A modified file fails with ``subject does not match distribution digest``, and a file signed by another repository fails
with ``provenance was signed by repository ...``. To check the copy on PyPI without downloading it first, prefix the
file name with ``pypi:``, as in ``pypi:virtualenv-21.10.0-py3-none-any.whl``.

*******************
 Verify the zipapp
*******************

Download the zipapp and its provenance bundle from the GitHub release, then verify one against the other:

.. code-block:: console

    $ gh release download 21.10.0 --repo pypa/virtualenv --pattern virtualenv.pyz --pattern virtualenv.pyz.intoto.jsonl
    $ gh attestation verify virtualenv.pyz --repo pypa/virtualenv --bundle virtualenv.pyz.intoto.jsonl \
        --signer-workflow pypa/virtualenv/.github/workflows/release.yaml

Add ``--source-ref refs/tags/21.10.0`` to also require that the build ran from the ``21.10.0`` tag. Without
``--bundle``, ``gh`` fetches the attestation from GitHub instead of reading the local file.

The zipapp at ``https://bootstrap.pypa.io/virtualenv.pyz`` comes from `pypa/get-virtualenv
<https://github.com/pypa/get-virtualenv>`_ and can trail the latest release. ``python virtualenv.pyz --version`` shows
which release you have. Verify it with ``gh attestation verify`` as above, leaving out ``--bundle``. A release without a
provenance bundle has no attestation to check; compare the file's SHA-256 with the digest GitHub lists for the release
asset instead:

.. code-block:: console

    $ gh release view 21.10.0 --repo pypa/virtualenv --json assets --jq '.assets[] | .name + " " + .digest'
    virtualenv.pyz sha256:345775312f24d272017d7c640b3184414fa1779152e28aa9f082491766d5fb38
    virtualenv.pyz.intoto.jsonl sha256:e2486ddcc38fa254afda37cd325dc14db45b42519235eb7e304388ea6afd3e2e
    $ shasum -a 256 virtualenv.pyz
    345775312f24d272017d7c640b3184414fa1779152e28aa9f082491766d5fb38  virtualenv.pyz

************************
 Read the embedded SBOM
************************

The wheel carries a `CycloneDX <https://cyclonedx.org>`_ SBOM that lists the ``pip`` and ``setuptools`` wheels
virtualenv bundles, with their hashes, licenses and the Python versions each one seeds. Extract it from the wheel:

.. code-block:: console

    $ python -m zipfile --extract virtualenv-21.10.0-py3-none-any.whl wheel
    $ jq -r '.components[] | select(.hashes) | "\(.name) \(.version) Python \([.properties[] | select(.name == "virtualenv:seeded-for-python").value] | join(","))"' \
        wheel/virtualenv-21.10.0.dist-info/sboms/virtualenv.cdx.json
    pip 26.0.1 Python 3.9
    pip 26.2.1 Python 3.10,3.11,3.12,3.13,3.14,3.15,3.16
    setuptools 82.0.1 Python 3.9
    setuptools 84.0.0 Python 3.10,3.11,3.12,3.13,3.14,3.15,3.16

An installed virtualenv keeps the same file in its ``.dist-info`` directory. Print its path with the Python that runs
virtualenv:

.. code-block:: console

    $ python -c "import importlib.metadata as m; print(next(f.locate() for f in m.files('virtualenv') if f.name == 'virtualenv.cdx.json'))"

******************************
 Verify the SBOM attestations
******************************

The release workflow attests the SBOM against the wheel and the sdist. Check that attestation exists and was signed by
the release workflow:

.. code-block:: console

    $ gh attestation verify virtualenv-21.10.0-py3-none-any.whl -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom

To confirm the attested SBOM matches the one inside the wheel, save the attested copy and compare the two. ``diff``
prints nothing when they match:

.. code-block:: console

    $ gh attestation verify virtualenv-21.10.0-py3-none-any.whl -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.cdx.json
    $ diff <(jq -S . attested.cdx.json) <(jq -S . wheel/virtualenv-21.10.0.dist-info/sboms/virtualenv.cdx.json)

Newer releases also attach the SBOM as ``virtualenv.cdx.json`` and an SPDX 2.3 rendering of it as
``virtualenv.spdx.json``, and attest the SPDX document against the wheel and the sdist as well. Replace ``<version>``
with a release that has these assets. The CycloneDX asset must match the SBOM in the wheel, and the SPDX asset what the
release attested:

.. code-block:: console

    $ uvx pip download virtualenv==<version> --no-deps --dest .
    $ gh release download <version> --repo pypa/virtualenv --pattern virtualenv.cdx.json --pattern virtualenv.spdx.json
    $ unzip -p virtualenv-<version>-py3-none-any.whl '*.dist-info/sboms/virtualenv.cdx.json' | cmp - virtualenv.cdx.json
    $ gh attestation verify virtualenv-<version>-py3-none-any.whl -R pypa/virtualenv --predicate-type https://spdx.dev/Document/v2.3 \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.spdx.json
    $ diff <(jq -S . attested.spdx.json) <(jq -S . virtualenv.spdx.json)

**********************
 Read the zipapp SBOM
**********************

Newer releases describe the zipapp in its own CycloneDX SBOM. The zipapp carries it at its root, the release attaches it
as ``virtualenv.pyz.cdx.json``, and GitHub attests it against ``virtualenv.pyz``. Check all three agree:

.. code-block:: console

    $ gh release download <version> --repo pypa/virtualenv --pattern virtualenv.pyz --pattern virtualenv.pyz.cdx.json
    $ unzip -p virtualenv.pyz virtualenv.pyz.cdx.json | cmp - virtualenv.pyz.cdx.json
    $ gh attestation verify virtualenv.pyz -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.pyz.cdx.json
    $ diff <(jq -S . attested.pyz.cdx.json) <(jq -S . virtualenv.pyz.cdx.json)

List the distributions the zipapp bundles and the Python versions that load each one:

.. code-block:: console

    $ jq -r '.components[] | "\(.name) \(.version) \([.properties[] | select(.name == "virtualenv:loaded-for-python").value] | join(","))"' \
        virtualenv.pyz.cdx.json

*******************
 Rebuild the sdist
*******************

The release builds with ``SOURCE_DATE_EPOCH`` set to the commit time of the release tag, so rebuilding the tag yields
the same sdist, byte for byte:

.. code-block:: console

    $ git clone --branch 21.10.0 https://github.com/pypa/virtualenv
    $ cd virtualenv
    $ SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uv build --sdist --out-dir rebuild .
    $ cmp rebuild/virtualenv-21.10.0.tar.gz ../virtualenv-21.10.0.tar.gz

``cmp`` prints nothing when the files match. A rebuilt wheel matches the published one in every file except the SBOM,
which records the machine that built it, and ``RECORD``, which holds the SBOM's hash.
