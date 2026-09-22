# Assurance Case

The argument that virtualenv meets the security requirements it states, and the evidence behind each step.
[SECURITY.md](SECURITY.md) sets the requirements and says how to report a problem, [THREAT_MODEL.md](THREAT_MODEL.md)
lists the threats, and [INCIDENT_RESPONSE.md](INCIDENT_RESPONSE.md) covers what happens after a report. This document
ties them to the code and to the tests that keep each fix in place.

## Review record

[Bernát Gábor](https://github.com/gaborbernat) performed this review on 2026-09-22 against `main` at commit `e3de9da`,
which is release 21.10.0 plus one CI change. For each requirement below Bernát read the code that enforces it, the pull
request and advisory that introduced the fix, and the tests that exercise it, and confirmed every file path listed here
exists at that commit. Bernát also checked the workflows and the repository's Actions settings for the least privilege
claims.

One maintainer wrote and reviewed this document, so it carries the blind spots of one reader. The project runs on a
single-maintainer workflow: Bernát Gábor maintains it, [Rahul Devikar](https://github.com/rahuldevikar) covers when
Bernát is unavailable, and [Paul Moore](https://github.com/pfmoore) is the backup if both step away. If you find a claim
here that the code does not support, report it as SECURITY.md describes.

We repeat the review when a change hits one of the triggers listed at the end of THREAT_MODEL.md, after every published
advisory, and at least once a year.

## Security requirements

The in-scope list in [SECURITY.md](SECURITY.md#scope) defines what virtualenv promises:

1. A value the caller passes in, such as the destination path or `--prompt`, reaches every activation script as data and
   never changes what the script does.
1. The same holds for `pyvenv.cfg` and every other file virtualenv writes.
1. virtualenv checks the integrity of what it downloads before it uses it.
1. virtualenv does not write outside the directory the caller named, whether through a symlink, a race or path handling.
1. virtualenv does not create files or directories with wider permissions than intended.

This document argues that the release at the commit above meets these five requirements, with the exceptions
THREAT_MODEL.md records as accepted risks.

## Threat model

[THREAT_MODEL.md](THREAT_MODEL.md), which arrives with [#3294](https://github.com/pypa/virtualenv/pull/3294), holds the
full model: what virtualenv trusts, the assets, two data-flow diagrams, a STRIDE table ranked by risk, and the
supply-chain threats. virtualenv runs with the rights of the user who starts it and trusts that user, the target
interpreter, the app-data directory and installed plugins. The attacker we defend against controls a value that a tool
such as tox or hatch passes to virtualenv from project metadata, or sits between virtualenv and PyPI. An attacker who
can already run code as the user, or write to the user's app-data directory, is out of scope.

## Trust boundaries

The Scope section of [SECURITY.md](SECURITY.md#scope) names the boundary: virtualenv turns caller values and network
bytes into shell scripts, `pyvenv.cfg` and files on disk. THREAT_MODEL.md splits that into four crossings.

| Boundary | Crossing                                                                        | Requirement |
| -------- | ------------------------------------------------------------------------------- | ----------- |
| TB1      | Caller values into activation scripts and `pyvenv.cfg`                          | 1, 2        |
| TB2      | Wheel bytes from an index into app-data and then an environment                 | 3           |
| TB3      | Built artifacts from GitHub Actions to PyPI, GitHub Releases and get-virtualenv | release     |
| TB4      | Code from contributors and dependencies into a release                          | release     |

Requirements 4 and 5 apply wherever virtualenv touches the filesystem, on both sides of TB1 and TB2.

## Secure design principles

**Least privilege.** Every workflow except `scorecard.yaml` and `upgrade.yaml` starts from `permissions: {}` and grants
each job only what it needs; `scorecard.yaml` starts read-only and `upgrade.yaml` starts at `contents: read`. The
repository's default workflow token is read-only, and GitHub rejects any action not pinned to a full commit SHA.
Checkouts set `persist-credentials: false`, except in `pre-release.yaml`, which pushes the release commit and tag with
`GH_RELEASE_TOKEN`. PyPI uploads use trusted publishing, so no long-lived PyPI token exists. Inside the tool, when the
app-data seeder links packages by symlink, it marks the extracted wheel image read-only (`set_tree` in
`src/virtualenv/seed/embed/via_app_data/pip_install/symlink.py`).

**Fail-safe defaults.** A failed TLS handshake with PyPI aborts the periodic update instead of retrying without
verification; the unverified fallback needs `VIRTUALENV_PERIODIC_UPDATE_INSECURE` set by the user
([#3122](https://github.com/pypa/virtualenv/pull/3122)). virtualenv refuses a seed wheel whose SHA-256 does not match
before caching or using it. The batch activator logs a warning and writes no batch scripts for a path it cannot quote
without changing it ([#3280](https://github.com/pypa/virtualenv/pull/3280)).

**Complete mediation.** Every caller value that enters a generated script goes through the activator's `quote()` at
render time, with one quoting rule per shell: `shlex.quote` for POSIX shells, extra escaping for csh history and prompt
expansion, and separate rules for batch, PowerShell, Nushell, xonsh and Python. Every key and value written to
`pyvenv.cfg` goes through `collapse_line_boundaries` in `src/virtualenv/util/text.py`. virtualenv hashes each bundled
wheel before first use in each process, including when it reads the wheel from inside the zipapp.

**Economy of mechanism.** One helper, `collapse_line_boundaries`, handles line breaks for both `pyvenv.cfg` and the
batch activator. Wheel integrity uses one comparison, a SHA-256 against a table (`BUNDLE_SHA256`) for bundled wheels and
against PyPI's published digest for downloaded ones. virtualenv implements no cryptography of its own.

**Open design.** The code, the workflows, the threat model and this document are public. None of the defenses depends on
an attacker not knowing how they work, and every past advisory is public at
<https://github.com/pypa/virtualenv/security/advisories>.

## Common weaknesses countered

Each row names a weakness class that applies to what virtualenv does, the fix that counters it, and the tests that fail
if the fix regresses. CI runs the unit tests, the Hypothesis property tests (`tox -e property`) and the Atheris fuzz
targets (`tox -e fuzz`) on every pull request.

| Weakness                                 | Where it applies                                                                  | Fix                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Tests                                                                                                                                                                                                                                                                                                                                                                                                                          |
| ---------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| CWE-78 OS command injection              | Destination path and `--prompt` in activators                                     | Batch quoting, [#3250](https://github.com/pypa/virtualenv/pull/3250) ([GHSA-x78j-v8h9-3j2q](https://github.com/pypa/virtualenv/security/advisories/GHSA-x78j-v8h9-3j2q)), and refusing paths that quoting would alter, [#3280](https://github.com/pypa/virtualenv/pull/3280). Path handling in bash and fish, [#3252](https://github.com/pypa/virtualenv/pull/3252) ([GHSA-p58f-9548-mpm2](https://github.com/pypa/virtualenv/security/advisories/GHSA-p58f-9548-mpm2)). csh history and prompt expansion, [#3256](https://github.com/pypa/virtualenv/pull/3256) and [#3263](https://github.com/pypa/virtualenv/pull/3263). | [`test_batch.py`](../tests/unit/activation/test_batch.py), [`test_batch_quote.py`](../tests/property/test_batch_quote.py), [`test_bash.py`](../tests/unit/activation/test_bash.py), [`test_fish.py`](../tests/unit/activation/test_fish.py), [`test_csh.py`](../tests/unit/activation/test_csh.py), [`fuzz_powershell_quote.py`](../tasks/fuzz_powershell_quote.py), [`fuzz_nushell_quote.py`](../tasks/fuzz_nushell_quote.py) |
| CWE-93 CRLF injection                    | Keys and values written to `pyvenv.cfg`                                           | Line boundaries collapsed to spaces, [#3247](https://github.com/pypa/virtualenv/pull/3247) ([GHSA-9h9j-4vrj-gf7g](https://github.com/pypa/virtualenv/security/advisories/GHSA-9h9j-4vrj-gf7g))                                                                                                                                                                                                                                                                                                                                                                                                                              | [`test_pyenv_cfg.py`](../tests/property/test_pyenv_cfg.py), [`fuzz_pyenv_cfg.py`](../tasks/fuzz_pyenv_cfg.py)                                                                                                                                                                                                                                                                                                                  |
| CWE-88 argument injection                | Distribution and version passed to `pip download`                                 | Both validated before the call, [#3120](https://github.com/pypa/virtualenv/pull/3120)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       | [`test_acquire.py`](../tests/unit/seed/wheels/test_acquire.py)                                                                                                                                                                                                                                                                                                                                                                 |
| CWE-22 path traversal                    | Wheel extraction into app-data, zipapp reads                                      | Archive entries validated before extraction, [#3118](https://github.com/pypa/virtualenv/pull/3118). Zipapp reads confined to the archive root, [#3121](https://github.com/pypa/virtualenv/pull/3121)                                                                                                                                                                                                                                                                                                                                                                                                                        | [`test_bootstrap_link_via_app_data.py`](../tests/unit/seed/embed/test_bootstrap_link_via_app_data.py), [`test_util.py`](../tests/unit/test_util.py)                                                                                                                                                                                                                                                                            |
| CWE-59 link following                    | Copying into an existing environment                                              | virtualenv replaces a stale symlink at the destination instead of writing through it, [#3229](https://github.com/pypa/virtualenv/pull/3229)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | [`test_util.py`](../tests/unit/test_util.py), [`test_creator.py`](../tests/unit/create/test_creator.py)                                                                                                                                                                                                                                                                                                                        |
| CWE-367 TOCTOU race                      | App-data and lock directory creation                                              | Check-then-create replaced with `os.makedirs(..., exist_ok=True)`, [#3013](https://github.com/pypa/virtualenv/pull/3013) ([GHSA-597g-3phw-6986](https://github.com/pypa/virtualenv/security/advisories/GHSA-597g-3phw-6986), CVE-2026-22702)                                                                                                                                                                                                                                                                                                                                                                                | No regression test came with the fix. `test_reentrant_file_lock_is_thread_safe` in [`test_util.py`](../tests/unit/test_util.py) and `test_app_data_parallel_ok` in [`test_bootstrap_link_via_app_data.py`](../tests/unit/seed/embed/test_bootstrap_link_via_app_data.py) run concurrent creation.                                                                                                                              |
| CWE-295 certificate validation           | PyPI metadata request in the periodic update                                      | No silent fallback to unverified TLS, [#3122](https://github.com/pypa/virtualenv/pull/3122)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | [`test_periodic_update.py`](../tests/unit/seed/wheels/test_periodic_update.py)                                                                                                                                                                                                                                                                                                                                                 |
| CWE-494 download without integrity check | Bundled and downloaded seed wheels                                                | Bundled wheels checked against `BUNDLE_SHA256`, [#3119](https://github.com/pypa/virtualenv/pull/3119). Downloaded wheels checked against PyPI's digest, [#3251](https://github.com/pypa/virtualenv/pull/3251) ([GHSA-94p9-xgh2-xp45](https://github.com/pypa/virtualenv/security/advisories/GHSA-94p9-xgh2-xp45))                                                                                                                                                                                                                                                                                                           | [`test_bundle.py`](../tests/unit/seed/wheels/test_bundle.py), [`test_acquire.py`](../tests/unit/seed/wheels/test_acquire.py), [`test_periodic_update.py`](../tests/unit/seed/wheels/test_periodic_update.py)                                                                                                                                                                                                                   |
| CWE-732 incorrect permissions            | Wheel image in app-data, deleting read-only files, executables in the environment | In symlink mode the wheel image is read-only. To delete a read-only file, `safe_delete` adds owner write and keeps the other bits, [#3222](https://github.com/pypa/virtualenv/pull/3222). `make_exe` adds execute bits and nothing else.                                                                                                                                                                                                                                                                                                                                                                                    | `test_safe_delete_keeps_the_other_mode_bits_when_clearing_read_only` in [`test_util.py`](../tests/unit/test_util.py)                                                                                                                                                                                                                                                                                                           |

Beyond these rows, ruff runs with every rule enabled, including the flake8-bandit `S` rules, as a required pre-commit.ci
check, and CodeQL scans the Python code and the workflows. zizmor checks the workflows for template injection and
credential persistence.

## Residual risk

The accepted risks and open items in THREAT_MODEL.md are the places where this argument stops. Two of them bear on the
requirements above. The PyPI digest check passes with a log line when the metadata request fails or when the user sets a
custom index through an environment variable, and virtualenv does not re-hash wheels from `--extra-search-dir` or the
app-data cache on use. The CWE-367 fix has no dedicated regression test, and virtualenv does not defend against another
user racing it inside a directory both can write.
