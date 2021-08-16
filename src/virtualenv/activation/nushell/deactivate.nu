# Setting the old path
let-env $path-name = $nu.env.VENV_OLD_PATH

# Unleting the environment variables that where created when activating the env
unlet-env VIRTUAL_ENV
unlet-env VENV_OLD_PATH
unlet-env PROMPT_STRING
