# This file must be used with "source bin/activate" *from bash*
# you cannot run it directly

deactivate () {
    if [ -n "$_OLD_VIRTUAL_PATH" ] ; then
        PATH="$_OLD_VIRTUAL_PATH"
        export PATH
        unset _OLD_VIRTUAL_PATH
    fi
    if [ -n "$_OLD_VIRTUAL_PS1" ] ; then
        PS1="$_OLD_VIRTUAL_PS1"
        export PS1
        unset _OLD_VIRTUAL_PS1
    fi

    unset VIRTUAL_ENV
    if [ ! "$1" = "nondestructive" ] ; then
    # Self destruct!
        unset deactivate
    fi
}

# unset irrelavent variables
deactivate nondestructive

export VIRTUAL_ENV="__VIRTUAL_ENV__"

_OLD_VIRTUAL_PATH="$PATH"
PATH="$VIRTUAL_ENV/bin:$PATH"
export PATH

_OLD_VIRTUAL_PS1="$PS1"
if [ `basename $VIRTUAL_ENV` == __ ] ; then
    # special case for Aspen magic directories
    # see http://www.zetadev.com/software/aspen/
    PS1="[`basename \`dirname $VIRTUAL_ENV\``] $PS1"
else
    PS1="(`basename $VIRTUAL_ENV`)$PS1"
fi
export PS1

# This should detect bash, which has a hash command that must
# be called to get it to forget past commands.  Without
# forgetting past commands the $PATH changes we made may not
# be respected
if [ -n "$BASH" ] ; then
    hash -r
fi
