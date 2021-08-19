# Setting the old path
let path-name = (if ((sys).host.name == "Windows") { "Path" } { "PATH" })
let-env $path-name = $nu.env.VENV_OLD_PATH

# Unleting the environment variables that were created when activating the env
unlet-env VIRTUAL_ENV
unlet-env VENV_OLD_PATH
unlet-env PROMPT_STRING

unalias pydoc
unalias deactivate
