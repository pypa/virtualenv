#############################
 Verify a virtualenv release
#############################

The ``release.yaml`` workflow in `pypa/virtualenv <https://github.com/pypa/virtualenv>`_ builds and publishes every
release. The steps below check that a file you downloaded came out of that workflow, and show you what the release
bundles. The examples use release ``21.12.1``; replace it with the version you have.
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

    $ uvx pip download virtualenv==21.12.1 --no-deps --dest .
    $ uvx pip download virtualenv==21.12.1 --no-deps --no-binary :all: --dest .

Check each file against the attestation PyPI stores for it, one file per call:

.. code-block:: console

    $ uvx pypi-attestations verify pypi --repository https://github.com/pypa/virtualenv virtualenv-21.12.1-py3-none-any.whl
    OK: virtualenv-21.12.1-py3-none-any.whl
    $ uvx pypi-attestations verify pypi --repository https://github.com/pypa/virtualenv virtualenv-21.12.1.tar.gz
    OK: virtualenv-21.12.1.tar.gz

A modified file fails with ``subject does not match distribution digest``, and a file signed by another repository fails
with ``provenance was signed by repository ...``. To check the copy on PyPI without downloading it first, prefix the
file name with ``pypi:``, as in ``pypi:virtualenv-21.12.1-py3-none-any.whl``.

**************************************
 Verify the GitHub release and assets
**************************************

Releases from 21.11.0 on are `immutable
<https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases>`_:
GitHub signs a release attestation that binds the tag to its commit and to the SHA-256 of every asset, and refuses any
later change to the tag or the assets. Check that attestation:

.. code-block:: console

    $ gh release verify 21.12.1 --repo pypa/virtualenv
    Resolved tag 21.12.1 to sha1:befec5eae075d1c4cb00a41d0c72bcdb91bf4586
    Loaded attestation from GitHub API
    ✓ Release 21.12.1 verified!

Then check a file you downloaded against the digests the attestation lists. The command hashes the local file, so it
works for a copy under any name:

.. code-block:: console

    $ gh release download 21.12.1 --repo pypa/virtualenv --pattern virtualenv.pyz
    $ gh release verify-asset 21.12.1 virtualenv.pyz --repo pypa/virtualenv
    ✓ Verification succeeded! virtualenv.pyz is present in release 21.12.1

GitHub signs the release attestation itself, so it shows the assets did not change after publication. It does not name
the workflow that built them; the provenance check below does.

*******************
 Verify the zipapp
*******************

Download the zipapp and its provenance bundle from the GitHub release, then verify one against the other:

.. code-block:: console

    $ gh release download 21.12.1 --repo pypa/virtualenv --pattern virtualenv.pyz --pattern virtualenv.pyz.intoto.jsonl
    $ gh attestation verify virtualenv.pyz --repo pypa/virtualenv --bundle virtualenv.pyz.intoto.jsonl \
        --signer-workflow pypa/virtualenv/.github/workflows/release.yaml

Add ``--source-ref refs/tags/21.12.1`` to also require that the build ran from the ``21.12.1`` tag. Without
``--bundle``, ``gh`` fetches the attestation from GitHub instead of reading the local file.

The zipapp at ``https://bootstrap.pypa.io/virtualenv.pyz`` comes from `pypa/get-virtualenv
<https://github.com/pypa/get-virtualenv>`_ and can trail the latest release. ``python virtualenv.pyz --version`` shows
which release you have. Verify it with ``gh release verify-asset`` for that release, or with ``gh attestation verify``
as above, leaving out ``--bundle``. Releases before 21.7.11 have neither a release attestation nor a provenance bundle;
compare the file's SHA-256 with the digest GitHub lists for the release asset instead:

.. code-block:: console

    $ gh release view 21.7.10 --repo pypa/virtualenv --json assets --jq '.assets[] | .name + " " + .digest'
    virtualenv.pyz sha256:06ee4ea84517e9b8565f7ee81c064d2de5e83dad3874d2babd7b94b2b40c4595
    $ shasum -a 256 virtualenv.pyz
    06ee4ea84517e9b8565f7ee81c064d2de5e83dad3874d2babd7b94b2b40c4595  virtualenv.pyz

************************
 Read the embedded SBOM
************************

The wheel carries a `CycloneDX <https://cyclonedx.org>`_ SBOM that lists the ``pip`` and ``setuptools`` wheels
virtualenv bundles, with their hashes, licenses and the Python versions each one seeds. Extract it from the wheel:

.. code-block:: console

    $ python -m zipfile --extract virtualenv-21.12.1-py3-none-any.whl wheel
    $ jq -r '.components[] | select(.hashes) | "\(.name) \(.version) Python \([.properties[] | select(.name == "virtualenv:seeded-for-python").value] | join(","))"' \
        wheel/virtualenv-21.12.1.dist-info/sboms/virtualenv.cdx.json
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

    $ gh attestation verify virtualenv-21.12.1-py3-none-any.whl -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom

To confirm the attested SBOM matches the one inside the wheel, save the attested copy and compare the two. ``diff``
prints nothing when they match:

.. code-block:: console

    $ gh attestation verify virtualenv-21.12.1-py3-none-any.whl -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.cdx.json
    $ diff <(jq -S . attested.cdx.json) <(jq -S . wheel/virtualenv-21.12.1.dist-info/sboms/virtualenv.cdx.json)

Releases from 21.11.0 on also attach the SBOM as ``virtualenv.cdx.json`` and an SPDX 2.3 rendering of it as
``virtualenv.spdx.json``, and attest the SPDX document against the wheel and the sdist as well. The CycloneDX asset must
match the SBOM in the wheel, and the SPDX asset what the release attested:

.. code-block:: console

    $ gh release download 21.12.1 --repo pypa/virtualenv --pattern virtualenv.cdx.json --pattern virtualenv.spdx.json
    $ unzip -p virtualenv-21.12.1-py3-none-any.whl '*.dist-info/sboms/virtualenv.cdx.json' | cmp - virtualenv.cdx.json
    $ gh attestation verify virtualenv-21.12.1-py3-none-any.whl -R pypa/virtualenv --predicate-type https://spdx.dev/Document/v2.3 \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.spdx.json
    $ diff <(jq -S . attested.spdx.json) <(jq -S . virtualenv.spdx.json)

**********************
 Read the zipapp SBOM
**********************

Releases from 21.11.0 on describe the zipapp in its own CycloneDX SBOM. The zipapp carries it at its root, the release
attaches it as ``virtualenv.pyz.cdx.json``, and GitHub attests it against ``virtualenv.pyz``. Check all three agree:

.. code-block:: console

    $ gh release download 21.12.1 --repo pypa/virtualenv --pattern virtualenv.pyz --pattern virtualenv.pyz.cdx.json
    $ unzip -p virtualenv.pyz virtualenv.pyz.cdx.json | cmp - virtualenv.pyz.cdx.json
    $ gh attestation verify virtualenv.pyz -R pypa/virtualenv --predicate-type https://cyclonedx.org/bom \
        --format json --jq '.[0].verificationResult.statement.predicate' > attested.pyz.cdx.json
    $ diff <(jq -S . attested.pyz.cdx.json) <(jq -S . virtualenv.pyz.cdx.json)

List the distributions the zipapp bundles and the Python versions that load each one:

.. code-block:: console

    $ jq -r '.components[] | "\(.name) \(.version) \([.properties[] | select(.name == "virtualenv:loaded-for-python").value] | join(","))"' \
        virtualenv.pyz.cdx.json
    virtualenv 21.12.1
    distlib 0.4.3 3.14,3.13,3.12,3.11,3.10,3.9,3.8
    filelock 3.19.1 3.9,3.8
    filelock 3.32.6 3.14,3.13,3.12,3.11,3.10
    platformdirs 4.11.8 3.14,3.13,3.12,3.11,3.10
    platformdirs 4.4.0 3.9,3.8
    python-discovery 1.6.0 3.14,3.13,3.12,3.11,3.10,3.9,3.8
    typing_extensions 4.16.0 3.10,3.9,3.8

***************************
 Rebuild the release files
***************************

The release builds with ``SOURCE_DATE_EPOCH`` set to the commit time of the release tag, so rebuilding the tag yields
the same sdist, byte for byte:

.. code-block:: console

    $ git clone --branch 21.12.1 https://github.com/pypa/virtualenv
    $ cd virtualenv
    $ SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uv build --sdist --out-dir rebuild .
    $ cmp rebuild/virtualenv-21.12.1.tar.gz ../virtualenv-21.12.1.tar.gz

``cmp`` prints nothing when the files match.

The wheel of a release from 21.11.0 on rebuilds byte for byte too, on any operating system and architecture, once the
Python patch version and the build backend versions match the ones the release used. Its SBOM lists both, so read them
from the published wheel and pass them to the build:

.. code-block:: console

    $ unzip -p ../virtualenv-21.12.1-py3-none-any.whl '*.dist-info/sboms/virtualenv.cdx.json' > published.cdx.json
    $ jq -r '.metadata.tools.components[] | select(.type == "platform") | .version' published.cdx.json
    3.14.7
    $ jq -r '.metadata.tools.components[] | select(.purl // "" | startswith("pkg:pypi/")) | "\(.name)==\(.version)"' \
        published.cdx.json > build-constraints.txt
    $ SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uv build --wheel --python 3.14.7 \
        --build-constraint build-constraints.txt --out-dir rebuild .
    $ cmp rebuild/virtualenv-21.12.1-py3-none-any.whl ../virtualenv-21.12.1-py3-none-any.whl

Build from a git checkout, since the SBOM records the source commit and an sdist does not carry it. Wheels up to 21.10.0
recorded the machine that built them in the SBOM, so a rebuild of those differs in the SBOM and in ``RECORD``, which
holds the SBOM's hash.

The zipapp of a release from 21.11.0 on rebuilds byte for byte as well. The `pylock.zipapp.toml
<https://github.com/pypa/virtualenv/blob/main/pylock.zipapp.toml>`_ lock at the tag pins each distribution it bundles by
version and SHA-256, so only the build tools can drift. Two SBOMs list them: the zipapp SBOM holds the tools of the
``tox`` environment that assembles the zipapp, and the wheel SBOM inside the zipapp holds the build backend for that
wheel. Constrain both, and run on the CPython version the zipapp SBOM lists:

.. code-block:: console

    $ jq -r '.metadata.tools.components[] | select(.purl // "" | startswith("pkg:pypi/")) | "\(.name)==\(.version)"' \
        ../virtualenv.pyz.cdx.json > zipapp-constraints.txt
    $ unzip -p ../virtualenv.pyz 'virtualenv-*.dist-info/sboms/virtualenv.cdx.json' \
        | jq -r '.metadata.tools.components[] | select(.purl // "" | startswith("pkg:pypi/")) | "\(.name)==\(.version)"' \
        > wheel-constraints.txt
    $ UV_CONSTRAINT=$PWD/zipapp-constraints.txt PIP_BUILD_CONSTRAINT=$PWD/wheel-constraints.txt \
        SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct) uvx --with tox-uv tox r -e zipapp -x 'env.zipapp.pass_env+=PIP_BUILD_CONSTRAINT'
    $ cmp virtualenv.pyz ../virtualenv.pyz

The release runs ``tox`` with the ``tox-uv`` plugin as well. The plugin passes ``UV_*`` variables into the environment,
and the ``-x`` override adds ``PIP_BUILD_CONSTRAINT`` for the ``pip wheel`` call that builds the virtualenv wheel inside
the zipapp.
