#!/usr/bin/env bash
#
# This script tries to install all possible tools needed for full testing
# under current running platform.
#
# Platforms: ubuntu, macos
# Tools: bash, fish, csh (tcsh), powershell
set -o pipefail
set -o errexit
set -o nounset
#set -o xtrace

# Return if we are not in a Pull Request
if [[ "$TRAVIS_OS_NAME" = "linux" ]]; then

  # Covering Ubuntu only for the moment
  source /etc/os-release
  sudo apt-add-repository -y ppa:fish-shell/release-2
  # https://github.com/PowerShell/PowerShell/blob/master/docs/installation/linux.md
  curl --silent https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
  curl --silent https://packages.microsoft.com/config/ubuntu/${VERSION_ID}/prod.list | sudo tee /etc/apt/sources.list.d/microsoft.list
  sudo apt-get -qq update
  sudo apt-get install -qqy fish tcsh powershell
else
  # brew update
  brew install fish tree tcsh Caskroom/cask/powershell
fi

bash --version | head -n 1
fish --version
csh --verison
powershell --version
