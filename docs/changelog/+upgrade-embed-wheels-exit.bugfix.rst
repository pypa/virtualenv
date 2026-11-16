Stop logging ``SystemExit: None`` as an error after a successful ``virtualenv --upgrade-embed-wheels``. The command
already exited with status 0; its output now ends with the upgrade summary instead of a line that looks like a crash.
