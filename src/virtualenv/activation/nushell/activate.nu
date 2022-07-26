# This command prepares the required environment variables
def-env activate-virtualenv [] {
    def is-string [x] {
        ($x | describe) == 'string'
    }

    def has-env [name: string] {
        $name in (env).name
    }

    let is_windows = ((sys).host.name | str downcase) == 'windows'
    let virtual_env = '__VIRTUAL_ENV__'
    let bin = '__BIN_NAME__'
    let path_sep = '__PATH_SEP__'
    let path_name = if $is_windows {
        if (has-env 'Path') {
            'Path'
        } else {
            'PATH'
        }
    } else {
        'PATH'
    }

    let old_path = (
        if $is_windows {
            if (has-env 'Path') {
                $env.Path
            } else {
                $env.PATH
            }
        } else {
            $env.PATH
        } | if (is-string $in) {
            # if Path/PATH is a string, make it a list
            $in | split row $path_sep | path expand
        } else {
            $in
        }
    )

    let venv_path = ([$virtual_env $bin] | path join)
    let new_path = ($old_path | prepend $venv_path | str collect $path_sep)

    # Creating the new prompt for the session
    let virtual_prompt = if ('__VIRTUAL_PROMPT__' == '') {
        $'(char lparen)($virtual_env | path basename)(char rparen) '
    } else {
        '(__VIRTUAL_PROMPT__) '
    }

    # Back up the old prompt builder
    let old_prompt_command = if (has-env 'VIRTUAL_ENV') && (has-env '_OLD_PROMPT_COMMAND') {
        $env._OLD_PROMPT_COMMAND
    } else {
        if (has-env 'PROMPT_COMMAND') {
            $env.PROMPT_COMMAND
        } else {
            ''
        }
    }

    # If there is no default prompt, then only the env is printed in the prompt
    let new_prompt = if (has-env 'PROMPT_COMMAND') {
        if ($old_prompt_command | describe) == 'block' {
            { $'($virtual_prompt)(do $old_prompt_command)' }
        } else {
            { $'($virtual_prompt)($old_prompt_command)' }
        }
    } else {
        { $'($virtual_prompt)' }
    }

    # Environment variables that will be batched loaded to the virtual env
    let new_env = {
        $path_name          : $new_path
        VIRTUAL_ENV         : $virtual_env
        _OLD_VIRTUAL_PATH   : ($old_path | str collect $path_sep)
        _OLD_PROMPT_COMMAND : $old_prompt_command
        PROMPT_COMMAND      : $new_prompt
        VIRTUAL_PROMPT      : $virtual_prompt
    }

    # Activate the environment variables
    load-env $new_env
}

# Activate the virtualenv
activate-virtualenv

alias pydoc = python -m pydoc
alias deactivate = source '__DEACTIVATE_PATH__'
