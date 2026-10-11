# Threat model

The project's own policy is [.github/SECURITY.md](../.github/SECURITY.md), and the full threat model with its assurance
case is [.github/THREAT_MODEL.md](../.github/THREAT_MODEL.md). This file summarizes them for the scanner. Where they
disagree, SECURITY.md wins.

## What this project does and where untrusted input enters

virtualenv creates Python virtual environments. It runs as the `virtualenv` command, as `python -m virtualenv`, as a
zipapp, and through the Python API (`virtualenv.cli_run`), which tox and hatch call with values they read from project
configuration. A run has four stages, each a plugin loaded from entry points (`src/virtualenv/run/plugin/`):

1. Discovery (`src/virtualenv/discovery/`) finds the target interpreter, runs it in a subprocess
   (`discovery/py_info.py`, `discovery/cached_py_info.py`) and caches the result in the app-data directory.
1. Creation (`src/virtualenv/create/`) writes the environment: interpreter links or copies, `pyvenv.cfg`
   (`create/pyenv_cfg.py`), `_virtualenv.py`/`.pth` into site-packages, `CACHEDIR.TAG` and `.gitignore`.
1. Seeding (`src/virtualenv/seed/`) installs pip and setuptools from the wheels embedded in `seed/wheels/embed/`, from
   newer wheels the periodic update downloaded into app-data (`seed/wheels/periodic_update.py`), from
   `--extra-search-dir`, or from PyPI with `--download` (`seed/wheels/acquire.py`). The app-data seeder extracts wheels
   into a cached image and links or copies them (`seed/embed/via_app_data/`).
1. Activation (`src/virtualenv/activation/`) renders one script per shell from templates: bash, batch, csh, fish,
   Nushell, PowerShell, xonsh and Python (`activate_this.py`). It substitutes the destination path, the prompt, the
   interpreter path and the Tcl/Tk paths.

virtualenv runs with the rights of the user who starts it. The user and their environment are trusted: command line
options, `VIRTUALENV_*` environment variables (`config/env_var.py`), the `virtualenv.ini` file (`config/ini.py`), `PATH`
and the interpreters found on it, pip's configuration, installed plugins, `--extra-search-dir` contents and the user's
app-data directory.

Untrusted input is:

- values a caller passes on someone else's behalf, chiefly the destination path and `--prompt`. tox and hatch derive
  these from project metadata the user did not write, so they may contain quotes, `$`, backticks, `%`, `!`, newlines,
  and non-ASCII text;
- wheel bytes and metadata from PyPI, fetched by the periodic update and by `--download`, which virtualenv checks
  against the SHA-256 digest PyPI's JSON API publishes;
- wheel archives being extracted into app-data (entry names, symlinks);
- the embedded wheels, which virtualenv hashes against the table in `seed/wheels/embed/__init__.py` before first use,
  including when reading from inside the zipapp (`util/zipapp.py`).

## Components that matter most / least

Most:

- the activators and their quoting, in `src/virtualenv/activation/*/__init__.py`, the templates beside them, and
  `activation/via_template.py`. The batch activator also has logic to refuse paths it cannot quote;
- the `pyvenv.cfg` writer (`create/pyenv_cfg.py`) and the line boundary helper (`util/text.py`);
- wheel acquisition and integrity checks: `seed/wheels/acquire.py`, `seed/wheels/bundle.py`,
  `seed/wheels/periodic_update.py`, `seed/wheels/embed/__init__.py`;
- wheel extraction and linking into app-data and the environment: `seed/embed/via_app_data/`, `app_data/`,
  `util/zipapp.py`;
- filesystem writes that could escape the destination or follow a symlink: `create/creator.py`, `util/path/`,
  `util/lock.py`;
- arguments passed to `pip download` and other subprocesses (`seed/embed/pip_invoke.py`, `util/subprocess/`).

Least: discovery of interpreters on `PATH` (the interpreter is trusted), `report.py`, the CLI help text, and everything
under `tasks/` (release and CI tooling) and `docs/`. Test code and fixtures are out of scope.

## How to exercise it

The repository is at `/src`, installed in editable mode into a virtual environment at `/opt/venv` that is on `PATH`,
with the `test`, `property` and `fuzz` dependency groups. bash, csh, tcsh, fish, nu, pwsh and xonsh are installed, so
the activator tests run the generated scripts in real shells.

- Create an environment: `virtualenv --no-periodic-update --prompt '<payload>' '/tmp/<payload>/venv'`, then source the
  activation script in the matching shell. `--activators bash,fish` limits which scripts are written.
- Unit tests: `python -m pytest tests/unit -n auto`. Activator tests are in `tests/unit/activation/` (one file per
  shell), `pyvenv.cfg` in `tests/unit/create/test_creator.py`, seeding and wheel checks in `tests/unit/seed/`.
- Property tests: `python -m pytest tests/property -m property`, covering batch quoting and the `pyvenv.cfg` writer.
- Fuzz targets: `python tasks/fuzz_pyenv_cfg.py -runs=20000`, and the same for `tasks/fuzz_nushell_quote.py` and
  `tasks/fuzz_powershell_quote.py`.
- Integration tests need `--int`; the zipapp test may need network: `python -m pytest tests/integration --int`.

The scan has no network, so `--download`, the periodic update and the PyPI digest check can only be exercised with the
mocks the tests use.

## How you rate severity

The levels are those in `.github/INCIDENT_RESPONSE.md`.

- High: attacker-chosen data becomes code on a normal path with no unusual setup. A destination path or `--prompt` that
  makes any activation script run a command when sourced is high (GHSA-x78j-v8h9-3j2q in `activate.bat`,
  GHSA-p58f-9548-mpm2 in bash and fish). So is a downloaded seed wheel that is used despite failing or skipping the
  SHA-256 check without the user opting out, and wheel extraction that writes outside app-data.
- Medium: real damage that needs a race, a specific configuration or local timing, such as a TOCTOU gap in directory
  creation (GHSA-597g-3phw-6986), or a caller value that adds a key or line to `pyvenv.cfg` (GHSA-9h9j-4vrj-gf7g).
  Writing outside the destination through a symlink, or creating files with wider permissions than intended, is medium
  unless it gives code execution.
- Low: an integrity or correctness failure with narrow effect (GHSA-94p9-xgh2-xp45), and denial of service such as a
  crash or a hang on a crafted path or wheel.

## Anything to leave alone

These are out of scope in SECURITY.md or accepted risks in THREAT_MODEL.md:

- an attacker who already runs code as the user, or can write to the user's app-data directory, `PATH`, interpreters,
  `virtualenv.ini`, `VIRTUALENV_*` variables or `--extra-search-dir`. Cached wheels and cached interpreter info in
  app-data are read back without re-hashing by design;
- shell syntax in the command the user types to launch virtualenv, as opposed to data that reaches a generated file;
- code in pip, setuptools or packages installed into the environment, and plugins registered through entry points;
- skipping the PyPI digest check when `PIP_INDEX_URL`, `PIP_EXTRA_INDEX_URL` or `PIP_INDEX` is set, and the unverified
  TLS fallback behind `VIRTUALENV_PERIODIC_UPDATE_INSECURE`;
- a privileged user running virtualenv on a directory a less privileged user can write;
- `pyvenv.cfg` recording the interpreter path and the creating command;
- the release workflows and CI configuration, test code and fixtures, and Python versions virtualenv no longer supports.
