# Security Policy

`virtualenv` creates Python environments. A small team maintains it: [Bernát Gábor](https://github.com/gaborbernat)
handles most day-to-day work and answers fastest, with [Rahul Devikar](https://github.com/rahuldevikar) and
[Paul Moore](https://github.com/pfmoore) in backup roles. [Tidelift](https://tidelift.com/security) supports the
project. This policy says how to report a security problem, what happens next, and how long it takes.

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting:

1. Go to [the advisory form](https://github.com/pypa/virtualenv/security/advisories/new).
1. Fill in what you found. Everything stays private until an advisory is published.
1. Submit. The report reaches the maintainers directly.

If you do not have a GitHub account, or you are a Tidelift subscriber, report through the
[Tidelift security contact](https://tidelift.com/security) instead. Tidelift coordinates the fix and the disclosure with
us. If you subscribe to Tidelift, prefer that path: it carries a contractual response time the project cannot offer on
its own.

### What to include

- What the problem is and what an attacker gains from it.
- The steps or a proof of concept that reproduce it.
- The versions, operating system and Python you tested against.
- Any mitigation you already know of.
- A severity estimate, and a CWE identifier if you know one.

Write the report yourself. Reports that consist of unreviewed tool or model output take longer to triage, and we may
close them without a detailed reply.

## What to expect

We are volunteers, with no on-call rotation and no 24-hour incident response. The targets are an acknowledgment within
**5 working days** and an assessment within **15 working days**. Those are targets and not guarantees. Tidelift
subscribers get a committed response time through the Tidelift lane.

If two weeks pass with no acknowledgment at all, escalate through the
[Tidelift security contact](https://tidelift.com/security).

## Supported versions

Only the most recent release is supported. Fixes ship in a new release rather than as backports to older lines.

virtualenv follows a backwards-compatible release policy, so upgrading to the newest version is usually a small change.
Before reporting, confirm the problem still reproduces on the latest release.

## Scope

virtualenv takes values from whoever runs it, such as the destination path and `--prompt`, and from the network, such as
the seed wheels it downloads. It turns those values into shell scripts, into `pyvenv.cfg`, and into files on disk. That
conversion is the boundary this policy cares about.

**In scope**

- Caller-supplied values changing the meaning of a generated script rather than appearing as data, in any activator:
  `activate`, `activate.bat`, `activate.csh`, `activate.fish`, `activate.nu`, `Activate.ps1`, `activate.xsh`.
- The same problem in `pyvenv.cfg` or any other file virtualenv writes.
- Missing or incorrect integrity checking of anything virtualenv downloads, including seed wheels and app-data cache
  entries.
- virtualenv writing outside the directory it was pointed at, whether through a symlink, a race or path handling.
- Files or directories created with wider permissions than intended.

**Out of scope**

- An attacker who already has arbitrary command execution as the victim, or can replace the victim's executables or
  app-data contents. This does not exclude an attacker who controls only a value that a caller passes to virtualenv,
  such as project metadata used as a prompt or destination path.
- Tricking a user into executing shell syntax in the command they use to launch virtualenv. Injection from argument data
  into a generated activation script or configuration file remains in scope.
- Code that runs from packages virtualenv seeds or that are installed into the environment afterwards. Report malware on
  PyPI to [PyPI security](https://pypi.org/security/).
- Vulnerabilities in pip or setuptools themselves. Report those to their own projects.
- Test code and test fixtures.
- Unreleased code on `main`.
- Anything reachable only on a Python version virtualenv no longer supports.

If you cannot tell which side a finding falls on, report it and we will assess it.

## How a report is handled

1. **Triage.** Confirm the report, decide whether it is a vulnerability under the scope above, and set a severity.
1. **Fix in private.** We work in a temporary private fork attached to the draft advisory.
1. **Embargo.** The default window is **90 days** from the report. It shrinks when a problem is being exploited and can
   grow when a fix turns out to be hard. We agree any change with the reporter.
1. **Identifier.** We request a CVE through GitHub once a fix exists.
1. **Release.** The fix ships in a new release, and we publish the advisory alongside it.

## Credit

We credit reporters in the advisory under whatever name or alias they ask for, and they can stay anonymous. GitHub sends
a credit invitation that the reporter has to accept, so a name appears only with their agreement.

## If the problem becomes public early

The embargo ends when the details are public. At that point the advisory goes out with whatever mitigation exists, and a
fix follows as soon as one is ready. Advance warning that a report is about to be published is welcome and far better
than finding out from the timeline.

## Bug bounty

There is none. This project does not pay for reported vulnerabilities.

## Published advisories

Past advisories are at [the project's advisory list](https://github.com/pypa/virtualenv/security/advisories). To be
notified of new ones, open the repository page and choose **Watch**, then **Custom**, then enable **Security alerts**.
