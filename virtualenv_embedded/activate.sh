# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

deactivate () {
    unset pydoc

    # reset old environment variables
    if [ -n "$_OLD_VIRTUAL_PATH" ] ; then
        PATH="$_OLD_VIRTUAL_PATH"
        export PATH
        unset _OLD_VIRTUAL_PATH
    fi
    if [ -n "$_OLD_VIRTUAL_PYTHONHOME" ] ; then
        PYTHONHOME="$_OLD_VIRTUAL_PYTHONHOME"
        export PYTHONHOME
        unset _OLD_VIRTUAL_PYTHONHOME
    fi

    # This should detect bash and zsh, which have a hash command that must
    # be called to get it to forget past commands.  Without forgetting
    # past commands the $PATH changes we made may not be respected
    if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
        hash -r 2>/dev/null
    fi

    if [ -n "$_OLD_VIRTUAL_PS1" ] ; then
        PS1="$_OLD_VIRTUAL_PS1"
        export PS1
        unset _OLD_VIRTUAL_PS1
    fi

    unset VIRTUAL_ENV
    if [ ! "$1" = "nondestructive" ] ; then
    # Self destruct!
        unset -f deactivate
    fi
}

set_custom_ps1() {
    PS1="${VIRTUAL_ENV_PS1//VIRTUAL_ENV_NAME/$VIRTUAL_ENV_NAME}"
}

# unset irrelevant variables
deactivate nondestructive

VIRTUAL_ENV="__VIRTUAL_ENV__"
export VIRTUAL_ENV

_OLD_VIRTUAL_PATH="$PATH"
PATH="$VIRTUAL_ENV/__BIN_NAME__:$PATH"
export PATH

# unset PYTHONHOME if set
# this will fail if PYTHONHOME is set to the empty string (which is bad anyway)
# could use `if (set -u; : $PYTHONHOME) ;` in bash
if [ -n "$PYTHONHOME" ] ; then
    _OLD_VIRTUAL_PYTHONHOME="$PYTHONHOME"
    unset PYTHONHOME
fi

if [ -z "$VIRTUAL_ENV_DISABLE_PROMPT" ] ; then
    _OLD_VIRTUAL_PS1="$PS1"

    if [ "x__VIRTUAL_PROMPT__" != x ] ; then
        PS1="__VIRTUAL_PROMPT__$PS1"

    elif [ "$(basename "$VIRTUAL_ENV")" = "__" ] ; then
        # special case for Aspen magic directories
        # see http://www.zetadev.com/software/aspen/
        VIRTUAL_ENV_NAME="$(basename "$(dirname "$VIRTUAL_ENV")")"

        if [ -n "$VIRTUAL_ENV_PS1" ]; then
            set_custom_ps1
        else
            PS1="[$VIRTUAL_ENV_NAME] $PS1"
        fi

    else
        VIRTUAL_ENV_NAME="$(basename "$VIRTUAL_ENV")"

        if [ -n "$VIRTUAL_ENV_PS1" ]; then
            set_custom_ps1
        else
            PS1="($VIRTUAL_ENV_NAME)$PS1"
        fi
    fi
    export PS1
fi

alias pydoc="python -m pydoc"

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
    hash -r 2>/dev/null
fi
