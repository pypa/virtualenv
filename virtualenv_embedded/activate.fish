# This file should be used using `. bin/activate.fish` *within a running fish ( http://fishshell.com ) session*.
# Do not run it directly.

function deactivate -d 'Exit virtualenv mode and return to the normal environment.'
    if test -n $_VIRTUALENV_OLD_PATH
        set -gx PATH $_VIRTUALENV_OLD_PATH
        set -e _VIRTUALENV_OLD_PATH
    end

    if test -n $_VIRTUALENV_OLD_PYTHONHOME
        set -gx PYTHONHOME $_VIRTUALENV_OLD_PYTHONHOME
        set -e _VIRTUALENV_OLD_PYTHONHOME
    end

    if test -n $_VIRTUALENV_OLD_FISH_PROMPT_OVERRIDE
        # Set an empty local `$fish_function_path` to allow the removal of `fish_prompt` using `functions -e`.
        set -l fish_function_path

        # Erase virtualenv's `fish_prompt` and restore the original.
        functions -e fish_prompt
        functions -c _old_fish_prompt fish_prompt
        functions -e _old_fish_prompt
        set -e _VIRTUALENV_OLD_FISH_PROMPT_OVERRIDE
    end

    set -e VIRTUAL_ENV

    if test $argv[1] != 'nondestructive'
        # Self-destruct!
        functions -e deactivate
    end
end

# Unset irrelevant variables.
deactivate nondestructive

set -gx VIRTUAL_ENV "__VIRTUAL_ENV__"

set -gx _VIRTUALENV_OLD_PATH $PATH
set -gx PATH $VIRTUAL_ENV/"__BIN_NAME__" $PATH

# Unset `$PYTHONHOME` if set.
if set -q PYTHONHOME
    set -gx _VIRTUALENV_OLD_PYTHONHOME $PYTHONHOME
    set -e PYTHONHOME
end

if test \( -z $VIRTUAL_ENV_DISABLE_PROMPT \)
    # Copy the current `fish_prompt` function as `_old_fish_prompt`.
    functions -c fish_prompt _old_fish_prompt

    function fish_prompt
        # Save the current $status, for fish_prompts that display it.
        set -l old_status $status

        # Prompt override provided?
        # If not, just prepend the environment name.
        if test -n "__VIRTUAL_PROMPT__"
            printf '%s%s' "__VIRTUAL_PROMPT__" (set_color normal)
        else
            printf '%svirtualenv:%s %s%s%s\n' (set_color white) (set_color normal) (set_color -b black white) (basename $VIRTUAL_ENV) (set_color normal)
        end
        
        # Restore the original $status
        source "exit $old_status" | source
        _old_fish_prompt
    end

    set -gx _VIRTUALENV_OLD_FISH_PROMPT_OVERRIDE $VIRTUAL_ENV
end
