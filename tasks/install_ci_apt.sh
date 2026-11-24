#!/usr/bin/env bash
set -euo pipefail

sources=$(mktemp "$RUNNER_TEMP/virtualenv-apt.XXXXXX.list")
trap 'rm -f "$sources"' EXIT
cat > "$sources" <<'EOF'
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu/ noble main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://archive.ubuntu.com/ubuntu/ noble-updates main universe
deb [signed-by=/usr/share/keyrings/ubuntu-archive-keyring.gpg] http://security.ubuntu.com/ubuntu/ noble-security main universe
EOF

apt=(sudo apt-get -o "Dir::Etc::sourcelist=$sources" -o Dir::Etc::sourceparts=- -o Acquire::Retries=3)
"${apt[@]}" -o APT::Update::Error-Mode=any update
"${apt[@]}" install -y "$@"
