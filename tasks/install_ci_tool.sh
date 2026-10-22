#!/usr/bin/env bash
# Download the release asset tasks/ci-tools.json pins for this runner's OS, check its sha256 and put the tool on PATH.
set -euo pipefail

tool=$1
case "$tool" in
    fish) repository=fish-shell/fish-shell ;;
    nushell) repository=nushell/nushell ;;
    rustpython) repository=RustPython/RustPython ;;
    *)
        echo "unknown tool: $tool" >&2
        exit 1
        ;;
esac
# tr drops the CR that jq.exe emits on Windows
read -r tag asset sha256 < <(jq --raw-output --arg tool "$tool" --arg os "$RUNNER_OS" \
    '.[$tool] | [.tag, .assets[$os].name, .assets[$os].sha256] | @tsv' tasks/ci-tools.json | tr -d '\r')
gh release download "$tag" --repo "$repository" --pattern "$asset" --dir "$RUNNER_TEMP"
(cd "$RUNNER_TEMP" && echo "$sha256  $asset" | sha256sum -c -)

bin=/usr/local/bin
if [ "$RUNNER_OS" = "Windows" ]; then
    bin=/c/ProgramData/chocolatey/bin
fi
case "$asset" in
    *.pkg) sudo installer -pkg "$RUNNER_TEMP/$asset" -target / ;;
    *.zip)
        7z x "$RUNNER_TEMP/$asset" -o"$RUNNER_TEMP/$tool" -y
        cp "$RUNNER_TEMP/$tool/nu.exe" "$bin/nu.exe"
        ;;
    *.tar.gz | *.tar.xz)
        mkdir -p "$RUNNER_TEMP/$tool"
        tar -xf "$RUNNER_TEMP/$asset" -C "$RUNNER_TEMP/$tool"
        sudo install -m 0755 "$(find "$RUNNER_TEMP/$tool" -type f -name "${tool%shell}" -print -quit)" "$bin/"
        ;;
    *.exe) cp "$RUNNER_TEMP/$asset" "$bin/$tool.exe" ;;
    *) sudo install -m 0755 "$RUNNER_TEMP/$asset" "$bin/$tool" ;;
esac
