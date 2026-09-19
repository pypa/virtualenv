# Incident Response Plan

How a security problem in virtualenv gets handled once someone reports it. For how to report one, and for what counts as
a vulnerability, read [SECURITY.md](SECURITY.md) instead.

This is a living document. It changes after each incident that shows it is wrong.

## What counts as an incident

A vulnerability in virtualenv itself, or in one of the pip and setuptools wheels bundled under
`src/virtualenv/seed/wheels/embed/`, is the usual case. Three others count and need a different response:

- A tampered release artifact, on PyPI, in a GitHub Release, or at `bootstrap.pypa.io/virtualenv.pyz`.
- Commits, tags or releases that no maintainer made, or a change to the trusted publisher configuration.
- A compromised maintainer account.

The last three are less likely than a code bug and worse when they happen, which is why they get their own containment
step below.

## Who responds

[Bernát Gábor](https://github.com/gaborbernat) leads the response, because he does most of the day-to-day work and
answers fastest. [Rahul Devikar](https://github.com/rahuldevikar) and [Paul Moore](https://github.com/pfmoore) back that
up. Nothing here depends on who is available: anyone holding release rights can run this plan, and the lead for a given
incident is whoever picks it up.

We are volunteers, with no rotation and no out-of-hours cover. The targets in [SECURITY.md](SECURITY.md) are what this
team can meet on a good week, not a service level. [Tidelift](https://tidelift.com/security) is the lane that carries a
committed acknowledgment, and it handles intake, the first reply and coordination on release timing. Triage, the fix,
the release and the announcement stay here.

A reporter, or a contributor already trusted with review, may be invited into the private advisory to help build or
check a fix.

## Severity

Four levels, set by judgment rather than a calculator. virtualenv is a library and a command line tool, and a score
computed without knowing how a caller invokes it says little. curl, the ASF and OpenSSL all reach the same conclusion
for the same reason, and GitHub's advisory form accepts a plain severity with no vector attached.

| Level    | Meaning                                                                                               | Example from this project                                                       |
| -------- | ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Critical | A tampered artifact reached users, or an account or publishing credential is in someone else's hands. | none so far                                                                     |
| High     | Attacker-chosen data becomes code on a normal path, with no unusual setup.                            | `GHSA-x78j-v8h9-3j2q`, command injection through `--prompt` into `activate.bat` |
| Medium   | Real damage that needs a race, a specific configuration, or local timing to land.                     | `GHSA-597g-3phw-6986`, a time-of-check to time-of-use gap in directory creation |
| Low      | A correctness or integrity failure with a narrow or hard-to-reach effect.                             | `GHSA-94p9-xgh2-xp45`, seed wheels used without an integrity check              |

Severity decides two things. High and Critical get a private fork and an out-of-band release. Low and Medium may be
fixed through an ordinary pull request that does not advertise itself as a security fix, and may wait for the next
release. Anyone scoring the same issue with CVSS afterwards may land somewhere else, and that is expected.

## Where reports come from

The [advisory form](https://github.com/pypa/virtualenv/security/advisories/new), the Tidelift contact, Dependabot and
CodeQL, and a public issue that turns out to be worse than it looked and gets moved into a private advisory.
Self-discovery during ordinary work is also a real source: every advisory published against virtualenv so far started
that way.

## Response

**Triage.** Confirm the problem, open or adopt a private advisory, set a severity, and decide whether
[SECURITY.md](SECURITY.md) puts it in scope. Reply to the reporter either way. An out-of-scope report gets a reason, not
silence.

**Contain.** Only for the artifact, account and credential cases above. Yank the affected release from PyPI, revoke the
publishing credentials and the `release` environment, check every tag against a known good commit, roll back
`bootstrap.pypa.io/virtualenv.pyz`, and re-examine anything published while the access was open.

**Measure the blast radius.** For anything beyond a plain code bug, write down whether there is evidence of real
exploitation and how confident that answer is. Guessing in public later is worse than recording uncertainty now.

**Fix.** High and Critical are built in the temporary private fork attached to the advisory. Low and Medium go through a
normal pull request. Either way the fix carries a regression test, and nothing in a commit message, branch name or issue
says "security" until disclosure.

**Release.** Follow the usual release process in `docs/development.rst`. Remember there are three surfaces: PyPI, the
GitHub Release zipapp, and `bootstrap.pypa.io/virtualenv.pyz`.

**Disclose.** Publish the advisory with the release. Request a CVE through GitHub. Credit the reporter as they asked to
be credited. Close any duplicate draft advisories covering the same issue, so the published record has one entry per
problem.

**Learn.** See below.

## After the incident

Within a few days of the release, write a short account in the advisory itself: a timeline, what was affected, the root
cause with a link to the commit or pull request that introduced it, and what the fix changed. Say what worked and what
did not. The account blames the process rather than a person: on a team this small, blaming a person produces nothing
useful and discourages the next write-up.

Hardening work and process gaps that the incident exposed do not belong in the closed advisory, where nobody will read
them again. They become ordinary public issues. Keeping them separate is what stops the incident from expanding while it
is still open, and stops the follow-up from being quietly dropped once the release ships.

## Keeping this current

Review after every incident, and at least once a year even without one. An incident that this plan handled badly is the
best reason to change it, and the only time the gaps are obvious.
