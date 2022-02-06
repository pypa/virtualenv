# This command prepares the required environment variables
def-env activate-virtualenv [] {
    def is-string [x] {
        ($x | describe) == "string"
    }

    def has-env [name: string] {
        $name in (env).name
    }

    let is-windows = ((sys).host.name | str downcase) == "windows"
    let virtual-env = "__VIRTUAL_ENV__"
    let bin = "__BIN_NAME__"
    let path-sep = "__PATH_SEP__"
    let path-name = if $is-windows {
        "Path"
    } else {
        "PATH"
    }

    let old-path = (
        if $is-windows {
            if (has-env "Path") {
                $env.Path
            } else {
                $env.PATH
            }
        } else {
            $env.PATH
        } | if (is-string $in) {
            # if Path/PATH is a string, make it a list
            $in | split row $path-sep | path expand
        } else {
            $in
        }
    )

    let venv-path = ([$virtual-env $bin] | path join)
    let new-path = ($old-path | prepend $venv-path | str collect $path-sep)

    # Creating the new prompt for the session
    let virtual-prompt = (
        if ("__VIRTUAL_PROMPT__" == "") {
            $"(char lparen)($virtual-env | path basename)(char rparen) "
        } else {
            "(__VIRTUAL_PROMPT__) "
        }
    )

    # Back up the old prompt builder
    let old-prompt-command = if (has-env "VIRTUAL_ENV") {
        $env._OLD_PROMPT_COMMAND
    } else {
        if (has-env "PROMPT_COMMAND") {
            $env.PROMPT_COMMAND
        } else {
            ""
        }
    }

    # If there is no default prompt, then only the env is printed in the prompt
    let new-prompt = if (has-env "PROMPT_COMMAND") {
        if ($env._OLD_PROMPT_COMMAND | describe) == "block" {
            { $"($virtual-prompt)(do $env._OLD_PROMPT_COMMAND)" }
        } else {
            { $"($virtual-prompt)($env._OLD_PROMPT_COMMAND)" }
        }
    } else {
        { $"($virtual-prompt)" }
    }

    # Environment variables that will be batched loaded to the virtual env
    let new-env = {
        $path-name          : $new-path
        _OLD_VIRTUAL_PATH   : ($old-path | str collect $path-sep)
        VIRTUAL_ENV         : $virtual-env
        _OLD_PROMPT_COMMAND : $old-prompt-command
        PROMPT_COMMAND      : $new-prompt
        VIRTUAL_PROMPT      : $virtual-prompt
    }

    # Activate the environment variables
    load-env $new-env
}

# def pydoc [] {
#     python -m pydoc
# }

alias pydoc = python -m pydoc

def-env deactivate [] {
    source "__DEACTIVATE_PATH__"
}

# Activate the virtualenv
activate-virtualenv
