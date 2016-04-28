# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

deactivate () {
    unset -f pydoc >/dev/null 2>&1

    # Restore old environment variables.
    if ! [ -z "${VIRTUAL_ENV+_}" ] ; then
        remove_from_path() {
            local path_to_remove="$1"
            local path_before
            local result=":$PATH:"
            while [ "$path_before" != "$result" ]; do
                path_before="$result"
                result="${result//:$path_to_remove:/:}"
            done
            # Trim trailing/leading colons.
            result="${result%:}"
            echo "${result#:}"
        }
        PATH="$(remove_from_path "$VIRTUAL_ENV/__BIN_NAME__")"
    fi
    if ! [ -z "${_OLD_VIRTUAL_PYTHONHOME+_}" ] ; then
        PYTHONHOME="$_OLD_VIRTUAL_PYTHONHOME"
        export PYTHONHOME
        unset _OLD_VIRTUAL_PYTHONHOME
    fi

    # This should detect bash and zsh, which have a hash command that must
    # be called to get it to forget past commands.  Without forgetting
    # past commands the $PATH changes we made may not be respected
    if [ -n "${BASH-}" ] || [ -n "${ZSH_VERSION-}" ] ; then
        hash -r 2>/dev/null
    fi

    if ! [ -z "${_OLD_VIRTUAL_PS1+_}" ] ; then
        PS1="$_OLD_VIRTUAL_PS1"
        export PS1
        unset _OLD_VIRTUAL_PS1
    fi

    unset VIRTUAL_ENV
    if [ ! "${1-}" = "nondestructive" ] ; then
    # Self destruct!
        unset -f deactivate
    fi
}

# unset irrelevant variables
deactivate nondestructive

VIRTUAL_ENV="__VIRTUAL_ENV__"
export VIRTUAL_ENV

PATH="$VIRTUAL_ENV/__BIN_NAME__:$PATH"
export PATH

# unset PYTHONHOME if set
if ! [ -z "${PYTHONHOME+_}" ] ; then
    _OLD_VIRTUAL_PYTHONHOME="$PYTHONHOME"
    unset PYTHONHOME
fi

if [ -z "${VIRTUAL_ENV_DISABLE_PROMPT-}" ] ; then
    _OLD_VIRTUAL_PS1="$PS1"
    if [ "x__VIRTUAL_PROMPT__" != x ] ; then
        PS1="__VIRTUAL_PROMPT__$PS1"
    else
        PS1="(`basename \"$VIRTUAL_ENV\"`) $PS1"
    fi
    export PS1
fi

# Make sure to unalias pydoc if it's already there
alias pydoc 2>/dev/null >/dev/null && unalias pydoc

pydoc () {
    python -m pydoc "$@"
}

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "${BASH-}" ] || [ -n "${ZSH_VERSION-}" ] ; then
    hash -r 2>/dev/null
fi
