# virtualenv installed from source the way CI installs it (.github/workflows/check.yaml and tox.toml in the virtualenv
# repository), with the shells whose activation scripts the tests run.
FROM python:3.14-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg bash csh tcsh fish \
    && rm -rf /var/lib/apt/lists/*

# Nushell from the repository CI uses, and PowerShell from Microsoft's, because Debian packages neither.
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://apt.fury.io/nushell/gpg.key | gpg --dearmor -o /etc/apt/keyrings/fury-nushell.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/fury-nushell.gpg] https://apt.fury.io/nushell/ /" \
      > /etc/apt/sources.list.d/fury.list \
    && curl -fsSL -o /tmp/packages-microsoft-prod.deb \
      https://packages.microsoft.com/config/debian/12/packages-microsoft-prod.deb \
    && dpkg -i /tmp/packages-microsoft-prod.deb && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update && apt-get install -y --no-install-recommends nushell powershell \
    && rm -rf /var/lib/apt/lists/*

# A virtual environment on PATH, as tox gives the tests: some tests skip or change behavior under a system Python.
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The package with the test, property (Hypothesis) and fuzz (Atheris) dependency groups, plus xonsh for its activator
# tests. hatch-vcs reads the version from git, so pin one when the checkout has no history.
RUN pip install --upgrade pip \
    && if ! git -C /src rev-parse --git-dir >/dev/null 2>&1; then export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0; fi \
    && pip install -e . --group test --group property --group fuzz xonsh

# Run the fast unit tests so you know the image works, but do not let a failing test abort the build.
RUN python -m pytest tests/unit --skip-slow -n auto -p no:randomly \
    || echo "WARNING: virtualenv unit tests reported failures"
