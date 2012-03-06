# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

ACTIVATE_PATH_FALLBACK="$_"

deactivate () {
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
        hash -r
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

# unset irrelavent variables
deactivate nondestructive

# attempt to determine VIRTUAL_ENV in relocatable way
if [ ! -z "${BASH_SOURCE:-}" ]; then
    # bash
    ACTIVATE_PATH="${BASH_SOURCE}"
elif [ ! -z "${DASH_SOURCE:-}" ]; then
    # dash
    ACTIVATE_PATH="${DASH_SOURCE}"
elif [ ! -z "${ZSH_VERSION:-}" ]; then
    # zsh
    ACTIVATE_PATH="$0"
elif [ ! -z "${KSH_VERSION:-}" ] || [ ! -z "${.sh.version:}" ]; then
    # ksh - we have to use history, and unescape spaces before quoting
    ACTIVATE_PATH="$(history -r -l -n | head -1 | sed -e 's/^[\t ]*\(\.\|source\) *//;s/\\ / /g')"
elif [ "$(basename "$ACTIVATE_PATH_FALLBACK")" == "activate.sh" ]; then
    ACTIVATE_PATH="${ACTIVATE_PATH_FALLBACK}"
else
    ACTIVATE_PATH=""
fi

# default to non-relocatable path
VIRTUAL_ENV="__VIRTUAL_ENV__"
if [ ! -z "${ACTIVATE_PATH:-}" ]; then
    VIRTUAL_ENV="$(cd "$(dirname "${ACTIVATE_PATH}")/.."; pwd)"
fi
unset ACTIVATE_PATH
unset ACTIVATE_PATH_FALLBACK
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
    else
    if [ "`basename \"$VIRTUAL_ENV\"`" = "__" ] ; then
        # special case for Aspen magic directories
        # see http://www.zetadev.com/software/aspen/
        PS1="[`basename \`dirname \"$VIRTUAL_ENV\"\``] $PS1"
    else
        PS1="(`basename \"$VIRTUAL_ENV\"`)$PS1"
    fi
    fi
    export PS1
fi

# This should detect bash and zsh, which have a hash command that must
# be called to get it to forget past commands.  Without forgetting
# past commands the $PATH changes we made may not be respected
if [ -n "$BASH" -o -n "$ZSH_VERSION" ] ; then
    hash -r
fi
