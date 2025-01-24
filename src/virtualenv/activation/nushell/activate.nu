# Virtualenv activation module for Windows and Linux/macOS
# Activate with `overlay use activate.nu`
# Deactivate with `deactivate`, as usual
#
# To customize the overlay name, you can call `overlay use activate.nu as foo`,
# but then simply `deactivate` won't work because it is just an alias to hide
# the "activate" overlay. You'd need to call `overlay hide foo` manually.

# Virtualenv activation module for Windows and Linux/macOS
# Activate with `overlay use activate.nu`
# Deactivate with `deactivate`, as usual

export-env {
    def is-string [x] {
        ($x | describe) == 'string'
    }

    def has-env [name: string] {
        $name in $env
    }

    # Emulates a `test -z`, but better as it handles values like 'false'
    def is-env-true [name: string] {
      if (has-env $name) {
        let parsed = do -i { $env | get $name | into bool }
        if ($parsed | describe) == 'bool' {
          $parsed
        } else {
          not ($env | get $name | is-empty)
        }
      } else {
        false
      }
    }

    # Detect OS (Windows or Linux/macOS)
    let os_name = ($nu.os-info.name | str downcase)
    let is_windows = $os_name == 'windows'
    let is_macos = $os_name == 'macos'
    let is_linux = $os_name == 'linux'

    # Set environment path correctly based on OS
    let virtual_env = ($env.PWD | path join ".env")  # Adjust the virtual environment directory

    let bin = if $is_windows { "Scripts" } else { "bin" }  # Use 'Scripts' for Windows and 'bin' for Unix systems

    let path_sep = if $is_windows { ";" } else { ":" }  # Use ';' for Windows, ':' for Unix systems

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
            $in | split row $path_sep | path expand
        } else {
            $in
        }
    )

    let venv_path = ([$virtual_env, $bin] | path join)
    let new_path = ($old_path | prepend $venv_path | str join $path_sep)

    let new_env = {
        $path_name  : $new_path
        VIRTUAL_ENV : $virtual_env
    }
    let new_env = if (is-env-true 'VIRTUAL_ENV_DISABLE_PROMPT') {
        $new_env
      } else {
        # Creating the new prompt for the session
        let virtual_prefix = $"(char lparen)($virtual_env | path basename)(char rparen) "
      
        # Back up the old prompt builder
        let old_prompt_command = if (has-env 'PROMPT_COMMAND') {
            $env.PROMPT_COMMAND
        } else {
            ""
        }
      
        let new_prompt = if (has-env 'PROMPT_COMMAND') {
            if 'closure' in ($old_prompt_command | describe) {
                {|| $'($virtual_prefix)(do $old_prompt_command)' }
            } else {
                {|| $'($virtual_prefix)($old_prompt_command)' }
            }
        } else {
            {|| $'($virtual_prefix)' }
        }
      
        # Ensure the correct variable name for the test
        $new_env | merge {
          _OLD_VIRTUAL_PATH   : ($old_path | str join $path_sep)
          _OLD_PROMPT_COMMAND : $old_prompt_command
          PROMPT_COMMAND      : $new_prompt
          VIRTUAL_PREFIX      : $virtual_prefix  # Change here to match the test expectation
        }
      }
      

    # Load environment variables to activate the virtualenv
    load-env $new_env
}

export alias pydoc = python -m pydoc
export alias deactivate = overlay hide activate
