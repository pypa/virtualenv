def-env deactivate-virtualenv [] {
    def has-env [name: string] {
        $name in (env).name
    }

    let is-windows = ((sys).host.name | str downcase) == "windows"

    let path-name = if $is-windows {
        if (has-env "Path") {
            "Path"
        } else {
            "PATH"
        }
    } else {
        "PATH"
    }

    load-env { $path-name : $env._OLD_VIRTUAL_PATH }

    # Hiding the environment variables that were created when activating the env
    hide _OLD_VIRTUAL_PATH
    hide _OLD_PROMPT_COMMAND
    hide VIRTUAL_ENV
    hide PROMPT_COMMAND
    hide VIRTUAL_PROMPT
}

deactivate-virtualenv

hide pydoc
hide deactivate
