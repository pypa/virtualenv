#################
 Release History
#################

.. towncrier-draft-entries:: [UNRELEASED DRAFT]

.. towncrier release notes start

.. _release-21-14-13:

************************
 v21.14.13 (2026-10-22)
************************

.. _release-21-14-13-security:

Security
--------

- Stop bash running commands from ``--prompt`` or an environment name containing ``$(...)``, backticks or a backslash
  after ``shopt -s promptvars``, ``set -o posix``, or in a child shell that inherits an exported ``PS1``
  (GHSA-cx6f-vjhg-g3cc); reported by :user:`rozzkml`. zsh now draws the prompt from ``psvar[9]``, which is never parsed
  as shell syntax. (:pr:`3466`) - by :user:`gaborbernat`.
- Write the ``.venv`` redirect and the wheel ``RECORD`` with exclusive create, so a link planted after the existence
  check cannot redirect the write. On POSIX, replace a read-only ``.venv`` redirect that points at a virtualenv.
  (:pr:`3466`) - by :user:`gaborbernat`.

.. _release-21-14-12:

************************
 v21.14.12 (2026-10-21)
************************

.. _release-21-14-12-packaging:

Packaging
---------

- Upgrade the embedded setuptools wheel from ``84.0.0`` to ``84.2.1`` and the embedded pip wheel from ``26.2.1`` to
  ``26.2.2``. (:pr:`3452`)

.. _release-21-14-11:

************************
 v21.14.11 (2026-10-18)
************************

.. _release-21-14-11-fixed:

Fixed
-----

- Search all directories supplied by repeated ``--extra-search-dir`` options instead of keeping only the last group.
  (:pr:`3440`) - by :user:`repzakske`.
- On Windows, the app data is now migrated into the nested cache directory instead of the migration failing with a
  warning on every run. (:pr:`3441`) - by :user:`gaborbernat` and :user:`XXXXXQ-0206`.

.. _release-21-14-10:

************************
 v21.14.10 (2026-10-17)
************************

.. _release-21-14-10-fixed:

Fixed
-----

- Always copy seed packages when app-data is temporary, including when symlink seeding is enabled through an environment
  variable or configuration file. Seeded packages remain available after temporary cache cleanup. (:pr:`3437`) - by
  :user:`gaborbernat`.

.. _release-21-14-9:

***********************
 v21.14.9 (2026-10-17)
***********************

.. _release-21-14-9-fixed:

Fixed
-----

- Parse ``VIRTUALENV_PERIODIC_UPDATE_INSECURE`` as a boolean, so ``0``, ``false``, ``no`` and ``off`` keep certificate
  verification enabled. (:pr:`3398`) - by :user:`gaborbernat`.
- Reject destinations whose resolved path contains the platform's PATH separator, including separators inherited from
  the working directory or a directory symlink. (:pr:`3399`) - by :user:`gaborbernat`.
- Preserve an existing ``pyvenv.cfg`` when a prompt or configuration value cannot be encoded as UTF-8, instead of
  leaving the file empty after a failed environment creation. The file now ends its lines with LF on every platform.

  Debug logs show each configuration line as a Python string literal, so control characters are visible. (:pr:`3400`) -
  by :user:`gaborbernat`.

- Skip writing a ``.venv`` redirect when the environment name contains a line boundary. The environment is still
  created, and any existing redirect remains unchanged. (:pr:`3401`) - by :user:`gaborbernat`.
- Preserve non-ASCII values in ``activate_this.py`` when applications read the script with a legacy text encoding before
  executing it. (:pr:`3402`) - by :user:`gaborbernat`.
- Reject malformed seed versions and requirements ending in archive suffixes before starting pip, with an error
  identifying the invalid value instead of a misleading download or local-file error. (:pr:`3403`) - by
  :user:`gaborbernat`.
- Allow a literal percent sign as a csh prompt and preserve carets in tcsh prompt display instead of interpreting them
  as control-character notation.

  Separate csh history and prompt escapes from preceding non-ASCII text in legacy locales. (:pr:`3404`) - by
  :user:`gaborbernat`.

- Report an error when an existing ``pyvenv.cfg`` is not a regular file, instead of trying to read or write directories,
  pipes, or devices as configuration files. (:pr:`3405`) - by :user:`gaborbernat`.
- Preserve percent-containing paths during batch reactivation and show dollar signs literally in command prompts. Skip
  batch scripts for paths containing line boundaries, and remove stale batch scripts for unsupported paths even when
  only other activators are selected. (:pr:`3406`) - by :user:`gaborbernat`.
- Compile shared seed-cache bytecode without loading site customizations from the destination environment or importing
  modules from the current working directory. (:pr:`3407`) - by :user:`gaborbernat`.
- Keep the bundled seed version when a cached periodic update is older, and stop recording downloads below the bundled
  version during update checks. (:pr:`3408`) - by :user:`gaborbernat`.
- Stop activating a moved environment, leaving ``PATH`` unchanged, when the shell is not bash, the script is evaluated
  or read from standard input, a path tool fails, the sourced file is not the environment's own activation script, or
  the new location has no ``pyvenv.cfg``, instead of continuing with an incorrect environment path. (:pr:`3409`) - by
  :user:`gaborbernat`.
- Reject built-in options with missing values before creating the application-data directory or starting interpreter
  discovery, instead of reporting the argument error after those operations. (:pr:`3410`) - by :user:`gaborbernat`.
- Keep unset-variable bookkeeping out of exported xonsh variables, so child shells do not restore an internal sentinel
  as ``PYTHONHOME``. Skip xonsh activation for destination names that its PATH handling would expand to a different
  path.

  Restore unset Tcl/Tk library variables when switching between environments in one xonsh session.

  Preserve non-ASCII paths and prompts when xonsh reads activation scripts with a legacy encoding. (:pr:`3411`) - by
  :user:`gaborbernat`.

- Skip default shell activators with a warning when a POSIX path encoding is incompatible with their UTF-8 scripts.
  Explicitly requested incompatible shell activators still report an error. Environments created with ``--activators=``
  or ``--activators=python`` remain supported in legacy locales. Undecodable parent paths are now caught before any
  shell activation script is written. (:pr:`3412`) - by :user:`gaborbernat`.
- Keep apostrophes and backslashes in fish activation values separate from preceding non-ASCII characters, so fish 3
  legacy locale decoders cannot consume their escapes as part of a multibyte character. (:pr:`3413`) - by
  :user:`gaborbernat`.
- Preserve backslashes and apostrophes in csh activation values when tcsh's ``backslash_quote`` option is enabled.
  Assign prompt text before conditional branches so skipped prompt branches do not reinterpret its quoting.

  Display literal backslashes once in bsd-csh prompts. Keep disabled prompts unchanged when generated values contain
  quotes. (:pr:`3414`) - by :user:`gaborbernat`.

- Preserve backslashes in POSIX environment directory names during PowerShell activation, including configuration lookup
  and the default prompt. Resolve relative, home-relative, PSDrive-qualified and filesystem provider-qualified
  ``-VenvDir`` arguments to absolute paths, and stop activation when that resolution fails. (:pr:`3415`) - by
  :user:`gaborbernat`.
- Keep helper processes for pip, symlink-seed compilation, stdlib venv creation, and periodic wheel updates from
  importing modules through Python's implicit current-directory entry. Pip helpers retain the selected bootstrap wheel
  on their import path.

  Preserve Python environment-variable overrides for delegated stdlib venv creation while removing the implicit
  working-directory import entry.

  Retain explicit Python configuration when compiling symlink seed images, and report compilation failures. (:pr:`3416`)
  - by :user:`gaborbernat`.

- Preserve spaces, quotes, and backslashes in interpreter paths when pip console scripts need a POSIX shell launcher.
  Paths containing tabs also use the shell launcher so the kernel does not split the interpreter name.

  Apply the same launcher quoting after pip seeding and refresh the installed file records. Later independent pip
  installs or upgrades can overwrite these launchers; recreate affected environments after upgrading virtualenv.
  (:pr:`3417`) - by :user:`gaborbernat`.

- Leave ``PS1`` unchanged when sourcing the POSIX activation script in a shell other than bash or zsh, whose prompt
  escaping rules virtualenv handles; ``VIRTUAL_ENV_PROMPT`` stays available to custom prompts in other shells.

  In bash, keep the prompt literal under older compatibility levels, with ``promptvars`` disabled and in posix mode, and
  avoid ``nounset`` errors after ``VIRTUAL_ENV_PROMPT`` is unset. (:pr:`3418`) - by :user:`gaborbernat`.

- Remove Python's implicit working-directory import entry before handling ``python -m virtualenv`` commands, reducing
  accidental module shadowing during environment creation. Explicit import paths keep their existing order.

  Keep the working-directory entry when virtualenv itself is installed there, and preserve explicit paths under Python
  safe-path mode. (:pr:`3419`) - by :user:`gaborbernat`.

- Start periodic wheel updates with the same virtualenv installation or zipapp that scheduled them, even when the host
  interpreter has another virtualenv version installed or no installed copy.

  Keep standard-library precedence and explicit Python configuration in update processes, and drop only the implicit
  working-directory import entry before importing anything. (:pr:`3420`) - by :user:`gaborbernat`.

- Create new default app-data directories with owner-only access where supported. For existing POSIX defaults owned by
  the current user, remove group and other write access, preserving group write on setgid shared caches. Keep
  permissions on directories owned by another user and on explicit app-data paths. Warn and use temporary app-data if
  changing an owned default cache's permissions fails. (:pr:`3421`) - by :user:`gaborbernat`.
- Reject ``--clear`` when the normalized destination is a symlink or Windows reparse point, including paths containing
  ``..``. Pass the target directory explicitly to clear it. Creating an environment through a symlink without
  ``--clear`` remains supported. (:pr:`3422`) - by :user:`gaborbernat`.
- Detach seed-package and launcher symlinks before running the pip seeder. Reseeding an environment created with
  ``--symlink-app-data`` no longer rewrites its shared wheel image. Unrelated launcher symlinks remain in place.

  Preserve case in console entry-point names and use the last value for duplicate entries when regenerating launchers.

  Remove linked metadata from previous seed versions when reseeding with pip so package listings report the installed
  version. (:pr:`3423`) - by :user:`gaborbernat`.

- Replace line-boundary characters in csh prompt text with spaces so activation remains valid.

  When a filesystem path contains a newline, skip csh activation and remove any stale csh activation scripts. Keep
  filesystem paths unchanged, including other control characters, and omit skipped activators from the creation summary.
  (:pr:`3424`) - by :user:`gaborbernat`.

- Apply the current umask when copying interpreter and seed-package files instead of inheriting cached permission bits.
  Executable sources remain executable within the permissions allowed by that umask. Copied files no longer grant group
  or world write access, even with a permissive umask. Source modes are not preserved: data files start from 0644 and
  executable files from 0755 before applying the umask. (:pr:`3425`) - by :user:`gaborbernat`.
- Reject destinations containing line boundaries when using the stdlib ``venv`` creator, before it writes
  ``pyvenv.cfg``. Other creators retain their existing destination support. Write the final configuration from the
  selected interpreter and virtualenv options instead of merging stdlib's intermediate configuration. GraalPy launcher
  settings are derived from the selected interpreter. (:pr:`3426`) - by :user:`gaborbernat`.
- Preserve file permissions when deletion fails on POSIX. On Windows, clear read-only attributes through a handle that
  opens the entry itself and prevents replacement, preserving other attributes and rejecting reparse points.
  (:pr:`3427`) - by :user:`gaborbernat`.
- Limit seed-package cleanup to entries inside the environment. Ignore metadata entries that name the environment
  itself, a directory holding the metadata (a blank ``top_level.txt`` line names ``site-packages``), or resolve outside
  the environment, with a warning. Launcher entries inside the environment remain supported. (:pr:`3428`) - by
  :user:`gaborbernat`.
- Replace pre-existing directory symlinks and Windows junctions in the environment's executable and library paths before
  creating files. Links within those paths are replaced even when they point inside the environment. Log replaced links
  and junctions, and reject a non-directory encountered while creating their replacements. (:pr:`3429`) - by
  :user:`gaborbernat`.
- Verify downloads in a private staging directory before adding them to the reusable wheel cache. Select the downloaded
  archive from that directory instead of pip's output. The pip seeder now uses the same download verification path and
  installs pinned versions from a temporary directory containing only the selected wheels, without another index lookup.
  Seeded packages retain version pins in pip freeze output. (:pr:`3430`) - by :user:`gaborbernat`.
- Replace existing symbolic and hard links when writing environment configuration, activation scripts, import hooks, and
  seed launchers. Create generated text files exclusively so a replacement link cannot redirect the final file open.
  Before recreating an environment with the stdlib venv creator, replace executable-directory symlinks and Windows
  junctions with real directories. Remove symbolic and hard links inside that directory before creating interpreter
  files, including when switching from symlinks to copies. (:pr:`3431`) - by :user:`gaborbernat`.
- Write xonsh prompt and path literals as ASCII escapes in every generated activation script. This preserves their
  values when xonsh reads the script with a legacy encoding such as GBK or Big5. Regenerate existing scripts to apply
  the fix. (:pr:`3432`) - by :user:`gaborbernat`.
- Keep existing redirects whose target has a non-regular configuration file, and allow ``--clear`` to recreate
  environments with such configuration paths. (:pr:`3433`) - by :user:`gaborbernat`.
- Reject invalid and archive-like seed versions while parsing options for both seeders, before creating an environment
  or looking up wheels, with an error naming the invalid value. Apply the same validation to versions obtained from
  wheel filenames. (:pr:`3434`) - by :user:`gaborbernat`.
- Skip writing ``.venv`` redirects for environment names with leading or trailing whitespace, which redirect readers may
  strip. (:pr:`3435`) - by :user:`gaborbernat`.

.. _release-21-14-9-documentation:

Documentation
-------------

- Document the accepted boolean values and environment-only scope of ``VIRTUALENV_PERIODIC_UPDATE_INSECURE``.
  (:pr:`3436`) - by :user:`gaborbernat`.

.. _release-21-14-8:

***********************
 v21.14.8 (2026-10-16)
***********************

.. _release-21-14-8-fixed:

Fixed
-----

- Activate PowerShell environments whose path contains square brackets, and read the environment's own ``pyvenv.cfg``
  instead of whichever file the path matches as a wildcard pattern - by :user:`repzakske` and :user:`gaborbernat`.
  (:pr:`3396`)

.. _release-21-14-7:

***********************
 v21.14.7 (2026-10-12)
***********************

.. _release-21-14-7-fixed:

Fixed
-----

- Escape the environment name in the bash activator for both of bash's ``PS1`` passes, so a name or ``--prompt`` value
  with a backslash before ``$(...)`` or backticks no longer runs as a command each time bash draws the prompt - by
  :user:`gaborbernat`. (:pr:`3390`)

.. _release-21-14-6:

***********************
 v21.14.6 (2026-10-08)
***********************

.. _release-21-14-6-fixed:

Fixed
-----

- Fall back to the bundled seed wheel with periodic update on (the default) when the embed update log holds JSON of the
  wrong shape, instead of downloading the wheel or, offline, failing to create the environment - by :user:`darrenhuai`
  and :user:`gaborbernat`. (:pr:`3383`)

.. _release-21-14-5:

***********************
 v21.14.5 (2026-10-02)
***********************

.. _release-21-14-5-fixed:

Fixed
-----

- Fall back to the bundled seed wheel and remove the embed update log when the log in the app data folder holds JSON of
  the wrong shape, instead of failing to create the environment - by :user:`pasmud` and :user:`gaborbernat`.
  (:pr:`3376`)

.. _release-21-14-4:

***********************
 v21.14.4 (2026-10-02)
***********************

.. _release-21-14-4-fixed:

Fixed
-----

- Fix ``activate`` running commands from a virtual environment name or ``--prompt`` that holds ``$(...)``, backticks or
  ``${...}`` when zsh has ``PROMPT_SUBST`` set, and show a ``%`` in the name as typed under zsh (`GHSA-5vjq-rrrf-7h2q
  <https://github.com/pypa/virtualenv/security/advisories/GHSA-5vjq-rrrf-7h2q>`_); reported by :user:`kemrec` and
  :user:`gaborbernat`. (:pr:`3373`)

.. _release-21-14-3:

***********************
 v21.14.3 (2026-10-01)
***********************

.. _release-21-14-3-fixed:

Fixed
-----

- Honor ``~=`` and every clause of a seed wheel's ``Requires-Python`` when picking a wheel for the target Python, and
  skip a wheel whose ``Requires-Python`` is not a valid specifier instead of failing - by :user:`pasmud` and
  :user:`gaborbernat`. (:pr:`3369`)

.. _release-21-14-2:

***********************
 v21.14.2 (2026-10-01)
***********************

.. _release-21-14-2-fixed:

Fixed
-----

- Fix ``pyvenv.cfg`` getting an absolute path in ``python-version``, ``include-system-site-packages`` and the other keys
  that hold no path when the working directory has an entry named like the value, such as ``3.14`` for ``virtualenv
  3.14`` or ``true`` with ``--system-site-packages`` - by :user:`darrenhuai` and :user:`gaborbernat`. (:pr:`3366`)
- Fix activation scripts running code from a virtual environment path whose parent directory carries a placeholder name
  such as ``__VIRTUAL_NAME__`` (`GHSA-8rjx-v5ww-45pp
  <https://github.com/pypa/virtualenv/security/advisories/GHSA-8rjx-v5ww-45pp>`_), and ``activate.fish`` running
  commands from a path or ``--prompt`` that holds a backslash before a single quote (`GHSA-c947-3pg5-gm8q
  <https://github.com/pypa/virtualenv/security/advisories/GHSA-c947-3pg5-gm8q>`_); both reported by :user:`Kwstubbs` and
  :user:`gaborbernat` of GitHub Security Lab. (:pr:`3367`)

.. _release-21-14-1:

***********************
 v21.14.1 (2026-09-29)
***********************

.. _release-21-14-0:

***********************
 v21.14.0 (2026-09-29)
***********************

.. _release-21-14-0-added:

Added
-----

- Record the SPDX license id in the wheel and zipapp SBOMs for bundled packages that declare their license by name or
  classifier, such as ``distlib`` and ``python-discovery``, so license scanners can match them. (:pr:`3339`) - by
  :user:`gaborbernat`.
- Add the Tidelift and thanks.dev funding links to the PyPI project URLs, next to GitHub Sponsors - by
  :user:`gaborbernat`. (:pr:`3340`)

.. _release-21-14-0-fixed:

Fixed
-----

- Build the release sdist, wheel and zipapp with the build backend and SBOM tools that
  ``tasks/release-requirements.txt`` pins by version and SHA-256, so a rebuild of the tag uses the same versions.
  (:pr:`3337`) - by :user:`gaborbernat`.
- Use PEP 440 version ordering when selecting seed wheels, so pinned pre-releases, post-releases and local versions
  resolve to the requested wheel. (:pr:`3361`) - by :user:`pasmud` and :user:`gaborbernat`.

.. _release-21-14-0-documentation:

Documentation
-------------

- Apply the licensing policy to what the wheel and zipapp ship, checked against their SBOMs, and name
  ``ALLOWED_LICENSES`` in ``tasks/license_policy.py`` as the list of accepted licenses. (:pr:`3339`) - by
  :user:`gaborbernat`.
- Document what a maintainer checks when reviewing a pull request and what the ``main`` ruleset requires before a merge
  - by :user:`gaborbernat`. (:pr:`3341`)
- Document how the project selects, obtains and tracks its dependencies, and which dependency findings block a merge or
  a release - by :user:`gaborbernat`. (:pr:`3342`)
- Document which static analysis findings block a merge or a release, and how maintainers suppress a finding - by
  :user:`gaborbernat`. (:pr:`3343`)
- Document which secrets the project stores, who can read them and when maintainers rotate them - by
  :user:`gaborbernat`. (:pr:`3344`)
- Update the roadmap: :PEP:`832` support shipped, and :PEP:`838` waits on the PEP - by :user:`gaborbernat`. (:pr:`3345`)

.. _release-21-13-0:

***********************
 v21.13.0 (2026-09-26)
***********************

.. _release-21-13-0-added:

Added
-----

- Add ``Changelog`` and ``Funding`` links to the PyPI project metadata, and replace the ``2020-202x`` placeholder in
  ``LICENSE`` with ``2020-present`` so the copyright field of the wheel SBOM reads as a real range - by
  :user:`gaborbernat`. (:pr:`3334`)

.. _release-21-13-0-fixed:

Fixed
-----

- Escape the curly single quotes ``U+2018``-``U+201B`` in the PowerShell activator's ``quote`` so a virtual environment
  prompt, name or Tcl/Tk library path containing them can no longer close the string literal and run commands - by
  :user:`gaborbernat`. (:pr:`3325`)
- Stop the bash activator from re-expanding the prompt inside ``PS1``, so a virtual environment name or ``--prompt``
  value containing ``$(...)``, backticks or backslashes no longer runs as a command each time bash draws the prompt - by
  :user:`gaborbernat`. (:pr:`3326`)

.. _release-21-13-0-documentation:

Documentation
-------------

- Correct the documented changelog fragment types and example to match the enforced towncrier categories.
  (:issue:`3323`) - by :user:`januththedev`.
- List the Unlicense and the SPDX BSD variants in the runtime dependency licensing policy, matching the ``filelock``
  releases virtualenv installs on Python 3.9, and describe the dependency review check that enforces the policy.
  (:pr:`3329`) - by :user:`gaborbernat`.
- Show how to check a release with ``gh release verify`` and ``gh release verify-asset``, and how to rebuild the zipapp
  byte for byte with the build tool versions its SBOMs list. Drop the claims that the zipapp build does not pin the
  distributions it bundles and that wheels differ between build machines - by :user:`gaborbernat`. (:pr:`3330`)

.. _release-21-12-1:

***********************
 v21.12.1 (2026-09-24)
***********************

.. _release-21-12-1-fixed:

Fixed
-----

- Limit the :PEP:`832` ``.venv`` redirect to folders holding a ``pyproject.toml`` and no ``.venv`` yet, so ``virtualenv
  foo`` in a scratch folder, and tools such as tox or nox building environments through virtualenv, no longer claim a
  folder's default environment - by :user:`gaborbernat`.

  - ``--venv-redirect`` writes the redirect in any folder and replaces an earlier virtualenv redirect.
  - A flag on the command line overrides the environment variable and the config file in either direction. (:pr:`3316`)

.. _release-21-12-0:

***********************
 v21.12.0 (2026-09-24)
***********************

.. _release-21-12-0-added:

Added
-----

- Write the `PEP 838 <https://peps.python.org/pep-0838/>`_ ``python-version`` key into ``pyvenv.cfg``, holding the
  target interpreter's feature release. The new :doc:`reference/files` page covers it alongside every other file a
  created environment holds - by :user:`konstin`. (:pr:`3193`)
- Point a ``.venv`` redirect file in the parent folder at the created environment, per `PEP 832
  <https://peps.python.org/pep-0832/>`_, so editors and type checkers can find it - by :user:`gaborbernat` and
  :user:`konstin`.

  - virtualenv leaves a ``.venv`` folder alone, and a redirect pointing at an environment it did not create.
  - Pass ``--no-venv-redirect`` to opt out.
  - The feature is provisional while PEP 832 is a draft: a minor or patch release may change it in backward incompatible
    ways to follow the PEP. (:pr:`3204`)

.. _release-21-11-1:

***********************
 v21.11.1 (2026-09-23)
***********************

.. _release-21-11-1-fixed:

Fixed
-----

- Include the pre-commit configuration and the zipapp lock file in the source distribution, so downstream packagers can
  run the test suite from it. (:issue:`3314`) - by :user:`Gonghan-Princess`.

.. _release-21-11-0:

***********************
 v21.11.0 (2026-09-23)
***********************

.. _release-21-11-0-added:

Added
-----

- Attach the CycloneDX SBOM and an SPDX 2.3 rendering of it (``virtualenv.cdx.json``, ``virtualenv.spdx.json``) to each
  GitHub release, and attest the SPDX document against the sdist and wheel. (:pr:`3299`) - by :user:`gaborbernat`.
- Describe the zipapp in its own CycloneDX SBOM, which lists virtualenv, the embedded pip and setuptools wheels, and
  each bundled dependency with the Python versions that load it, down to a SHA-256 per file. The SBOM sits at the root
  of ``virtualenv.pyz``, ships as the ``virtualenv.pyz.cdx.json`` release asset, and GitHub attests it against the
  zipapp. (:pr:`3310`) - by :user:`gaborbernat`.

.. _release-21-11-0-fixed:

Fixed
-----

- Refuse a seed wheel downloaded from the default index when virtualenv cannot get its sha256 from PyPI after three
  retries, instead of seeding it unverified. Seeding falls back to the bundled wheel unless a specific version was
  requested. (:pr:`3302`) - by :user:`gaborbernat`.
- Build the zipapp from the dependency wheels that ``pylock.zipapp.toml`` pins by URL and sha256, so a release bundles
  only files matching the committed hashes. (:pr:`3306`) - by :user:`gaborbernat`.
- Leave the build machine out of the wheel and zipapp SBOMs, so the wheel rebuilds byte for byte on any operating system
  and architecture given the same source, ``SOURCE_DATE_EPOCH``, Python patch version and build backend versions. Zipapp
  entries now carry the ``SOURCE_DATE_EPOCH`` timestamp and fixed permissions instead of the build time. (:pr:`3311`) -
  by :user:`gaborbernat`.

.. _release-21-11-0-documentation:

Documentation
-------------

- Document the backup maintainer and the two-factor authentication and access review expectations for maintainers.
  (:pr:`3290`) - by :user:`gaborbernat`.
- Link the Carl Meyer talk on the home page over HTTPS - by :user:`gaborbernat`. (:pr:`3300`)
- Add a roadmap to the development guide listing what the project plans to do, and not do, through September 2027 - by
  :user:`gaborbernat`. (:pr:`3304`)
- Document what a release publishes and how to verify each file, covering the PyPI attestations, the zipapp and its
  provenance, the CycloneDX and SPDX SBOMs of the wheel, the zipapp SBOM, and rebuilding the sdist from its tag.
  (:pr:`3305`) - by :user:`gaborbernat`.

.. _release-21-10-0:

***********************
 v21.10.0 (2026-09-22)
***********************

.. _release-21-10-0-added:

Added
-----

- Include versioned identities for packages vendored inside seed wheels in the embedded SBOM. (:pr:`3281`) - by
  :user:`gaborbernat`.
- Allow ``filelock`` 4.x on Python 3.10+ by relaxing the upper bound from ``<4`` to ``<5`` - by :user:`r3wretrhy`.
  (:issue:`3285`)

.. _release-21-10-0-fixed:

Fixed
-----

- Skip Windows batch activation scripts when environment or Tcl/Tk paths contain ``^`` or ``!``, since quoting changes
  those paths. Other activation scripts remain available. (:pr:`3280`) - by :user:`gaborbernat`.

.. _release-21-9-1:

**********************
 v21.9.1 (2026-09-22)
**********************

.. _release-21-9-1-fixed:

Fixed
-----

- Correct SBOM CSV parsing and unresolved dependency relationships, and omit CI run identifiers from reproducible
  builds. (:pr:`3278`) - by :user:`gaborbernat`.

.. _release-21-9-0:

**********************
 v21.9.0 (2026-09-20)
**********************

.. _release-21-9-0-added:

Added
-----

- The embedded SBOM now describes the root component's license, copyright, maintainers and project links, each bundled
  wheel from its own metadata, the declared runtime dependencies, and the full build environment (interpreter, OS and
  every distribution in the isolated build environment with the dependency graph between them), plus the GitHub Actions
  run when built there. (:pr:`3270`) - by :user:`gaborbernat`.

.. _release-21-9-0-fixed:

Fixed
-----

- Add ``metadata.timestamp`` (derived from ``SOURCE_DATE_EPOCH`` for reproducibility) and ``metadata.tools`` naming the
  generator to the embedded SBOM, and validate both fields in the packaging checks that already run on every pull
  request. (:pr:`3269`) - by :user:`gaborbernat`.
- Fix the embedded SBOM not conforming to the CycloneDX 1.6 schema (an invalid ``vendor`` key on the generator tool
  entry) and validate it against the schema in CI. (:pr:`3270`) - by :user:`gaborbernat`.

.. _release-21-8-1:

**********************
 v21.8.1 (2026-09-19)
**********************

.. _release-21-8-1-fixed:

Fixed
-----

- Make the embedded SBOM's ``serialNumber`` a deterministic UUID derived from the package name, version and bundled
  wheel hashes, so the same source tree produces a byte-identical SBOM, and validate the SBOM's structure as part of the
  packaging checks that already run on every pull request. (:pr:`3268`) - by :user:`gaborbernat`.

.. _release-21-8-0:

**********************
 v21.8.0 (2026-09-19)
**********************

.. _release-21-8-0-added:

Added
-----

- Every published wheel now carries a `CycloneDX <https://cyclonedx.org/>`_ SBOM at
  ``.dist-info/sboms/virtualenv.cdx.json`` (:PEP:`770`), declaring the bundled ``pip`` and ``setuptools`` wheels that
  generic SBOM tools cannot see on their own. GitHub attests it against the released sdist and wheel. (:pr:`3265`) - by
  :user:`gaborbernat`.

.. _release-21-7-16:

***********************
 v21.7.16 (2026-09-19)
***********************

.. _release-21-7-16-fixed:

Fixed
-----

- Fix ``activate.csh`` rendering the venv's prompt text wrong when it contains ``!`` (csh and tcsh both expand it) or
  ``%`` (tcsh only, since plain csh has no ``%`` prompt escape at all). (:pr:`3263`) - by :user:`gaborbernat`.

.. _release-21-7-15:

***********************
 v21.7.15 (2026-09-18)
***********************

.. _release-21-7-15-fixed:

Fixed
-----

- Restore an empty ``PATH`` on ``deactivate`` in the bash and fish activators, and stop bash leaving the prompt in
  ``PS1`` when it was unset before activation. (:pr:`3259`) - by :user:`gaborbernat`.
- Fix ``activate.csh`` failing to restore ``PATH`` and other saved variables on ``deactivate`` when ``PATH`` was already
  empty. (:pr:`3260`) - by :user:`gaborbernat`.

.. _release-21-7-14:

***********************
 v21.7.14 (2026-09-18)
***********************

.. _release-21-7-14-fixed:

Fixed
-----

- Fix ``activate.csh`` failing with ``Event not found`` when the virtual environment path contains ``!``. (:pr:`3256`) -
  by :user:`gaborbernat`.

.. _release-21-7-13:

***********************
 v21.7.13 (2026-09-18)
***********************

.. _release-21-7-13-fixed:

Fixed
-----

- Fix ``activate`` and ``activate.fish`` running commands embedded in the virtual environment path or in the
  interpreter's Tcl/Tk library paths. (:pr:`3252`) - by :user:`gaborbernat`.

.. _release-21-7-12:

***********************
 v21.7.12 (2026-09-18)
***********************

.. _release-21-7-12-fixed:

Fixed
-----

- Fix ``activate.bat`` running arbitrary commands from a crafted ``--prompt``, ``VIRTUALENV_PROMPT``, or config file
  value. (:pr:`3250`) - by :user:`gaborbernat`.
- Verify a downloaded seed wheel's sha256 against PyPI before seeding it into a virtual environment, skipped when a
  custom pip index is configured. (:pr:`3251`) - by :user:`gaborbernat`.

.. _release-21-7-11:

***********************
 v21.7.11 (2026-09-17)
***********************

.. _release-21-7-11-fixed:

Fixed
-----

- Running ``activate.bat`` again before ``deactivate`` no longer makes ``deactivate`` leave the environment's
  ``PKG_CONFIG_PATH``, ``TCL_LIBRARY`` and ``TK_LIBRARY`` behind, or lose values the user had set before the first
  activation - by :user:`darrenhuai`. (:pr:`3245`)
- Write ``pyvenv.cfg`` values on a single line, so a prompt carrying a line boundary can no longer inject configuration.
  ``--prompt``, the ``VIRTUALENV_PROMPT`` environment variable and the config file all set the prompt, and
  ``pyvenv.cfg`` has no escape syntax, so a newline, a carriage return, or any other boundary ``str.splitlines``
  recognizes, such as ``U+2028``, started a new configuration line. Reading the file back picked up those lines as keys,
  and since the last value for a key wins, they replaced anything written earlier, including ``home``. (:pr:`3247`) - by
  :user:`gaborbernat`.

.. _release-21-7-11-documentation:

Documentation
-------------

- Document the policy for AI-assisted contributions and the licensing rules for dependencies. (:pr:`3239`) - by
  :user:`gaborbernat`.

.. _release-21-7-10:

***********************
 v21.7.10 (2026-09-15)
***********************

.. _release-21-7-10-fixed:

Fixed
-----

- Skip blank lines, ``#`` comments and lines without ``=`` in ``pyvenv.cfg`` instead of raising ``ValueError`` - by
  :user:`r3wretrhy` and :user:`gaborbernat`. (:pr:`3232`)
- ``deactivate`` in bash, fish and PowerShell unsets ``PKG_CONFIG_PATH`` when activation found it unset, instead of
  keeping the environment's ``lib/pkgconfig``. csh activation no longer drops a ``PKG_CONFIG_PATH`` the user had set.
  Activation in batch, fish, nushell and PowerShell no longer adds a trailing separator when ``PKG_CONFIG_PATH`` is
  unset, and PowerShell and nushell build the value with the host's path separators - by :user:`darrenhuai` and
  :user:`gaborbernat`. (:pr:`3233`)
- Activation in bash, csh, fish and PowerShell keeps the user's ``TCL_LIBRARY`` and ``TK_LIBRARY``, and ``deactivate``
  restores them. csh and PowerShell removed both variables on every activation, fish did so when the interpreter has
  tcl, and bash kept the environment's value after ``deactivate`` when the variable was unset before - by
  :user:`darrenhuai` and :user:`gaborbernat`. (:pr:`3234`)

.. _release-21-7-9:

**********************
 v21.7.9 (2026-09-09)
**********************

.. _release-21-7-9-fixed:

Fixed
-----

- Replace dangling symlinks, including interpreter aliases, when recreating an environment. This prevents
  ``FileExistsError`` with ``--symlinks`` and writes outside the environment with ``--copies`` - by :user:`darrenhuai`
  and :user:`gaborbernat`. (:pr:`3229`)
- Ignore malformed or unreadable ``virtualenv.ini`` files and report the error in the log and ``--help``. Accept a UTF-8
  byte order mark, as written by PowerShell 5 and older Notepad versions - by :user:`darrenhuai` and
  :user:`gaborbernat`. (:pr:`3230`)

.. _release-21-7-8:

**********************
 v21.7.8 (2026-09-01)
**********************

.. _release-21-7-8-fixed:

Fixed
-----

- A missing source needed by both install modes now disables the builtin creator through ``meta.error``. The check
  compared ``RefWhen`` values against ``RefMust`` members, so creation went on to fail with a ``FileNotFoundError`` or a
  dangling symlink - by :user:`darrenhuai`. (:pr:`3227`)

.. _release-21-7-7:

**********************
 v21.7.7 (2026-08-28)
**********************

.. _release-21-7-7-fixed:

Fixed
-----

- Bump the ``python-discovery`` minimum to ``>=1.6`` for ``PythonInfo.system_exe``, which reports the system interpreter
  without the nullable typing of ``system_executable`` - by :user:`gaborbernat`. (:pr:`3224`)

.. _release-21-7-7-documentation:

Documentation
-------------

- Document the names the interpreter answers to inside a created environment. A new :doc:`reference/environment-layout`
  page lists them per platform, the tutorial and the usage guide point at it, and the explanation of creators covers why
  an environment carries several names and why Windows copies a redirector - by :user:`gaborbernat`. (:pr:`3225`)

.. _release-21-7-6:

**********************
 v21.7.6 (2026-08-28)
**********************

.. _release-21-7-6-fixed:

Fixed
-----

- On Windows, ``virtualenv`` no longer copies the CPython 3.13+ ``venvlauncher.exe`` shim into ``Scripts`` under the
  shim's own name, and a host such as ``python_d.exe`` gets its alias back. The alias set took its names from the shim
  that stands in for the interpreter, so every environment gained a stray launcher copy and lost the interpreter's own
  file name - by :user:`darrenhuai` and :user:`gaborbernat`. (:pr:`3223`)

.. _release-21-7-5:

**********************
 v21.7.5 (2026-08-25)
**********************

.. _release-21-7-5-fixed:

Fixed
-----

- Fix the type check against ``python-discovery`` 1.5.2, whose annotations allow a ``None`` ``prefix`` and integer
  ``sysconfig_vars`` values: config var substitution now skips a missing prefix and locating the shared libpython
  requires string ``INSTSONAME``/``LIBDIR`` values. (:pr:`3211`) - by :user:`gaborbernat`.
- ``ExePathRef.can_run`` now checks the group and other execute bits instead of only the owner one, and returns
  ``False`` rather than ``None`` when a file carries none of the three - by :user:`darrenhuai` and :user:`gaborbernat`.
  (:pr:`3217`)
- ``safe_delete`` no longer passes ``ignore_errors=True`` to ``shutil.rmtree``, which replaced its own chmod-and-retry
  handler with a no-op and swallowed every failure. Read-only files - every file in a wheel image, which ``set_tree``
  marks - survived, so ``--reset-app-data`` and ``--clear`` kept trees they reported deleting. The handler now retries
  only the deletion itself, keeps the other mode bits, and raises the original error for anything it cannot clear - by
  :user:`darrenhuai` and :user:`gaborbernat`. (:pr:`3222`)

.. _release-21-7-4:

**********************
 v21.7.4 (2026-08-10)
**********************

.. _release-21-7-4-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``84.0.0`` from ``83.0.0`` (:pr:`3208`) - by :user:`gaborbernat`.

.. _release-21-7-3:

**********************
 v21.7.3 (2026-08-08)
**********************

.. _release-21-7-3-fixed:

Fixed
-----

- ``ListType.split_values`` now returns a ``list`` you can iterate more than once, and accepts ``bytes`` input instead
  of raising ``TypeError`` - by :user:`darrenhuai` and :user:`gaborbernat`. (:pr:`3207`)

.. _release-21-7-2:

**********************
 v21.7.2 (2026-08-07)
**********************

.. _release-21-7-2-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``26.2.1`` from ``26.2`` (:pr:`3206`) - by :user:`gaborbernat`.

.. _release-21-7-1:

**********************
 v21.7.1 (2026-07-30)
**********************

.. _release-21-7-1-documentation:

Documentation
-------------

- Document that ``virtualenv.png`` is the official logo and ``virtualenv.svg`` is a simplified favicon-only mark - by
  :user:`gaborbernat`. (:issue:`3199`)

.. _release-21-7-1-packaging:

Packaging
---------

- Upgrade the embedded pip wheel from ``26.1.2`` to ``26.2``.

.. _release-21-7-0:

**********************
 v21.7.0 (2026-07-21)
**********************

.. _release-21-7-0-added:

Added
-----

- Declare support for Python 3.15: CI now tests against the CPython 3.15 beta, including the free-threaded ``3.15t``
  build, and the ``Programming Language :: Python :: 3.15`` classifier is advertised. (:pr:`3192`) - by
  :user:`gaborbernat`.

.. _release-21-6-1:

**********************
 v21.6.1 (2026-07-10)
**********************

.. _release-21-6-1-fixed:

Fixed
-----

- Harden the fish activator prompt against user functions that shadow builtins. Routing ``functions``, ``printf``,
  ``string``, ``echo`` and ``source``/``.`` through ``builtin`` stops a shadowing function (such as a dot-style
  directory navigator that redefines ``.``) from hijacking the prompt and dropping the previous command's exit status,
  matching the CPython fix in `gh-140006 <https://github.com/python/cpython/issues/140006>`_. (:pr:`3185`) - by
  :user:`gaborbernat`.

.. _release-21-6-0:

**********************
 v21.6.0 (2026-07-06)
**********************

.. _release-21-6-0-added:

Added
-----

- Stop installing the ``_virtualenv.{py,pth}`` distutils import hook for Python 3.10 and later, where pip, setuptools
  and CPython already ignore the install config keys it guards against; this removes the hook's startup import cost. The
  hook is still installed for Python 3.9. (:issue:`3181`) - by :user:`gaborbernat`.

.. _release-21-5-2:

**********************
 v21.5.2 (2026-07-06)
**********************

.. _release-21-5-2-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``83.0.0`` (:pr:`3180`) - by :user:`gaborbernat`.

.. _release-21-5-1:

**********************
 v21.5.1 (2026-06-16)
**********************

.. _release-21-5-1-fixed:

Fixed
-----

- Refuse to create environments whose Python the bundled wheels no longer cover (currently below 3.9). virtualenv used
  to substitute the newest bundled ``pip``, which cannot run on such a target, leaving a broken environment; seeder
  selection now rejects it up front with a clear error. ``--no-seed`` and third-party seeders that ship compatible
  wheels still work - by :user:`gaborbernat`. (:issue:`3171`)

.. _release-21-5-0:

**********************
 v21.5.0 (2026-06-13)
**********************

.. _release-21-5-0-added:

Added
-----

- Drop support for Python 3.8; virtualenv now requires Python 3.9 or later to run and to create environments. Remove the
  embedded ``wheel`` seed package, which virtualenv bundled only for Python 3.8. The ``--wheel`` and ``--no-wheel``
  options stay as no-ops, but now warn that virtualenv will remove them in a release after 2026-12 - by
  :user:`gaborbernat`. (:pr:`3170`)

.. _release-21-5-0-packaging:

Packaging
---------

- Remove the embedded ``wheel`` package at version ``0.47.0`` - by :user:`gaborbernat`.

.. _release-21-4-3:

**********************
 v21.4.3 (2026-06-11)
**********************

.. _release-21-4-3-fixed:

Fixed
-----

- Resolve executable-only symlinks when recording ``home`` and ``base-executable`` in ``pyvenv.cfg``, mirroring
  CPython's ``getpath.realpath`` (python/cpython#115237), so environments created from a symlink to the interpreter
  binary locate the base stdlib (for example python-build-standalone); a fully symlinked interpreter tree is kept as-is
  - by :user:`gaborbernat`. (:issue:`3157`)
- Stop exporting ``PS1`` from the bash activator so child processes do not inherit shell prompt state. (:issue:`3158`) -
  by :user:`karlhillx`.
- Handle CYGWIN/MSYS/MINGW path conversions in fish activation script - by :user:`LuNoX`. (:issue:`3160`)

.. _release-21-4-3-packaging:

Packaging
---------

- Upgrade the embedded pip wheel from ``26.1.1`` to ``26.1.2``.

.. _release-21-4-2:

**********************
 v21.4.2 (2026-05-31)
**********************

.. _release-21-4-2-fixed:

Fixed
-----

- Stop ``deactivate`` in the bash/zsh activation script from aborting under ``set -e`` when ``hash -r`` fails (for
  example with shell hashing disabled) by appending ``|| true``, matching CPython ``venv`` (gh-149701) and the existing
  non-deactivate call - by :user:`gaborbernat`. (:pr:`3152`)

.. _release-21-4-1:

**********************
 v21.4.1 (2026-05-28)
**********************

.. _release-21-4-1-fixed:

Fixed
-----

- Fix Windows debug build ``venvlauncher_d.exe`` substitution never triggering because ``executables()`` compared the
  source executable name instead of the target name, and fix ``AttributeError`` on ``debug_build`` attribute for
  interpreter info objects missing the field - by :user:`gaborbernat`. (:pr:`3151`)

.. _release-21-4-0:

**********************
 v21.4.0 (2026-05-28)
**********************

.. _release-21-4-0-added:

Added
-----

- Support Windows debug builds (``python_d.exe``, ``venvlauncher_d.exe``) matching CPython venv behavior, remove dead
  ``__SCRIPT_DIR__`` replacement and ``has_shim`` version guard, drop unreachable Python 3.7 branch from
  ``pyvenv_launch_patch_active``, and fix wheel deprecation message to say ``>= 3.9`` - by :user:`gaborbernat`.
  (:pr:`3150`)

.. _release-21-3-3:

**********************
 v21.3.3 (2026-05-13)
**********************

.. _release-21-3-3-fixed:

Fixed
-----

- recognize GraalPy interpreters using the normalized ``GraalPy`` name - by :user:`timfel`. (:pr:`3144`)

.. _release-21-3-2:

**********************
 v21.3.2 (2026-05-12)
**********************

.. _release-21-3-1:

**********************
 v21.3.1 (2026-05-05)
**********************

.. _release-21-3-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``26.1.1`` from ``26.1`` (:pr:`3138`) - by :user:`gaborbernat`.

.. _release-21-3-0:

**********************
 v21.3.0 (2026-04-27)
**********************

.. _release-21-3-0-added:

Added
-----

- Re-introduce ``xonsh`` shell activator (``activate.xsh``) previously removed in 20.7.0, and make the plugin loader
  prefer virtualenv's built-in entry points so a third-party package cannot override them by registering a duplicate
  name. (:issue:`3003`) - by :user:`anki-code`.

.. _release-21-3-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``26.1`` (:pr:`3132`) - by :user:`gaborbernat`.

.. _release-21-2-4:

**********************
 v21.2.4 (2026-04-14)
**********************

.. _release-21-2-4-security:

Security
--------

- Security hardening: validate each entry of a seed wheel archive before extracting it so a tampered wheel cannot escape
  the app-data image directory via an absolute path or ``..`` traversal. (:pr:`3118`) - by :user:`gaborbernat`.
- Security hardening: verify the SHA-256 of every bundled seed wheel when it is loaded so a corrupted or tampered file
  on disk fails loud instead of being handed to pip. The hash table is generated alongside ``BUNDLE_SUPPORT`` by
  ``tasks/upgrade_wheels.py``. (:pr:`3119`) - by :user:`gaborbernat`.
- Security hardening: validate the distribution name and version specifier passed to ``pip download`` when acquiring a
  seed wheel so extras, pip flags, or shell metacharacters cannot be smuggled into the subprocess command line.
  (:pr:`3120`) - by :user:`gaborbernat`.
- Security hardening: replace the string-prefix containment check in ``virtualenv.util.zipapp`` with
  ``Path.relative_to`` so the zipapp extraction helpers refuse any path that does not resolve under the archive root.
  (:pr:`3121`) - by :user:`gaborbernat`.
- Security hardening: do not silently fall back to an unverified HTTPS context when the periodic update request to PyPI
  fails TLS verification. The returned metadata drives which wheel version virtualenv considers "up to date", so
  accepting an unverified response lets a network-level attacker suppress security updates. Set
  ``VIRTUALENV_PERIODIC_UPDATE_INSECURE=1`` to restore the previous behavior on hosts with broken trust stores.
  (:pr:`3122`) - by :user:`gaborbernat`.

.. _release-21-2-3:

**********************
 v21.2.3 (2026-04-14)
**********************

.. _release-21-2-2:

**********************
 v21.2.2 (2026-04-13)
**********************

.. _release-21-2-2-fixed:

Fixed
-----

- Bump ``python-discovery`` minimum to ``>=1.2.2`` to include ``normalize_isa`` support - by :user:`rahuldevikar`.
  (:pr:`3117`)

.. _release-21-2-1:

**********************
 v21.2.1 (2026-04-09)
**********************

.. _release-21-2-1-fixed:

Fixed
-----

- Use terminal width for help formatting instead of hardcoded 240. (:pr:`3110`) - by :user:`Bahtya`.

.. _release-21-2-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``82.0.1`` from ``82.0.0`` (:pr:`3093`) - by :user:`gaborbernat`.

.. _release-21-2-0:

**********************
 v21.2.0 (2026-03-09)
**********************

.. _release-21-2-0-fixed:

Fixed
-----

- Pass ``--without-scm-ignore-files`` to subprocess venv on Python 3.13+ so virtualenv controls ``.gitignore`` creation,
  fixing flaky ``test_create_no_seed`` and ``--no-vcs-ignore`` being ignored in subprocess path - by
  :user:`gaborbernat`. (:issue:`3089`)
- Use ``BASH_SOURCE[0]`` instead of ``$0`` in the bash activate script relocation fallback, fixing incorrect ``PATH``
  when sourcing the activate script from a different directory - by :user:`gaborbernat`. (:issue:`3090`)

.. _release-21-1-0:

**********************
 v21.1.0 (2026-02-27)
**********************

.. _release-21-1-0-added:

Added
-----

- Add comprehensive type annotations across the entire codebase and ship a PEP 561 ``py.typed`` marker so downstream
  consumers and type checkers recognize virtualenv as an inline-typed package - by :user:`rahuldevikar`. (:issue:`3075`)

.. _release-21-0-0:

**********************
 v21.0.0 (2026-02-25)
**********************

.. _release-21-0-0-changes:

Changes
-------

- The Python discovery logic has been extracted into a standalone ``python-discovery`` package on PyPI (`documentation
  <https://python-discovery.readthedocs.io/>`_) and is now consumed as a dependency. If you previously imported
  discovery internals directly (e.g. ``from virtualenv.discovery.py_info import PythonInfo``), switch to ``from
  python_discovery import PythonInfo``. Backward-compatibility re-export shims are provided at
  ``virtualenv.discovery.py_info``, ``virtualenv.discovery.py_spec``, and ``virtualenv.discovery.cached_py_info``,
  however these are considered unsupported and may be removed in a future release - by :user:`gaborbernat`. (:pr:`3070`)

.. _release-20-39-1:

***********************
 v20.39.1 (2026-02-25)
***********************

.. _release-20-39-1-added:

Added
-----

- Add support for creating virtual environments with RustPython - by :user:`elmjag`. (:pr:`3010`)

.. _release-20-39-0:

***********************
 v20.39.0 (2026-02-23)
***********************

.. _release-20-39-0-added:

Added
-----

- Automatically resolve version manager shims (pyenv, mise, asdf) to the real Python binary during discovery, preventing
  incorrect interpreter selection when shims are on ``PATH`` - by :user:`gaborbernat`. (:issue:`3049`)
- Add architecture (ISA) awareness to Python discovery — users can now specify a CPU architecture suffix in the
  ``--python`` spec string (e.g. ``cpython3.12-64-arm64``) to distinguish between interpreters that share the same
  version and bitness but target different architectures. Uses ``sysconfig.get_platform()`` as the data source, with
  cross-platform normalization (``amd64`` ↔ ``x86_64``, ``aarch64`` ↔ ``arm64``). Omitting the suffix preserves existing
  behavior - by :user:`rahuldevikar`. (:issue:`3059`)

.. _release-20-38-0:

***********************
 v20.38.0 (2026-02-19)
***********************

.. _release-20-38-0-added:

Added
-----

- Store app data (pip/setuptools/wheel caches) under the OS cache directory (``platformdirs.user_cache_dir``) instead of
  the data directory (``platformdirs.user_data_dir``). Existing app data at the old location is automatically migrated
  on first use. This ensures cached files that can be redownloaded are placed in the standard cache location (e.g.
  ``~/.cache`` on Linux, ``~/Library/Caches`` on macOS) where they are excluded from backups and can be cleaned by
  system tools - by :user:`rahuldevikar`. (:issue:`1884`) (:issue:`1884`)
- Add ``PKG_CONFIG_PATH`` environment variable support to all activation scripts (Bash, Batch, PowerShell, Fish, C
  Shell, Nushell, and Python). The virtualenv's ``lib/pkgconfig`` directory is now automatically prepended to
  ``PKG_CONFIG_PATH`` on activation and restored on deactivation, enabling packages that use ``pkg-config`` during
  build/install to find their configuration files - by :user:`rahuldevikar`. (:issue:`2637`)
- Replace ``ty: ignore`` comments with proper type narrowing using assertions and explicit None checks - by
  :user:`rahuldevikar`. (:issue:`3029`)

.. _release-20-38-0-fixed:

Fixed
-----

- Exclude pywin32 DLLs (``pywintypes*.dll``, ``pythoncom*.dll``) from being copied to the Scripts directory during
  virtualenv creation on Windows. This fixes compatibility issues with pywin32, which expects its DLLs to be installed
  in ``site-packages/pywin32_system32`` by its own post-install script - by :user:`rahuldevikar`. (:issue:`2662`)
- Preserve symlinks in ``pyvenv.cfg`` paths to match ``venv`` behavior. Use ``os.path.abspath()`` instead of
  ``os.path.realpath()`` to normalize paths without resolving symlinks, fixing issues with Python installations accessed
  via symlinked directories (common in network-mounted filesystems) - by :user:`rahuldevikar`. Fixes :issue:`2770`.
  (:issue:`2770`)
- Fix Windows activation scripts to properly quote ``python.exe`` path, preventing failures when Python is installed in
  a path with spaces (e.g., ``C:\Program Files``) and a file named ``C:\Program`` exists on the filesystem - by
  :user:`rahuldevikar`. (:issue:`2985`)
- Fix ``bash -u`` (``set -o nounset``) compatibility in bash activation script by using ``${PKG_CONFIG_PATH:-}`` and
  ``${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}`` to handle unset ``PKG_CONFIG_PATH`` - by :user:`Fridayai700`.
  (:issue:`3044`)
- Gracefully handle corrupted on-disk cache and invalid JSON from Python interrogation subprocess instead of crashing
  with unhandled ``JSONDecodeError`` or ``KeyError`` - by :user:`gaborbernat`. (:pr:`3054`)

.. _release-20-38-0-packaging:

Packaging
---------

- Upgrade embedded pip to ``26.0.1`` from ``25.3`` and setuptools to ``82.0.0``, ``75.3.4`` from ``75.3.2``, ``80.9.0``
  - by :user:`rahuldevikar`. (:issue:`3027`)

.. _release-20-36-1:

***********************
 v20.36.1 (2026-01-09)
***********************

.. _release-20-36-1-fixed:

Fixed
-----

- Fix TOCTOU vulnerabilities in app_data and lock directory creation that could be exploited via symlink attacks -
  reported by :user:`tsigouris007`, fixed by :user:`gaborbernat`. (:pr:`3013`)

.. _release-20-36-0:

***********************
 v20.36.0 (2026-01-07)
***********************

.. _release-20-36-0-added:

Added
-----

- Add support for PEP 440 version specifiers in the ``--python`` flag. Users can now specify Python versions using
  operators like ``>=``, ``<=``, ``~=``, etc. For example: ``virtualenv --python=">=3.12" myenv``. (:issue:`2994`) - by
  :user:`rahuldevikar`.

.. _release-20-35-4:

***********************
 v20.35.4 (2025-10-28)
***********************

.. _release-20-35-4-fixed:

Fixed
-----

- Fix race condition in ``_virtualenv.py`` when file is overwritten during import, preventing ``NameError`` when
  ``_DISTUTILS_PATCH`` is accessed - by :user:`gracetyy`. (:issue:`2969`)

.. _release-20-35-4-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``25.3`` from ``25.2`` (:pr:`2989`) - by :user:`gaborbernat`.

.. _release-20-35-3:

***********************
 v20.35.3 (2025-10-10)
***********************

.. _release-20-35-3-fixed:

Fixed
-----

- Accept RuntimeError in `test_too_many_open_files`, by :user:`esafak` (:issue:`2935`)

.. _release-20-35-2:

***********************
 v20.35.2 (2025-10-10)
***********************

.. _release-20-35-2-fixed:

Fixed
-----

- Revert out changes related to the extraction of the discovery module - by :user:`gaborbernat`. (:pr:`2978`)

.. _release-20-35-1:

***********************
 v20.35.1 (2025-10-09)
***********************

.. _release-20-35-1-fixed:

Fixed
-----

- Patch get_interpreter to handle missing cache and app_data - by :user:`esafak` (:issue:`2972`)
- Fix backwards incompatible changes to ``PythonInfo`` - by :user:`gaborbernat`. (:pr:`2975`)

.. _release-20-35-0:

***********************
 v20.35.0 (2025-10-08)
***********************

.. _release-20-35-0-added:

Added
-----

- Add AppData and Cache protocols to discovery for decoupling - by :user:`esafak`. (:issue:`2074`)
- Ensure python3.exe and python3 on Windows for Python 3 - by :user:`esafak`. (:issue:`2774`)

.. _release-20-35-0-fixed:

Fixed
-----

- Replaced direct references to tcl/tk library paths with getattr - by :user:`esafak` (:issue:`2944`)
- Restore absolute import of fs_is_case_sensitive - by :user:`esafak`. (:issue:`2955`)

.. _release-20-34-0:

***********************
 v20.34.0 (2025-08-13)
***********************

.. _release-20-34-0-added:

Added
-----

- Add PyPy 3.11 support. Contributed by :user:`esafak`. (:issue:`2932`)

.. _release-20-34-0-fixed:

Fixed
-----

- Accept RuntimeError in `test_too_many_open_files`, by :user:`esafak` (:issue:`2935`)
- Python in PATH takes precedence over uv-managed python. Contributed by :user:`edgarrmondragon`. (:pr:`2952`)

.. _release-20-34-0-packaging:

Packaging
---------

- Upgrade embedded wheel pip to ``25.2`` from ``25.1.1`` - by :user:`gaborbernat`. (:issue:`2333`)

.. _release-20-33-1:

***********************
 v20.33.1 (2025-08-05)
***********************

.. _release-20-33-1-fixed:

Fixed
-----

- Correctly unpack _get_tcl_tk_libs() response in PythonInfo. Contributed by :user:`esafak`. (:issue:`2930`)
- Restore `py_info.py` timestamp in `test_py_info_cache_invalidation_on_py_info_change` Contributed by :user:`esafak`.
  (:issue:`2933`)

.. _release-20-33-0:

***********************
 v20.33.0 (2025-08-03)
***********************

.. _release-20-33-0-added:

Added
-----

- Added support for Tcl and Tkinter. You're welcome. Contributed by :user:`esafak`. (:issue:`425`)

.. _release-20-33-0-fixed:

Fixed
-----

- Fix cache invalidation for PythonInfo by hashing `py_info.py`. Contributed by :user:`esafak`. (:issue:`2467`)
- When no discovery plugins are found, the application would crash with a StopIteration. This change catches the
  StopIteration and raises a RuntimeError with a more informative message. Contributed by :user:`esafak`.
  (:issue:`2493`)
- Stop `--try-first-with` overriding absolute `--python` paths. Contributed by :user:`esafak`. (:issue:`2659`)
- Force UTF-8 encoding for pip download Contributed by :user:`esafak`. (:issue:`2780`)
- Creating a virtual environment on a filesystem without symlink-support would fail even with `--copies` Make
  `fs_supports_symlink` perform a real symlink creation check on all platforms. Contributed by :user:`esafak`.
  (:issue:`2786`)
- Add a note to the user guide recommending the use of a specific Python version when creating virtual environments.
  Contributed by :user:`esafak`. (:issue:`2808`)
- Fix 'Too many open files' error due to a file descriptor leak in virtualenv's locking mechanism. Contributed by
  :user:`esafak`. (:issue:`2834`)
- Support renamed Windows venv redirector (`venvlauncher.exe` and `venvwlauncher.exe`) on Python 3.13 Contributed by
  :user:`esafak`. (:issue:`2851`)
- Resolve Nushell activation script deprecation warnings by dynamically selecting the ``--optional`` flag for Nushell
  ``get`` command on version 0.106.0 and newer, while retaining the deprecated ``-i`` flag for older versions to
  maintain compatibility. Contributed by :user:`gaborbernat`. (:pr:`2910`)

.. _release-20-32-0:

***********************
 v20.32.0 (2025-07-20)
***********************

.. _release-20-32-0-added:

Added
-----

- Warn on incorrect invocation of the Nushell activation script - by :user:`esafak`.
- Discover uv-managed Python installations (:issue:`2901`) - by :user:`edgarrmondragon`.

.. _release-20-32-0-fixed:

Fixed
-----

- Ignore missing absolute paths for python discovery - by :user:`esafak` (:issue:`2870`)

.. _release-20-32-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``80.9.0`` from ``80.3.1`` - by :user:`gaborbernat`. (:pr:`2900`)

.. _release-20-31-2:

***********************
 v20.31.2 (2025-05-08)
***********************

.. _release-20-31-1:

***********************
 v20.31.1 (2025-05-05)
***********************

.. _release-20-31-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``25.1.1`` from ``25.1``
  - setuptools to ``80.3.1`` from ``78.1.0`` (:pr:`2880`) - by :user:`gaborbernat`.

.. _release-20-31-0:

***********************
 v20.31.0 (2025-05-05)
***********************

.. _release-20-31-0-added:

Added
-----

- No longer bundle ``wheel`` wheels (except on Python 3.8), ``setuptools`` includes native ``bdist_wheel`` support.
  Update ``pip`` to ``25.1``. (:pr:`2868`) - by :user:`stefanor`.

.. _release-20-31-0-fixed:

Fixed
-----

- ``get_embed_wheel()`` no longer fails with a :exc:`TypeError` when it is called with an unknown *distribution*.
  (:pr:`2877`) - by :user:`tiran`.
- Fix ``HelpFormatter`` error with Python 3.14.0b1. (:pr:`2878`) - by :user:`cdce8p`.

.. _release-20-30-0:

***********************
 v20.30.0 (2025-03-31)
***********************

.. _release-20-30-0-added:

Added
-----

- Add support for `GraalPy <https://github.com/oracle/graalpython>`_. (:pr:`2832`) - by :user:`msimacek`.

.. _release-20-30-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``78.1.0`` from ``75.3.2`` (:pr:`2863`) - by :user:`gaborbernat`.

.. _release-20-29-3:

***********************
 v20.29.3 (2025-03-06)
***********************

.. _release-20-29-3-fixed:

Fixed
-----

- Ignore unreadable directories in ``PATH``. (:issue:`2794`) - by :user:`barneygale`.

.. _release-20-29-2:

***********************
 v20.29.2 (2025-02-10)
***********************

.. _release-20-29-2-fixed:

Fixed
-----

- Remove old virtualenv wheel from the source distribution - by :user:`gaborbernat`. (:issue:`2841`)

.. _release-20-29-2-packaging:

Packaging
---------

- Upgrade embedded wheel pip to ``25.0.1`` from ``24.3.1`` - by :user:`gaborbernat`. (:pr:`2843`)

.. _release-20-29-1:

***********************
 v20.29.1 (2025-01-17)
***********************

.. _release-20-29-1-fixed:

Fixed
-----

- Fix PyInfo cache incompatibility warnings - by :user:`robsdedude`. (:pr:`2827`)

.. _release-20-29-0:

***********************
 v20.29.0 (2025-01-15)
***********************

.. _release-20-29-0-added:

Added
-----

- Add support for selecting free-threaded Python interpreters, e.g., `python3.13t`. (:pr:`2809`) - by :user:`robsdedude`
  and :user:`gaborbernat`.

.. _release-20-29-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``75.8.0`` from ``75.6.0`` (:pr:`2823`) - by :user:`gaborbernat`.

.. _release-20-28-1:

***********************
 v20.28.1 (2025-01-02)
***********************

.. _release-20-28-1-fixed:

Fixed
-----

- Skip tcsh tests on broken tcsh versions - by :user:`gaborbernat`. (:issue:`2814`)

.. _release-20-28-0:

***********************
 v20.28.0 (2024-11-25)
***********************

.. _release-20-28-0-added:

Added
-----

- Write CACHEDIR.TAG file on creation (:pr:`2803`) - by :user:`neilramsay` and :user:`gaborbernat`.

.. _release-20-27-2:

***********************
 v20.27.2 (2024-11-25)
***********************

.. _release-20-27-2-fixed:

Fixed
-----

- no longer forcibly echo off during windows batch activation (:pr:`2801`) - by :user:`wiktorinox` and
  :user:`gaborbernat`.

.. _release-20-27-2-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``75.3.0`` from ``75.2.0`` (:pr:`2798`) - by :user:`gaborbernat`.

- Upgrade embedded wheels:

  - wheel to ``0.45.0`` from ``0.44.0``
  - setuptools to ``75.5.0`` (:pr:`2800`) - by :user:`gaborbernat`.

- Upgrade embedded wheels:

  - setuptools to ``75.6.0`` from ``75.5.0``
  - wheel to ``0.45.1`` from ``0.45.0`` (:pr:`2804`) - by :user:`gaborbernat`.

.. _release-20-27-1:

***********************
 v20.27.1 (2024-10-28)
***********************

.. _release-20-27-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``24.3.1`` from ``24.2`` (:issue:`2789`) - by :user:`gaborbernat`.

.. _release-20-27-0:

***********************
 v20.27.0 (2024-10-17)
***********************

.. _release-20-27-0-added:

Added
-----

- Drop 3.7 support as the CI environments no longer allow it running - by :user:`gaborbernat`. (:issue:`2758`)

.. _release-20-27-0-fixed:

Fixed
-----

- When a ``$PATH`` entry cannot be checked for existence, skip it instead of terminating - by :user:`hroncok`.
  (:pr:`2782`)
- Fix zipapp is broken on Windows post distlib ``0.3.9`` - by :user:`gaborbernat`. (:issue:`2784`)

.. _release-20-27-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``75.2.0`` from ``75.1.0``
  - Removed pip of ``24.0``
  - Removed setuptools of ``68.0.0``
  - Removed wheel of ``0.42.0``
  - by :user:`gaborbernat`. (:pr:`2783`)

.. _release-20-26-6:

***********************
 v20.26.6 (2024-09-27)
***********************

.. _release-20-26-6-fixed:

Fixed
-----

- Properly quote string placeholders in activation script templates to mitigate potential command injection - by
  :user:`y5c4l3`. (:issue:`2768`)

.. _release-20-26-5:

***********************
 v20.26.5 (2024-09-17)
***********************

.. _release-20-26-5-packaging:

Packaging
---------

- Upgrade embedded wheels: setuptools to ``75.1.0`` from ``74.1.2`` - by :user:`gaborbernat`. (:pr:`2765`)

.. _release-20-26-4:

***********************
 v20.26.4 (2024-09-07)
***********************

.. _release-20-26-4-fixed:

Fixed
-----

- Stop printing ``()`` during activation through a batch file. (:issue:`2728`) - by :user:`ShootGan`.

.. _release-20-26-4-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - wheel to ``0.44.0`` from ``0.43.0``
  - pip to ``24.2`` from ``24.1``
  - setuptools to ``74.1.2`` from ``70.1.0`` (:pr:`2760`) - by :user:`gaborbernat`.

.. _release-20-26-3:

***********************
 v20.26.3 (2024-06-21)
***********************

.. _release-20-26-3-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``70.1.0`` from ``69.5.1``
  - pip to ``24.1`` from ``24.0`` (:pr:`2741`) - by :user:`gaborbernat`.

.. _release-20-26-2:

***********************
 v20.26.2 (2024-05-13)
***********************

.. _release-20-26-2-fixed:

Fixed
-----

- ``virtualenv.pyz`` no longer fails when zipapp path contains a symlink - by :user:`HandSonic` and :user:`petamas`.
  (:issue:`1949`)
- Fix bad return code from ``activate.sh`` if hashing is disabled. (:pr:`2717`) - by :user:`fenkes-ibm`.

.. _release-20-26-1:

***********************
 v20.26.1 (2024-04-29)
***********************

.. _release-20-26-1-fixed:

Fixed
-----

- fix PATH-based Python discovery on Windows - by :user:`ofek`. (:pr:`2712`)

.. _release-20-26-0:

***********************
 v20.26.0 (2024-04-23)
***********************

.. _release-20-26-0-fixed:

Fixed
-----

- allow builtin discovery to discover specific interpreters (e.g. ``python3.12``) given an unspecific spec (e.g.
  ``python3``) - by :user:`flying-sheep` and :user:`gaborbernat`. (:pr:`2709`)

.. _release-20-25-3:

***********************
 v20.25.3 (2024-04-17)
***********************

.. _release-20-25-3-fixed:

Fixed
-----

- Python 3.13.0a6 renamed pathmod to parser. (:pr:`2702`) - by :user:`befeleme` and :user:`gaborbernat`.

.. _release-20-25-2:

***********************
 v20.25.2 (2024-04-16)
***********************

.. _release-20-25-2-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools of ``69.1.0`` to ``69.5.1``
  - wheel of ``0.42.0`` to ``0.43.0`` (:pr:`2699`) - by :user:`gaborbernat`.

.. _release-20-25-1:

***********************
 v20.25.1 (2024-02-21)
***********************

.. _release-20-25-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``69.0.3`` from ``69.0.2``
  - pip to ``23.3.2`` from ``23.3.1`` (:pr:`2681`) - by :user:`gaborbernat`.

- Upgrade embedded wheels:

  - pip ``23.3.2`` to ``24.0``,
  - setuptools ``69.0.3`` to ``69.1.0``. (:pr:`2691`) - by :user:`gaborbernat`.

.. _release-20-25-0:

***********************
 v20.25.0 (2023-12-01)
***********************

.. _release-20-25-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - wheel to ``0.42.0`` from ``0.41.3``
  - setuptools to ``69.0.2`` from ``68.2.2`` (:pr:`2669`) - by :user:`gaborbernat`.

.. _release-20-24-7:

***********************
 v20.24.7 (2023-11-21)
***********************

.. _release-20-24-7-packaging:

Packaging
---------

- Upgrade the embedded wheel package from ``0.41.2`` to ``0.41.3``. (:pr:`2665`) - by :user:`gaborbernat`.

.. _release-20-24-6:

***********************
 v20.24.6 (2023-10-23)
***********************

.. _release-20-24-6-fixed:

Fixed
-----

- Use get_hookimpls method instead of the private attribute in tests. (:pr:`2649`) - by :user:`danigm`.

.. _release-20-24-6-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``68.2.2`` from ``68.2.0``
  - pip to ``23.3.1`` from ``23.2.1`` (:pr:`2656`) - by :user:`gaborbernat`.

.. _release-20-24-5:

***********************
 v20.24.5 (2023-09-08)
***********************

.. _release-20-24-5-fixed:

Fixed
-----

- Declare PyPy 3.10 support - by :user:`cclauss`. (:pr:`2638`)
- Brew on macOS no longer allows copy builds - disallow choosing this by :user:`gaborbernat`. (:pr:`2640`)

.. _release-20-24-5-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``68.2.0`` from ``68.1.2`` (:pr:`2642`) - by :user:`gaborbernat`.

.. _release-20-24-4:

***********************
 v20.24.4 (2023-08-30)
***********************

.. _release-20-24-4-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``68.1.2`` from ``68.1.0`` on ``3.8+``
  - wheel to ``0.41.2`` from ``0.41.1`` on ``3.7+`` (:pr:`2628`)

.. _release-20-24-3:

***********************
 v20.24.3 (2023-08-11)
***********************

.. _release-20-24-3-fixed:

Fixed
-----

- Fix ``ResourceWarning`` on exit from the periodic update subprocess (:issue:`2472`) - by :user:`sigma67`.

.. _release-20-24-3-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - wheel to ``0.41.1`` from ``0.41.0`` (:pr:`2622`) - by :user:`gaborbernat`.

.. _release-20-24-2:

***********************
 v20.24.2 (2023-07-24)
***********************

.. _release-20-24-2-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``23.2.1`` from ``23.2``
  - wheel to ``0.41.0`` from ``0.40.0`` (:pr:`2614`) - by :user:`gaborbernat`.

.. _release-20-24-1:

***********************
 v20.24.1 (2023-07-19)
***********************

.. _release-20-24-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - pip to ``23.2`` from ``23.1.2`` - by :user:`arielkirkwood` (:pr:`2611`)

.. _release-20-24-0:

***********************
 v20.24.0 (2023-07-14)
***********************

.. _release-20-24-0-added:

Added
-----

- Export the prompt prefix as ``VIRTUAL_ENV_PROMPT`` when activating a virtual environment - by :user:`jimporter`.
  (:issue:`2194`)

.. _release-20-24-0-fixed:

Fixed
-----

- Fix test suite - by :user:`gaborbernat`. (:issue:`2592`)

.. _release-20-24-0-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``68.0.0`` from ``67.8.0`` (:pr:`2607`) - by :user:`gaborbernat`.

.. _release-20-23-1:

***********************
 v20.23.1 (2023-06-16)
***********************

.. _release-20-23-1-fixed:

Fixed
-----

- update and simplify nushell activation script, fixes an issue on Windows resulting in consecutive command not found -
  by :user:`melMass`. (:pr:`2572`)

.. _release-20-23-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - setuptools to ``67.8.0`` from ``67.7.2`` (:pr:`2588`) - by :user:`gaborbernat`.

.. _release-20-23-0:

***********************
 v20.23.0 (2023-04-27)
***********************

.. _release-20-23-0-added:

Added
-----

- Do not install ``wheel`` and ``setuptools`` seed packages for Python 3.12+. To restore the old behavior use:

  - for ``wheel`` use ``VIRTUALENV_WHEEL=bundle`` environment variable or ``--wheel=bundle`` CLI flag,
  - for ``setuptools`` use ``VIRTUALENV_SETUPTOOLS=bundle`` environment variable or ``--setuptools=bundle`` CLI flag.

  By :user:`chrysle`. (:issue:`2487`)

- 3.12 support - by :user:`gaborbernat` and :user:`chrysle`. (:pr:`2558`)

.. _release-20-23-0-fixed:

Fixed
-----

- Prevent ``PermissionError`` when using venv creator on systems that deliver files without user write permission - by
  :user:`kulikjak`. (:pr:`2543`)

.. _release-20-23-0-packaging:

Packaging
---------

- Upgrade setuptools to ``67.7.2`` from ``67.6.1`` and pip to ``23.1.2`` from ``23.1`` - by :user:`szleb`.
  (:issue:`2560`)

.. _release-20-22-0:

***********************
 v20.22.0 (2023-04-19)
***********************

.. _release-20-22-0-added:

Added
-----

- Drop support for creating Python <=3.6 (including 2) interpreters. Removed pip of ``20.3.4``, ``21.3.1``; wheel of
  ``0.37.1``; setuptools of ``59.6.0``, ``44.1.1``, ``50.3.2``- by :user:`gaborbernat`. (:pr:`2548`)

.. _release-20-21-1:

***********************
 v20.21.1 (2023-04-19)
***********************

.. _release-20-21-1-fixed:

Fixed
-----

- Add ``tox.ini`` to sdist - by :user:`mtelka`. (:issue:`2511`)
- Move the use of 'let' in nushell to ensure compatibility with future releases of nushell, where 'let' no longer
  assumes that its initializer is a full expressions. (:pr:`2527`) - by :user:`sophiajt`.
- The nushell command 'str collect' has been superseded by the 'str join' command. The activate.nu script has been
  updated to reflect this change. (:pr:`2532`) - by :user:`fdncred`.

.. _release-20-21-1-packaging:

Packaging
---------

- Upgrade embedded wheels:

  - wheel to ``0.40.0`` from ``0.38.4``
  - setuptools to ``67.6.1`` from ``67.4.0``
  - pip to ``23.1`` from ``23.0.1`` (:pr:`2546`) - by :user:`gaborbernat`.

.. _release-20-21-0:

***********************
 v20.21.0 (2023-03-12)
***********************

.. _release-20-21-0-added:

Added
-----

- Make closure syntax explicitly starts with {||. (:pr:`2512`) - by :user:`WindSoilder`.

.. _release-20-21-0-fixed:

Fixed
-----

- Add ``print`` command to nushell print_prompt to ensure compatibility with future release of nushell, where
  intermediate commands no longer print their result to stdout. (:pr:`2514`) - by :user:`NotLebedev`.
- Do not assume the default encoding. (:pr:`2515`) - by :user:`FFY00`.
- Make ``ReentrantFileLock`` thread-safe and, thereby, fix race condition in ``virtualenv.cli_run`` - by
  :user:`radoering`. (:issue:`2516`)

.. _release-20-20-0:

***********************
 v20.20.0 (2023-02-28)
***********************

.. _release-20-20-0-added:

Added
-----

- Change environment variable existence check in Nushell activation script to not use deprecated command. (:pr:`2506`) -
  by :user:`kubouch`.

.. _release-20-20-0-fixed:

Fixed
-----

- Discover CPython implementations distributed on Windows by any organization - by :user:`faph`. (:pr:`2504`)

.. _release-20-20-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``67.4.0`` from ``67.1.0`` and pip to ``23.0.1`` from ``23.0`` - by
  :user:`gaborbernat`. (:pr:`2510`)

.. _release-20-19-0:

***********************
 v20.19.0 (2023-02-07)
***********************

.. _release-20-19-0-added:

Added
-----

- Allow platformdirs version ``3`` - by :user:`cdce8p`. (:issue:`2499`)

.. _release-20-18-0:

***********************
 v20.18.0 (2023-02-06)
***********************

.. _release-20-18-0-added:

Added
-----

- Drop ``3.6`` runtime support (can still create ``2.7+``) - by :user:`gaborbernat`. (:pr:`2489`)

.. _release-20-18-0-fixed:

Fixed
-----

- Fix broken prompt in Nushell when activating virtual environment - by :user:`kubouc` and :user:`kubouch`. (:pr:`2481`)

.. _release-20-18-0-packaging:

Packaging
---------

- Bump embedded pip to ``23.0`` and setuptools to ``67.1`` - by :user:`gaborbernat`. (:pr:`2489`)

.. _release-20-17-1:

***********************
 v20.17.1 (2022-12-05)
***********************

.. _release-20-17-1-fixed:

Fixed
-----

- A ``py`` or ``python`` spec means any Python rather than ``CPython`` - by :user:`gaborbernat`. (:pr:`2460`)
- Make ``activate.nu`` respect ``VIRTUAL_ENV_DISABLE_PROMPT`` and not set the prompt if requested - by :user:`m-lima`.
  (:issue:`2461`)

.. _release-20-17-0:

***********************
 v20.17.0 (2022-11-27)
***********************

.. _release-20-17-0-added:

Added
-----

- Change Nushell activation script to be a module meant to be activated as an overlay. (:pr:`2422`) - by
  :user:`kubouch`.
- Update operator used in Nushell activation script to be compatible with future versions. (:pr:`2450`) - by
  :user:`kubouch`.

.. _release-20-17-0-fixed:

Fixed
-----

- Do not use deprecated API from ``importlib.resources`` on Python 3.10 or later - by :user:`gaborbernat`. (:pr:`2448`)

.. _release-20-17-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``65.6.3`` from ``65.5.1`` - by :user:`gaborbernat`. (:pr:`2451`)

.. _release-20-16-7:

***********************
 v20.16.7 (2022-11-12)
***********************

.. _release-20-16-7-fixed:

Fixed
-----

- Use parent directory of python executable for pyvenv.cfg "home" value per PEP 405 - by :user:`vfazio`. (:issue:`2440`)
- In POSIX virtual environments, try alternate binary names if ``sys._base_executable`` does not exist - by
  :user:`vfazio`. (:pr:`2442`)

.. _release-20-16-7-packaging:

Packaging
---------

- Upgrade embedded wheel to ``0.38.4`` and pip to ``22.3.1`` from ``22.3`` and setuptools to ``65.5.1`` from ``65.5.0``
  - by :user:`gaborbernat`. (:pr:`2443`)

.. _release-20-16-6:

***********************
 v20.16.6 (2022-10-25)
***********************

.. _release-20-16-6-added:

Added
-----

- Drop unneeded shims for PyPy3 directory structure (:pr:`2426`) - by :user:`mattip`.

.. _release-20-16-6-fixed:

Fixed
-----

- Fix selected scheme on debian derivatives for python 3.10 when ``python3-distutils`` is not installed or the ``venv``
  scheme is not available - by :user:`asottile`. (:issue:`2350`)
- Allow the test suite to pass even with the original C shell (rather than ``tcsh``) - by :user:`kulikjak`. (:pr:`2418`)
- Fix fallback handling of downloading wheels for bundled packages - by :user:`schaap`. (:issue:`2429`)

.. _release-20-16-6-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``65.5.0`` from ``65.3.0`` and pip to ``22.3`` from ``22.2.2`` - by
  :user:`gaborbernat`. (:pr:`2434`)

.. _release-20-16-5:

***********************
 v20.16.5 (2022-09-07)
***********************

.. _release-20-16-5-fixed:

Fixed
-----

- Do not turn echo off for subsequent commands in batch activators (``activate.bat`` and ``deactivate.bat``) - by
  :user:`pawelszramowski`. (:issue:`2411`)

.. _release-20-16-4:

***********************
 v20.16.4 (2022-08-29)
***********************

.. _release-20-16-4-packaging:

Packaging
---------

- Bump embed setuptools to ``65.3`` - by :user:`gaborbernat`. (:pr:`2405`)

.. _release-20-16-3:

***********************
 v20.16.3 (2022-08-04)
***********************

.. _release-20-16-3-packaging:

Packaging
---------

- Upgrade embedded pip to ``22.2.2`` from ``22.2.1`` and setuptools to ``63.4.1`` from ``63.2.0`` - by
  :user:`gaborbernat`. (:pr:`2395`)

.. _release-20-16-2:

***********************
 v20.16.2 (2022-07-27)
***********************

.. _release-20-16-2-packaging:

Packaging
---------

- Bump embedded pip from ``22.2`` to ``22.2.1`` - by :user:`gaborbernat`. (:pr:`2391`)

.. _release-20-16-1:

***********************
 v20.16.1 (2022-07-26)
***********************

.. _release-20-16-1-added:

Added
-----

- Update Nushell activation scripts to version 0.67 - by :user:`kubouch`. (:pr:`2386`)

.. _release-20-16-0:

***********************
 v20.16.0 (2022-07-25)
***********************

.. _release-20-16-0-added:

Added
-----

- Drop support for running under Python 2 (still can generate Python 2 environments) - by :user:`gaborbernat`.
  (:pr:`2382`)

.. _release-20-16-0-packaging:

Packaging
---------

- Upgrade embedded pip to ``22.2`` from ``22.1.2`` and setuptools to ``63.2.0`` from ``62.6.0`` - by
  :user:`gaborbernat`. (:pr:`2383`)

.. _release-20-15-1:

***********************
 v20.15.1 (2022-06-28)
***********************

.. _release-20-15-1-fixed:

Fixed
-----

- Fix the incorrect operation when ``setuptools`` plugins output something into ``stdout``. (:pr:`2335`) - by
  :user:`KOLANICH`.
- CPython3Windows creator ignores missing ``DLLs`` dir. (:issue:`2368`) - by :user:`reksar`.

.. _release-20-15-0:

***********************
 v20.15.0 (2022-06-25)
***********************

.. _release-20-15-0-added:

Added
-----

- Support for Windows embeddable Python package: includes ``python<VERSION>.zip`` in the creator sources - by
  :user:`reksarka`. (:issue:`1774`)

.. _release-20-15-0-fixed:

Fixed
-----

- Use ``shlex.quote`` instead of deprecated ``pipes.quote`` in Python 3 - by :user:`frenzymadness`. (:pr:`2351`)
- Fix Windows PyPy 3.6 - by :user:`reksarka` and :user:`reksar`. (:pr:`2363`)

.. _release-20-15-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``62.3.3`` from ``62.6.0`` and pip to ``22.1.2`` from ``22.0.4`` - by
  :user:`gaborbernat`. (:pr:`2348`)

.. _release-20-14-1:

***********************
 v20.14.1 (2022-04-11)
***********************

.. _release-20-14-1-added:

Added
-----

- Support for creating a virtual environment from a Python 2.7 framework on macOS 12 - by :user:`nickhutchinson`.
  (:issue:`2284`)

.. _release-20-14-1-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``62.1.0`` from ``61.0.0`` - by :user:`gaborbernat`. (:issue:`2327`)

.. _release-20-14-0:

***********************
 v20.14.0 (2022-03-25)
***********************

.. _release-20-14-0-added:

Added
-----

- Support Nushell activation scripts with nu version ``0.60`` - by :user:`kubouch`. (:pr:`2321`)

.. _release-20-14-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``61.0.0`` from ``60.10.0`` - by :user:`gaborbernat`. (:pr:`2322`)

.. _release-20-13-4:

***********************
 v20.13.4 (2022-03-18)
***********************

.. _release-20-13-4-performance:

Performance
-----------

- Improve performance of python startup inside created virtualenvs - by :user:`asottile`. (:pr:`2317`)

.. _release-20-13-4-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``60.10.0`` from ``60.9.3`` - by :user:`gaborbernat`. (:pr:`2320`)

.. _release-20-13-3:

***********************
 v20.13.3 (2022-03-07)
***********************

.. _release-20-13-3-fixed:

Fixed
-----

- Avoid symlinking the contents of ``/usr`` into PyPy3.8+ virtualenvs - by :user:`stefanor` and :user:`gaborbernat`.
  (:pr:`2310`)

.. _release-20-13-3-packaging:

Packaging
---------

- Bump embed pip from ``22.0.3`` to ``22.0.4`` - by :user:`gaborbernat`. (:pr:`2311`)

.. _release-20-13-2:

***********************
 v20.13.2 (2022-02-24)
***********************

.. _release-20-13-2-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``60.9.3`` from ``60.6.0`` - by :user:`gaborbernat`. (:pr:`2306`)

.. _release-20-13-1:

***********************
 v20.13.1 (2022-02-05)
***********************

.. _release-20-13-1-fixed:

Fixed
-----

- Fix "execv() arg 2 must contain only strings" on M1 macOS (:issue:`2282`) - by :user:`isac322`.

.. _release-20-13-1-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``60.5.0`` from ``60.2.0`` - by :user:`asottile`. (:pr:`2289`)
- Upgrade embedded pip to ``22.0.3`` and setuptools to ``60.6.0`` - by :user:`gaborbernat` and :user:`asottile`.
  (:pr:`2294`)

.. _release-20-13-0:

***********************
 v20.13.0 (2022-01-02)
***********************

.. _release-20-13-0-added:

Added
-----

- Add downloaded wheel information in the relevant JSON embed file to prevent additional downloads of the same wheel. -
  by :user:`mayeut`. (:issue:`2268`)

.. _release-20-13-0-fixed:

Fixed
-----

- Fix ``AttributeError: 'bool' object has no attribute 'error'`` when creating a Python 2.x virtualenv on macOS - by
  :user:`moreati`. (:issue:`2269`)
- Fix ``PermissionError: [Errno 1] Operation not permitted`` when creating a Python 2.x virtualenv on macOS/arm64 - by
  :user:`moreati`. (:issue:`2271`)

.. _release-20-12-1:

***********************
 v20.12.1 (2022-01-01)
***********************

.. _release-20-12-1-fixed:

Fixed
-----

- Try using previous updates of ``pip``, ``setuptools`` & ``wheel`` when inside an update grace period rather than
  always falling back to embedded wheels - by :user:`mayeut`. (:issue:`2265`)
- New patch versions of ``pip``, ``setuptools`` & ``wheel`` are now returned in the expected timeframe. - by
  :user:`mayeut`. (:issue:`2266`)
- Manual upgrades of ``pip``, ``setuptools`` & ``wheel`` are not discarded by a periodic update - by :user:`mayeut`.
  (:issue:`2267`)

.. _release-20-12-0:

***********************
 v20.12.0 (2021-12-31)
***********************

.. _release-20-12-0-added:

Added
-----

- Sign the python2 exe on Darwin arm64 - by :user:`tmspicer` and :user:`gaborbernat`. (:pr:`2233`)

.. _release-20-12-0-fixed:

Fixed
-----

- Fix ``--download`` option - by :user:`mayeut`. (:issue:`2120`)

.. _release-20-12-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``60.2.0`` from ``60.1.1`` - by :user:`gaborbernat`. (:pr:`2263`)

.. _release-20-11-2:

***********************
 v20.11.2 (2021-12-29)
***********************

.. _release-20-11-2-fixed:

Fixed
-----

- Fix installation of pinned versions of ``pip``, ``setuptools`` & ``wheel`` - by :user:`mayeut`. (:issue:`2203`)

.. _release-20-11-1:

***********************
 v20.11.1 (2021-12-29)
***********************

.. _release-20-11-1-packaging:

Packaging
---------

- Bump embed setuptools to ``60.1.1`` from ``60.1.0`` - by :user:`gaborbernat`. (:pr:`2258`)

.. _release-20-11-0:

***********************
 v20.11.0 (2021-12-28)
***********************

.. _release-20-11-0-added:

Added
-----

- Avoid deprecation warning from py-filelock argument - by :user:`ofek` and :user:`gaborbernat`. (:pr:`2237`)
- Drop the runtime dependency of ``backports.entry-points-selectable`` - by :user:`hroncok`. (:pr:`2246`)
- Fish: PATH variables should not be quoted when being set - by :user:`d3dave`. (:pr:`2248`)

.. _release-20-11-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``61.1.0`` from ``58.3.0`` - by :user:`gaborbernat`. (:issue:`2240`)

.. _release-20-10-0:

***********************
 v20.10.0 (2021-11-01)
***********************

.. _release-20-10-0-added:

Added
-----

- If a ``"venv"`` install scheme exists in ``sysconfig``, virtualenv now uses it to create new virtual environments.
  This allows Python distributors, such as Fedora, to patch/replace the default install scheme without affecting the
  paths in new virtual environments. A similar technique `was proposed to Python, for the venv module
  <https://bugs.python.org/issue45413>`_ - by :user:`hroncok` (:issue:`2208`)
- The activated virtualenv prompt is now always wrapped in parentheses. This affects venvs created with the ``--prompt``
  attribute, and matches virtualenv's behavior on par with venv. (:pr:`2224`) - by :user:`tusharsadhwani`.

.. _release-20-10-0-fixed:

Fixed
-----

- Fix broken prompt set up by activate.bat - by :user:`SiggyBar`. (:issue:`2225`)

.. _release-20-9-0:

**********************
 v20.9.0 (2021-10-23)
**********************

.. _release-20-9-0-added:

Added
-----

- Special-case ``--prompt .`` to the name of the current directory - by :user:`rkm` and :user:`gaborbernat`.
  (:pr:`2220`)
- Add libffi-8.dll to pypy windows :pr:`2218` - by :user:`mattip`

.. _release-20-9-0-fixed:

Fixed
-----

- Fixed path collision that could lead to a PermissionError or writing to system directories when using PyPy3.8 - by
  :user:`mgorny`. (:issue:`2182`)
- Remove stray closing parenthesis in activate.bat - by :user:`SiggyBar` and :user:`SigmundVik`. (:pr:`2221`)

.. _release-20-9-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``58.3.0`` from ``58.1.0`` and pip to ``21.3.1`` from ``21.2.4`` - by
  :user:`gaborbernat`. (:pr:`2205`)

.. _release-20-8-1:

**********************
 v20.8.1 (2021-09-24)
**********************

.. _release-20-8-1-fixed:

Fixed
-----

- Fixed a bug where while creating a venv on top of an existing one, without cleaning, when seeded wheel version
  mismatch occurred, multiple ``.dist-info`` directories may be present, confounding entrypoint discovery - by
  :user:`arcivanov` (:issue:`2185`)

.. _release-20-8-1-packaging:

Packaging
---------

- Bump embed setuptools from ``58.0.4`` to ``58.1.0`` - by :user:`gaborbernat`. (:pr:`2195`)

.. _release-20-8-0:

**********************
 v20.8.0 (2021-09-16)
**********************

.. _release-20-8-0-added:

Added
-----

- Add the nushell activation script - by :user:`elferherrera`.

.. _release-20-8-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``58.0.4`` from ``57.4.0`` and pip to ``21.2.4`` from ``21.2.3`` - by
  :user:`gaborbernat`.

.. _release-20-7-2:

**********************
 v20.7.2 (2021-08-10)
**********************

.. _release-20-7-2-packaging:

Packaging
---------

- Upgrade embedded pip to ``21.2.3`` from ``21.2.2`` and wheel to ``0.37.0`` from ``0.36.2`` - by :user:`gaborbernat`.
  (:pr:`2168`)

.. _release-20-7-1:

**********************
 v20.7.1 (2021-08-09)
**********************

.. _release-20-7-1-fixed:

Fixed
-----

- Fix unpacking dictionary items in PythonInfo.install_path (:pr:`2165`) - by :user:`denismaciel`.

.. _release-20-7-0:

**********************
 v20.7.0 (2021-07-31)
**********************

.. _release-20-7-0-removed:

Removed
-------

- Removed ``xonsh`` activator due to this breaking fairly often the CI and lack of support from those packages
  maintainers, upstream is encouraged to continue supporting the project as a `plugin
  <https://github.com/xonsh/xonsh/issues/3689>`_ - by :user:`gaborbernat`. (:pr:`2160`)

.. _release-20-7-0-packaging:

Packaging
---------

- upgrade embedded pip to ``21.2.2`` from ``21.1.3`` and setuptools to ``57.4.0`` from ``57.1.0`` - by
  :user:`gaborbernat` (:pr:`2159`)

.. _release-20-6-0:

**********************
 v20.6.0 (2021-07-14)
**********************

.. _release-20-6-0-added:

Added
-----

- Support Python interpreters without ``distutils`` (fallback to ``syconfig`` in these cases) - by :user:`gaborbernat`.
  (:issue:`1910`)

.. _release-20-5-0:

**********************
 v20.5.0 (2021-07-13)
**********************

.. _release-20-5-0-added:

Added
-----

- Plugins now use 'selectable' entry points - by :user:`jaraco`. (:issue:`2093`)
- add libffi-7.dll to the hard-coded list of dlls for PyPy (:pr:`2141`) - by :user:`mattip` and :user:`gaborbernat`.
- Use the better maintained ``platformdirs`` instead of ``appdirs`` - by :user:`gaborbernat`. (:pr:`2142`)
- Drop python ``3.4`` support as it has been over 2 years since EOL - by :user:`gaborbernat` and :user:`mattip`.
  (:pr:`2141`)

.. _release-20-5-0-packaging:

Packaging
---------

- Bump pip the embedded pip ``21.1.3`` and setuptools to ``57.1.0`` - by :user:`gaborbernat`. (:pr:`2135`)

.. _release-20-4-7:

**********************
 v20.4.7 (2021-05-24)
**********************

.. _release-20-4-7-packaging:

Packaging
---------

- Upgrade embedded pip to ``21.1.2`` and setuptools to ``57.0.0`` - by :user:`gaborbernat`. (:pr:`2123`)

.. _release-20-4-6:

**********************
 v20.4.6 (2021-05-05)
**********************

.. _release-20-4-6-fixed:

Fixed
-----

- Fix ``site.getsitepackages()`` broken on python2 on debian - by :user:`freundTech`. (:issue:`2105`)

.. _release-20-4-5:

**********************
 v20.4.5 (2021-05-05)
**********************

.. _release-20-4-5-fixed:

Fixed
-----

- Fix ``site.getsitepackages()`` ignoring ``--system-site-packages`` on python2 - by :user:`freundTech`. (:issue:`2106`)

.. _release-20-4-5-packaging:

Packaging
---------

- Bump pip to ``21.1.1`` from ``21.0.1`` - by :user:`gaborbernat`. (:pr:`2104`)

.. _release-20-4-4:

**********************
 v20.4.4 (2021-04-20)
**********************

.. _release-20-4-4-fixed:

Fixed
-----

- Built in discovery class is always preferred over plugin supplied classes. (:issue:`2087`) - by :user:`AWhetter`.

.. _release-20-4-4-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``56.0.0`` by :user:`gaborbernat`. (:pr:`2094`)

.. _release-20-4-3:

**********************
 v20.4.3 (2021-03-16)
**********************

.. _release-20-4-3-fixed:

Fixed
-----

- Fix PyPy3 stdlib on Windows is incorrect - by :user:`gaborbernat`. (:issue:`2071`)

.. _release-20-4-3-packaging:

Packaging
---------

- Bump embedded setuptools from ``52.0.0`` to ``54.1.2`` - by :user:`gaborbernat` (:pr:`2069`)

.. _release-20-4-2:

**********************
 v20.4.2 (2021-02-01)
**********************

.. _release-20-4-2-fixed:

Fixed
-----

- Running virtualenv ``--upgrade-embed-wheels`` crashes - by :user:`gaborbernat`. (:issue:`2058`)

.. _release-20-4-1:

**********************
 v20.4.1 (2021-01-31)
**********************

.. _release-20-4-1-packaging:

Packaging
---------

- Bump embedded pip and setuptools packages to latest upstream supported (``21.0.1`` and ``52.0.0``) - by
  :user:`gaborbernat`. (:pr:`2060`)

.. _release-20-4-0:

**********************
 v20.4.0 (2021-01-19)
**********************

.. _release-20-4-0-added:

Added
-----

- On the programmatic API allow passing in the environment variable dictionary to use, defaults to ``os.environ`` if not
  specified - by :user:`gaborbernat`. (:pr:`2054`)

.. _release-20-4-0-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``51.3.3`` from ``51.1.2`` - by :user:`gaborbernat`. (:pr:`2055`)

.. _release-20-3-1:

**********************
 v20.3.1 (2021-01-13)
**********************

.. _release-20-3-1-fixed:

Fixed
-----

- Allow unfunctioning of pydoc to fail freely so that virtualenvs can be activated under Zsh with set -e (since
  otherwise ``unset -f`` and ``unfunction`` exit with 1 if the function does not exist in Zsh) - by :user:`d125q`.
  (:pr:`2049`)
- Drop cached python information if the system executable is no longer present (for example when the executable is a
  shim and the mapped executable is replaced - such is the case with pyenv) - by :user:`gaborbernat`. (:pr:`2050`)

.. _release-20-3-1-packaging:

Packaging
---------

- Bump embed pip to ``20.3.3``, setuptools to ``51.1.1`` and wheel to ``0.36.2`` - by :user:`gaborbernat`. (:pr:`2036`)

.. _release-20-3-0:

**********************
 v20.3.0 (2021-01-10)
**********************

.. _release-20-3-0-added:

Added
-----

- The builtin discovery takes now a ``--try-first-with`` argument and is first attempted as valid interpreters. One can
  use this to force discovery of a given python executable when the discovery order/mechanism raises errors - by
  :user:`gaborbernat`. (:pr:`2046`)

.. _release-20-3-0-fixed:

Fixed
-----

- On Windows python ``3.7+`` distributions where the exe shim is missing fallback to the old ways - by
  :user:`gaborbernat`. (:issue:`1986`)
- When discovering interpreters on Windows, via the PEP-514, prefer ``PythonCore`` releases over other ones. virtualenv
  is used via pip mostly by this distribution, so prefer it over other such as conda - by :user:`gaborbernat`.
  (:pr:`2046`)

.. _release-20-2-2:

**********************
 v20.2.2 (2020-12-07)
**********************

.. _release-20-2-2-packaging:

Packaging
---------

- Bump pip to ``20.3.1``, setuptools to ``51.0.0`` and wheel to ``0.36.1`` - by :user:`gaborbernat`. (:pr:`2029`)

.. _release-20-2-1:

**********************
 v20.2.1 (2020-11-23)
**********************

.. _release-20-2-0:

**********************
 v20.2.0 (2020-11-21)
**********************

.. _release-20-2-0-added:

Added
-----

- Optionally skip VCS ignore directive for entire virtualenv directory, using option :option:`no-vcs-ignore`, by default
  ``False``. (:issue:`2003`) - by :user:`compwiztobe`.
- Add ``--read-only-app-data`` option to allow for creation based on an existing app data cache which is non-writable.
  This may be useful (for example) to produce a docker image where the app-data is pre-populated.

  .. code-block:: dockerfile

      ENV \
          VIRTUALENV_OVERRIDE_APP_DATA=/opt/virtualenv/cache \
          VIRTUALENV_SYMLINK_APP_DATA=1
      RUN virtualenv venv && rm -rf venv
      ENV VIRTUALENV_READ_ONLY_APP_DATA=1
      USER nobody
      # this virtualenv has symlinks into the read-only app-data cache
      RUN virtualenv /tmp/venv

  Patch by :user:`asottile`. (:pr:`2009`)

.. _release-20-2-0-fixed:

Fixed
-----

- Fix processing of the ``VIRTUALENV_PYTHON`` environment variable and make it multi-value as well (separated by comma)
  - by :user:`pneff`. (:pr:`1998`)

.. _release-20-1-0:

**********************
 v20.1.0 (2020-10-25)
**********************

.. _release-20-1-0-added:

Added
-----

- The python specification can now take one or more values, first found is used to create the virtual environment - by
  :user:`gaborbernat`. (:pr:`1995`)

.. _release-20-0-35:

***********************
 v20.0.35 (2020-10-15)
***********************

.. _release-20-0-35-fixed:

Fixed
-----

- After importing virtualenv passing cwd to a subprocess calls breaks with ``invalid directory`` - by
  :user:`gaborbernat`. (:issue:`1983`)

.. _release-20-0-35-packaging:

Packaging
---------

- Bump embedded setuptools from ``50.3.0`` to ``50.3.1`` - by :user:`gaborbernat`. (:pr:`1982`)

.. _release-20-0-34:

***********************
 v20.0.34 (2020-10-12)
***********************

.. _release-20-0-34-fixed:

Fixed
-----

- Align with venv module when creating virtual environments with builtin creator on Windows 3.7 and later - by
  :user:`gaborbernat`. (:issue:`1782`)
- Handle Cygwin path conversion in the activation script - by :user:`davidcoghlan`. (:issue:`1969`)

.. _release-20-0-33:

***********************
 v20.0.33 (2020-10-04)
***********************

.. _release-20-0-33-fixed:

Fixed
-----

- Fix ``None`` type error in cygwin if POSIX path in dest - by :user:`danyeaw`. (:issue:`1962`)
- Fix Python 3.4 incompatibilities (added back to the CI) - by :user:`gaborbernat`. (:issue:`1963`)

.. _release-20-0-32:

***********************
 v20.0.32 (2020-10-01)
***********************

.. _release-20-0-32-fixed:

Fixed
-----

- For activation scripts always use UNIX line endings (unless it's BATCH shell related) - by :user:`saytosid`.
  (:issue:`1818`)
- Avoid spawning new windows when doing seed package upgrades in the background on Windows - by :user:`gaborbernat`.
  (:issue:`1928`)
- Fix a bug that reading and writing on the same file may cause race on multiple processes. (:issue:`1938`) - by
  :user:`frostming`.
- Provide correct path for bash activator in cygwin or msys2 - by :user:`danyeaw`. (:issue:`1940`)
- Relax importlib requirement to allow version<3 - by :user:`usamasadiq` and :user:`UsamaSadiq` (:pr:`1953`)
- pth files were not processed on CPython2 if $PYTHONPATH was pointing to site-packages/ - by :user:`navytux`.
  (:issue:`1959`) (:pr:`1960`)

.. _release-20-0-32-packaging:

Packaging
---------

- Upgrade embedded pip to ``20.2.1`` and setuptools to ``49.4.0`` - by :user:`gaborbernat`. (:pr:`1918`)
- Upgrade embedded setuptools to ``50.2.0`` and pip to ``20.2.3`` - by :user:`gaborbernat`. (:pr:`1939`)

.. _release-20-0-31:

***********************
 v20.0.31 (2020-08-17)
***********************

.. _release-20-0-31-packaging:

Packaging
---------

- Upgrade embedded pip to ``20.2.1``, setuptools to ``49.6.0`` and wheel to ``0.35.1`` - by :user:`gaborbernat`.
  (:pr:`1918`)

.. _release-20-0-30:

***********************
 v20.0.30 (2020-08-04)
***********************

.. _release-20-0-30-packaging:

Packaging
---------

- Upgrade pip to ``20.2.1`` and setuptools to ``49.2.1`` - by :user:`gaborbernat`. (:pr:`1915`)

.. _release-20-0-29:

***********************
 v20.0.29 (2020-07-31)
***********************

.. _release-20-0-29-packaging:

Packaging
---------

- Upgrade embedded pip from version ``20.1.2`` to ``20.2`` - by :user:`gaborbernat`. (:pr:`1909`)

.. _release-20-0-28:

***********************
 v20.0.28 (2020-07-24)
***********************

.. _release-20-0-28-fixed:

Fixed
-----

- Fix test suite failing if run from system Python - by :user:`gaborbernat`. (:issue:`1882`)
- Provide ``setup_logging`` flag to python API so that users can bypass logging handling if their application already
  performs this - by :user:`gaborbernat`. (:issue:`1896`)
- Use ``\n`` instead if ``\r\n`` as line separator for report (because Python already performs this transformation
  automatically upon write to the logging pipe) - by :user:`gaborbernat`. (:pr:`1905`)

.. _release-20-0-27:

***********************
 v20.0.27 (2020-07-15)
***********************

.. _release-20-0-27-fixed:

Fixed
-----

- No longer preimport threading to fix support for `gpython <https://pypi.org/project/pygolang/#gpython>`_ and `gevent
  <https://www.gevent.org/>`_ - by :user:`navytux`. (:pr:`1897`)

.. _release-20-0-27-packaging:

Packaging
---------

- Upgrade setuptools from ``49.2.0`` on ``Python 3.5+`` - by :user:`gaborbernat`. (:pr:`1898`)

.. _release-20-0-26:

***********************
 v20.0.26 (2020-07-07)
***********************

.. _release-20-0-26-fixed:

Fixed
-----

- Bump dependency ``distutils >= 0.3.1`` - by :user:`gaborbernat`. (:pr:`1880`)
- Improve periodic update handling:

  - better logging output while running and enable logging on background process call (
    ``_VIRTUALENV_PERIODIC_UPDATE_INLINE`` may be used to debug behavior inline)
  - fallback to unverified context when querying the PyPi for release date,
  - stop downloading wheels once we reach the embedded version,

  by :user:`gaborbernat`. (:issue:`1883`)

- Do not print error message if the application exists with ``SystemExit(0)`` - by :user:`gaborbernat`. (:issue:`1885`)

.. _release-20-0-26-packaging:

Packaging
---------

- Upgrade embedded setuptools from ``47.3.1`` to ``49.1.0`` for Python ``3.5+`` - by :user:`gaborbernat`. (:pr:`1887`)

.. _release-20-0-25:

***********************
 v20.0.25 (2020-06-23)
***********************

.. _release-20-0-25-fixed:

Fixed
-----

- Fix that when the ``app-data`` seeders image creation fails the exception is silently ignored. Avoid two virtual
  environment creations to step on each others toes by using a lock while creating the base images. By
  :user:`gaborbernat`. (:issue:`1869`)

.. _release-20-0-24:

***********************
 v20.0.24 (2020-06-22)
***********************

.. _release-20-0-24-added:

Added
-----

- Ensure that the seeded packages do not get too much out of date:

  - add a CLI flag that triggers upgrade of embedded wheels under :option:`upgrade-embed-wheels`
  - periodically (once every 14 days) upgrade the embedded wheels in a background process, and use them if they have
    been released for more than 28 days (can be disabled via :option:`no-periodic-update`)

  More details under :ref:`wheels` - by :user:`gaborbernat`. (:issue:`1821`)

- Display the installed seed package versions in the final summary output, for example:

  .. code-block:: console

      created virtual environment CPython3.8.3.final.0-64 in 350ms
        creator CPython3Posix(dest=/x, clear=True, global=False)
        seeder FromAppData(download=False, pip=bundle, setuptools=bundle, wheel=bundle, via=copy, app_data_dir=/y/venv)
          added seed packages: pip==20.1.1, setuptools==47.3.1, wheel==0.34.2

  by :user:`gaborbernat`. (:issue:`1864`)

.. _release-20-0-24-fixed:

Fixed
-----

- Do not generate/overwrite ``.gitignore`` if it already exists at destination path - by :user:`gaborbernat`.
  (:issue:`1862`)
- Improve error message for no ``.dist-info`` inside the ``app-data`` copy seeder - by :user:`gaborbernat`. (:pr:`1867`)

.. _release-20-0-24-documentation:

Documentation
-------------

- How seeding mechanisms discover (and automatically keep it up to date) wheels at :ref:`wheels` - by
  :user:`gaborbernat`. (:issue:`1821`)
- How distributions should handle shipping their own embedded wheels at :ref:`distribution_wheels` - by
  :user:`gaborbernat`. (:issue:`1840`)

.. _release-20-0-24-packaging:

Packaging
---------

- Upgrade embed wheel content:

  - ship wheels for Python ``3.9`` and ``3.10``
  - upgrade setuptools for Python ``3.5+`` from ``47.1.1`` to ``47.3.1``

  by :user:`gaborbernat` and :user:`pradyunsg`. (:pr:`1841`)

.. _release-20-0-23:

***********************
 v20.0.23 (2020-06-12)
***********************

.. _release-20-0-23-fixed:

Fixed
-----

- Fix typo in ``setup.cfg`` - by :user:`RowdyHowell`. (:issue:`1857`)

.. _release-20-0-22:

***********************
 v20.0.22 (2020-06-12)
***********************

.. _release-20-0-22-fixed:

Fixed
-----

- Relax ``importlib.resources`` requirement to also allow version 2 - by :user:`asottile` and :user:`gaborbernat`.
  (:pr:`1846`)

.. _release-20-0-22-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``44.1.1`` for python 2 and ``47.1.1`` for python3.5+ - by :user:`gaborbernat`.
  (:pr:`1855`)

.. _release-20-0-21:

***********************
 v20.0.21 (2020-05-20)
***********************

.. _release-20-0-21-added:

Added
-----

- Generate ignore file for version control systems to avoid tracking virtual environments by default. Users should
  remove these files if still want to track. For now we support only **git** by :user:`gaborbernat`. (:issue:`1806`)

.. _release-20-0-21-fixed:

Fixed
-----

- Fix virtualenv fails sometimes when run concurrently, ``--clear-app-data`` conflicts with :option:`clear` flag when
  abbreviation is turned on. To bypass this while allowing abbreviated flags on the command line we had to move it to
  :option:`reset-app-data` - by :user:`gaborbernat`. (:issue:`1824`)
- Upgrade embedded ``setuptools`` to ``46.4.0`` from ``46.1.3`` on Python ``3.5+``, and ``pip`` from ``20.1`` to
  ``20.1.1`` - by :user:`gaborbernat`. (:pr:`1827`)
- Seeder pip now correctly handles ``--extra-search-dir`` - by :user:`frenzymadness`. (:issue:`1834`)

.. _release-20-0-20:

***********************
 v20.0.20 (2020-05-04)
***********************

.. _release-20-0-20-fixed:

Fixed
-----

- Fix download fails with python 3.4 - by :user:`gaborbernat`. (:issue:`1809`)
- Fixes older CPython2 versions use ``_get_makefile_filename`` instead of ``get_makefile_filename`` on ``sysconfig`` -
  by :user:`ianw`. (:issue:`1810`)
- Fix download is ``True`` by default - by :user:`gaborbernat`. (:pr:`1813`)
- Fail ``app-data`` seed operation when wheel download fails and better error message - by :user:`gaborbernat`.
  (:pr:`1814`)

.. _release-20-0-19:

***********************
 v20.0.19 (2020-05-03)
***********************

.. _release-20-0-19-fixed:

Fixed
-----

- Fix generating a Python 2 environment from Python 3 creates invalid python activator - by :user:`gaborbernat`.
  (:issue:`1776`)
- Fix pinning seed packages via ``app-data`` seeder raised ``Invalid Requirement`` - by :user:`gaborbernat`.
  (:issue:`1779`)
- Do not stop interpreter discovery if we fail to find the system interpreter for a executable during discovery - by
  :user:`gaborbernat`. (:issue:`1781`)
- On CPython2 POSIX platforms ensure ``syconfig.get_makefile_filename`` exists within the virtual environment (this is
  used by some c-extension based libraries - e.g. numpy - for building) - by :user:`gaborbernat`. (:issue:`1783`)
- Better handling of options :option:`copies` and :option:`symlinks`. Introduce priority of where the option is set to
  follow the order: CLI, env var, file, hardcoded. If both set at same level prefers copy over symlink. - by
  :user:`gaborbernat`. (:issue:`1784`)
- Fix CPython is not discovered from Windows registry, and discover pythons from Windows registry in decreasing order by
  version - by :user:`gaborbernat`. (:issue:`1796`)
- Fix symlink detection for creators - by :user:`asottile` (:pr:`1803`)

.. _release-20-0-19-packaging:

Packaging
---------

- Upgrade pip for Python ``2.7`` and ``3.5+`` from ``20.0.2`` to ``20.1`` - by :user:`gaborbernat`. (:pr:`1793`)

.. _release-20-0-18:

***********************
 v20.0.18 (2020-04-16)
***********************

.. _release-20-0-18-fixed:

Fixed
-----

- Importing setuptools before cli_run could cause our python information query to fail due to setuptools patching
  ``distutils.dist.Distribution`` - by :user:`gaborbernat`. (:pr:`1771`)

.. _release-20-0-17:

***********************
 v20.0.17 (2020-04-09)
***********************

.. _release-20-0-17-added:

Added
-----

- Extend environment variables checked for configuration to also check aliases (e.g. setting either
  ``VIRTUALENV_COPIES`` or ``VIRTUALENV_ALWAYS_COPY`` will work) - by :user:`gaborbernat`. (:pr:`1763`)

.. _release-20-0-16:

***********************
 v20.0.16 (2020-04-04)
***********************

.. _release-20-0-16-fixed:

Fixed
-----

- Allow seed wheel files inside the :option:`extra-search-dir` folders that do not have ``Requires-Python`` metadata
  specified, these are considered compatible with all python versions - by :user:`gaborbernat`. (:issue:`1757`)

.. _release-20-0-15:

***********************
 v20.0.15 (2020-03-27)
***********************

.. _release-20-0-15-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``46.1.3`` from ``46.1.1`` - by :user:`gaborbernat`. (:issue:`1752`)

.. _release-20-0-14:

***********************
 v20.0.14 (2020-03-25)
***********************

.. _release-20-0-14-added:

Added
-----

- Remove ``__PYVENV_LAUNCHER__`` on macOs for Python ``3.7.(<8)`` and ``3.8.(<3)`` on interpreter startup via ``pth``
  file, this pulls in the `upstream patch <https://github.com/python/cpython/pull/9516>`_ - by :user:`gaborbernat`.
  (:issue:`1704`)

.. _release-20-0-14-fixed:

Fixed
-----

- Fix discovery of interpreter by name from ``PATH`` that does not match a spec format - by :user:`gaborbernat`.
  (:issue:`1746`)

.. _release-20-0-14-packaging:

Packaging
---------

- Upgrade embedded setuptools for Python ``3.5+`` to ``46.1.1``, for Python ``2.7`` to ``44.1.0`` - by
  :user:`gaborbernat`. (:pr:`1745`)

.. _release-20-0-13:

***********************
 v20.0.13 (2020-03-19)
***********************

.. _release-20-0-13-fixed:

Fixed
-----

- Do not fail when the pyc files is missing for the host Python 2 - by :user:`gaborbernat`. (:issue:`1738`)
- Support broken Packaging pythons that put the include headers under distutils pattern rather than sysconfig one - by
  :user:`gaborbernat`. (:issue:`1739`)

.. _release-20-0-12:

***********************
 v20.0.12 (2020-03-19)
***********************

.. _release-20-0-12-fixed:

Fixed
-----

- Fix relative path discovery of interpreters - by :user:`gaborbernat`. (:pr:`1734`)

.. _release-20-0-11:

***********************
 v20.0.11 (2020-03-18)
***********************

.. _release-20-0-11-added:

Added
-----

- Improve error message when the host python does not satisfy invariants needed to create virtual environments (now we
  print which host files are incompatible/missing and for which creators when no supported creator can be matched,
  however we found creators that can describe the given Python interpreter - will still print no supported creator for
  Jython, however print exactly what host files do not allow creation of virtual environments in case of CPython/PyPy) -
  by :user:`gaborbernat`. (:issue:`1716`)

.. _release-20-0-11-fixed:

Fixed
-----

- Support Python 3 Framework distributed via XCode in macOs Catalina and before - by :user:`gaborbernat`.
  (:issue:`1663`)
- Fix Windows Store Python support, do not allow creation via symlink as that's not going to work by design - by
  :user:`gaborbernat`. (:issue:`1709`)
- Fix ``activate_this.py`` throws ``AttributeError`` on Windows when virtual environment was created via cross python
  mechanism - by :user:`gaborbernat`. (:issue:`1710`)
- Fix ``--no-pip``, ``--no-setuptools``, ``--no-wheel`` not being respected - by :user:`gaborbernat`. (:issue:`1712`)
- Allow missing ``.py`` files if a compiled ``.pyc`` version is available - by :user:`tucked` and :user:`gaborbernat`.
  (:pr:`1714`)
- Do not fail if the distutils/setuptools patch happens on a C-extension loader (such as ``zipimporter`` on Python 3.7
  or earlier) - by :user:`gaborbernat`. (:issue:`1715`)
- Support Python 2 implementations that require the landmark files and ``site.py`` to be in platform standard library
  instead of the standard library path of the virtual environment (notably some RHEL ones, such as the Docker image
  ``amazonlinux:1``) - by :user:`gaborbernat`. (:issue:`1719`)
- Allow the test suite to pass even when called with the system Python - to help repackaging of the tool for Linux
  distributions - by :user:`gaborbernat`. (:issue:`1721`)
- Also generate ``pipx.y`` console script beside ``pip-x.y`` to be compatible with how pip installs itself - by
  :user:`gaborbernat`. (:issue:`1723`)
- Automatically create the application data folder if it does not exists - by :user:`gaborbernat`. (:pr:`1728`)

.. _release-20-0-11-documentation:

Documentation
-------------

- :ref:`supports <compatibility-requirements>` details now explicitly what Python installations we support - by
  :user:`gaborbernat` and :user:`tucked`. (:pr:`1714`)

.. _release-20-0-10:

***********************
 v20.0.10 (2020-03-10)
***********************

.. _release-20-0-10-fixed:

Fixed
-----

- Fix acquiring python information might be altered by distutils configuration files generating incorrect layout virtual
  environments - by :user:`gaborbernat`. (:issue:`1663`)

.. _release-20-0-10-documentation:

Documentation
-------------

- Document requirements (pip + index server) when installing via pip under the installation section - by
  :user:`gaborbernat`. (:issue:`1618`)
- Document installing from non PEP-518 systems - :user:`gaborbernat`. (:issue:`1619`)
- Document installing latest unreleased version from Github - :user:`gaborbernat`. (:issue:`1620`)

.. _release-20-0-10-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``46.0.0`` from ``45.3.0`` on Python ``3.5+`` - by :user:`gaborbernat`. (:pr:`1702`)

.. _release-20-0-9:

**********************
 v20.0.9 (2020-03-08)
**********************

.. _release-20-0-9-fixed:

Fixed
-----

- ``pythonw.exe`` works as ``python.exe`` on Windows - by :user:`gaborbernat`. (:issue:`1686`)
- Handle legacy loaders for virtualenv import hooks used to patch distutils configuration load - by :user:`gaborbernat`.
  (:issue:`1690`)
- Support for python 2 platforms that store landmark files in ``platstdlib`` over ``stdlib`` (e.g. RHEL) - by
  :user:`gaborbernat`. (:issue:`1694`)

.. _release-20-0-9-packaging:

Packaging
---------

- Upgrade embedded setuptools to ``45.3.0`` from ``45.2.0`` for Python ``3.5+`` - by :user:`gaborbernat`. (:pr:`1699`)

.. _release-20-0-8:

**********************
 v20.0.8 (2020-03-04)
**********************

.. _release-20-0-8-fixed:

Fixed
-----

- Having `distutils configuration <https://docs.python.org/3/install/index.html#distutils-configuration-files>`_ files
  that set ``prefix`` and ``install_scripts`` cause installation of packages in the wrong location - by
  :user:`gaborbernat`. (:issue:`1663`)
- Fix ``PYTHONPATH`` being overridden on Python 2 — by :user:`jd` and :user:`gaborbernat`. (:pr:`1673`)
- Fix list configuration value parsing from config file or environment variable - by :user:`gaborbernat`.
  (:issue:`1674`)
- Fix Batch activation script shell prompt to display environment name by default - by :user:`spetafree` and
  :user:`gaborbernat`. (:pr:`1679`)
- Fix startup on Python 2 is slower for virtualenv - this was due to setuptools calculating it's working set
  distribution - by :user:`gaborbernat`. (:issue:`1682`)
- Fix entry points are not populated for editable installs on Python 2 due to setuptools working set being calculated
  before ``easy_install.pth`` runs - by :user:`gaborbernat`. (:issue:`1684`)
- Fix ``attr:`` import fails for setuptools - by :user:`gaborbernat`. (:issue:`1685`)

.. _release-20-0-7:

**********************
 v20.0.7 (2020-02-26)
**********************

.. _release-20-0-7-fixed:

Fixed
-----

- Disable distutils fixup for python 3 until `pypa/pip #7778 <https://github.com/pypa/pip/issues/7778>`_ is fixed and
  released - by :user:`gaborbernat`. (:issue:`1669`)

.. _release-20-0-6:

**********************
 v20.0.6 (2020-02-26)
**********************

.. _release-20-0-6-fixed:

Fixed
-----

- Fix global site package always being added with bundled macOs python framework builds - by :user:`gaborbernat`.
  (:issue:`1561`)
- Fix generated scripts use host version info rather than target - by :user:`gaborbernat`. (:issue:`1600`)
- Fix circular prefix reference with single elements (accept these as if they were system executables, print a info
  about them referencing themselves) - by :user:`gaborbernat`. (:issue:`1632`)
- Handle the case when the application data folder is read-only:

  - the application data folder is now controllable via :option:`app-data`,
  - ``clear-app-data`` now cleans the entire application data folder, not just the ``app-data`` seeder path,
  - check if the application data path passed in does not exist or is read-only, and fallback to a temporary directory,
  - temporary directory application data is automatically cleaned up at the end of execution,
  - :option:`symlink-app-data` is always ``False`` when the application data is temporary

  by :user:`gaborbernat`. (:issue:`1640`)

- Fix PyPy 2 builtin modules are imported from standard library, rather than from builtin - by :user:`gaborbernat`.
  (:issue:`1652`)
- Fix creation of entry points when path contains spaces - by :user:`nsoranzo` and :user:`gaborbernat`. (:pr:`1660`)
- Fix relative paths for the zipapp (for python ``3.7+``) - by :user:`gaborbernat`. (:pr:`1666`)

.. _release-20-0-5:

**********************
 v20.0.5 (2020-02-21)
**********************

.. _release-20-0-5-added:

Added
-----

- Also create ``pythonX.X`` executables when creating pypy virtualenvs - by :user:`asottile` (:issue:`1612`)
- Fail with better error message if trying to install source with unsupported ``setuptools``, allow ``setuptools-scm >=
  2`` and move to legacy ``setuptools-scm`` format to support better older platforms (``CentOS 7`` and such) - by
  :user:`gaborbernat`. (:issue:`1621`)
- Report of the created virtual environment is now split across four short lines rather than one long - by
  :user:`gaborbernat` (:pr:`1641`)

.. _release-20-0-5-fixed:

Fixed
-----

- Add macOs Python 2 Framework support (now we test it with the CI via brew) - by :user:`gaborbernat` (:issue:`1561`)
- Fix losing of libpypy-c.so when the pypy executable is a symlink - by :user:`asottile` (:issue:`1614`)
- Discover python interpreter in a case insensitive manner - by :user:`PrajwalM2212` (:issue:`1624`)
- Fix cross interpreter support when the host python sets ``sys.base_executable`` based on ``__PYVENV_LAUNCHER__`` - by
  :user:`cjolowicz` (:issue:`1643`)

.. _release-20-0-4:

**********************
 v20.0.4 (2020-02-14)
**********************

.. _release-20-0-4-added:

Added
-----

- When aliasing interpreters, use relative symlinks - by :user:`asottile`. (:issue:`1596`)

.. _release-20-0-4-fixed:

Fixed
-----

- Allow the use of ``/`` as pathname component separator on Windows - by :user:`vphilippon` (:issue:`1582`)
- Lower minimal version of six required to 1.9 (:pr:`1606`) - by :user:`ssbarnea`.

.. _release-20-0-3:

**********************
 v20.0.3 (2020-02-12)
**********************

.. _release-20-0-3-fixed:

Fixed
-----

- On Python 2 with Apple Framework builds the global site package is no longer added when the
  :option:`system-site-packages` is not specified - by :user:`gaborbernat`. (:issue:`1561`)
- Fix system python discovery mechanism when prefixes contain relative parts (e.g. ``..``) by resolving paths within the
  python information query - by :user:`gaborbernat`. (:issue:`1583`)
- Expose a programmatic API as ``from virtualenv import cli_run`` - by :user:`gaborbernat`. (:issue:`1585`)
- Fix ``app-data`` :option:`seeder` injects a extra ``.dist-info.virtualenv`` path that breaks ``importlib.metadata``,
  now we inject an extra ``.virtualenv`` - by :user:`gaborbernat`. (:issue:`1589`)

.. _release-20-0-3-documentation:

Documentation
-------------

- Document a programmatic API as ``from virtualenv import cli_run`` under :ref:`programmatic_api` - by
  :user:`gaborbernat`. (:issue:`1585`)

.. _release-20-0-2:

**********************
 v20.0.2 (2020-02-11)
**********************

.. _release-20-0-2-added:

Added
-----

- Print out a one line message about the created virtual environment when no :option:`verbose` is set, this can now be
  silenced to get back the original behavior via the :option:`quiet` flag - by :user:`pradyunsg`. (:issue:`1557`)
- Allow virtualenv's app data cache to be overridden by ``VIRTUALENV_OVERRIDE_APP_DATA`` - by :user:`asottile`.
  (:pr:`1559`)
- Passing in the virtual environment name/path is now required (no longer defaults to ``venv``) - by :user:`gaborbernat`
  and :user:`pradyunsg`. (:pr:`1568`)
- Add a CLI flag :option:`with-traceback` that allows displaying the stacktrace of the virtualenv when a failure occurs
  - by :user:`gaborbernat`. (:pr:`1572`)

.. _release-20-0-2-fixed:

Fixed
-----

- Support long path names for generated virtual environment console entry points (such as ``pip``) when using the
  ``app-data`` :option:`seeder` - by :user:`gaborbernat`. (:issue:`997`)
- Improve python discovery mechanism:

  - do not fail if there are executables that fail to query (e.g. for not having execute access to it) on the ``PATH``,
  - beside the prefix folder also try with the platform dependent binary folder within that,

  by :user:`gaborbernat`. (:issue:`1545`)

- When copying (either files or trees) do not copy the permission bits, last access time, last modification time, and
  flags as access to these might be forbidden (for example in case of the macOs Framework Python) and these are not
  needed for the user to use the virtual environment - by :user:`gaborbernat`. (:issue:`1561`)
- While discovering a python executables interpreters that cannot be queried are now displayed with info level rather
  than warning, so now they're no longer shown by default (these can be just executables to which we don't have access
  or that are broken, don't warn if it's not the target Python we want) - by :user:`gaborbernat`. (:pr:`1574`)
- The ``app-data`` :option:`seeder` no longer symlinks the packages on UNIX and copies on Windows. Instead by default
  always copies, however now has the :option:`symlink-app-data` flag allowing users to request this less robust but
  faster method - by :user:`gaborbernat`. (:pr:`1575`)

.. _release-20-0-2-documentation:

Documentation
-------------

- Add link to the `legacy documentation <https://virtualenv.pypa.io/en/legacy>`_ for the changelog by :user:`jezdez` and
  :user:`gaborbernat`. (:pr:`1547`)
- Fine tune the documentation layout: default width of theme, allow tables to wrap around, soft corners for code
  snippets - by :user:`pradyunsg` and :user:`gaborbernat`. (:pr:`1548`)

.. _release-20-0-1:

**********************
 v20.0.1 (2020-02-10)
**********************

.. _release-20-0-1-fixed:

Fixed
-----

- Virtual environments created via relative path on Windows creates bad console executables - by :user:`gaborbernat`.
  (:issue:`1552`)
- Seems sometimes venvs created set their base executable to themselves; we accept these without question, so we handle
  virtual environments as system pythons causing issues - by :user:`gaborbernat`. (:issue:`1553`)

.. _release-20-0-1-packaging:

Packaging
---------

- upgrade embedded setuptools to ``45.2.0`` from ``45.1.0`` for Python ``3.4+`` - by :user:`gaborbernat`. (:pr:`1554`)

.. _release-20-0-0:

**********************
 v20.0.0 (2020-02-10)
**********************

.. _release-20-0-0-documentation:

Documentation
-------------

- Fixes typos, repeated words and inconsistent heading spacing. Rephrase parts of the development documentation and CLI
  documentation. Expands shorthands like ``env var`` and ``config`` to their full forms. Uses descriptions from
  respective documentation, for projects listed in ``related links`` - by :user:`pradyunsg`. (:pr:`1540`)

.. _release-20-0-0b2:

************************
 v20.0.0b2 (2020-02-04)
************************

.. _release-20-0-0b2-added:

Added
-----

- Improve base executable discovery mechanism:

  - print at debug level why we refuse some candidates,
  - when no candidates match exactly, instead of hard failing fallback to the closest match where the priority of
    matching attributes is: python implementation, major version, minor version, architecture, patch version, release
    level and serial (this is to facilitate things to still work when the OS upgrade replace/upgrades the system python
    with a never version, than what the virtualenv host python was created with),
  - always resolve system_executable information during the interpreter discovery, and the discovered environment is the
    system interpreter instead of the venv/virtualenv (this happened before lazily the first time we accessed, and
    caused reporting that the created virtual environment is of type of the virtualenv host python version, instead of
    the system pythons version - these two can differ if the OS upgraded the system python underneath and the virtualenv
    host was created via copy),

  by :user:`gaborbernat`. (:issue:`1515`)

- Generate ``bash`` and ``fish`` activators on Windows too (as these can be available with git bash, cygwin or mysys2) -
  by :user:`gaborbernat`. (:issue:`1527`)
- Upgrade the bundled ``wheel`` package from ``0.34.0`` to ``0.34.2`` - by :user:`gaborbernat`. (:pr:`1531`)

.. _release-20-0-0b2-fixed:

Fixed
-----

- Bash activation script should have no extensions instead of ``.sh`` (this fixes the :pypi:`virtualenvwrapper`
  integration) - by :user:`gaborbernat`. (:issue:`1508`)
- Show less information when we run with a single verbosity (``-v``):

  - no longer shows accepted interpreters information (as the last proposed one is always the accepted one),
  - do not display the ``str_spec`` attribute for ``PythonSpec`` as these can be deduced from the other attributes,
  - for the ``app-data`` seeder do not show the type of lock, only the path to the app data directory,

  By :user:`gaborbernat`. (:issue:`1510`)

- Fixed cannot discover a python interpreter that has already been discovered under a different path (such is the case
  when we have multiple symlinks to the same interpreter) - by :user:`gaborbernat`. (:issue:`1512`)
- Support relative paths for ``-p`` - by :user:`gaborbernat`. (:issue:`1514`)
- Creating virtual environments in parallel fail with cannot acquire lock within app data - by :user:`gaborbernat`.
  (:issue:`1516`)
- pth files were not processed under Debian CPython2 interpreters - by :user:`gaborbernat`. (:issue:`1517`)
- Fix prompt not displayed correctly with upcoming fish 3.10 due to us not preserving ``$pipestatus`` - by
  :user:`krobelus`. (:pr:`1530`)
- Stable order within ``pyenv.cfg`` and add ``include-system-site-packages`` only for creators that reference a global
  Python (:pr:`1535`) - by :user:`gaborbernat`.

.. _release-20-0-0b2-documentation:

Documentation
-------------

- Create the first iteration of the new documentation - by :user:`gaborbernat`. (:issue:`1465`)
- Project readme is now of type MarkDown instead of reStructuredText - by :user:`gaborbernat`. (:pr:`1531`)

.. _release-20-0-0b1:

************************
 v20.0.0b1 (2020-01-28)
************************

.. _release-20-0-0b1-added:

Added
-----

- First public release of the rewrite.

.. _release-20-0-0b1-changes:

Changes
-------

- ``--download`` defaults to ``False``.

.. _release-20-0-0b1-removed:

Removed
-------

- Stop replacing the built-in ``site`` module with a `custom version baked into virtualenv
  <https://github.com/pypa/virtualenv/blob/legacy/virtualenv_embedded/site.py>`_. A shim remains for Python 2.

.. warning::

    The current virtualenv is the second iteration of implementation. From version ``0.8`` all the way to ``16.7.9`` we
    numbered the first iteration. Version ``20.0.0b1`` is a complete rewrite of the package, and as such this release
    history starts from there. The old changelog is still available in the `legacy branch documentation
    <https://virtualenv.pypa.io/en/legacy/changes.html>`_.
