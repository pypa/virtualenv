restore_on_deactivate() {
    # ok: ps1-before-prompt-escaping
    PS1="$_OLD_VIRTUAL_PS1"
}

assign_after_escaping() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ok: ps1-before-prompt-escaping, ps1-reads-virtual-env-prompt
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

read_prompt_after_escaping() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ruleid: ps1-reads-virtual-env-prompt
    PS1="($VIRTUAL_ENV_PROMPT) ${PS1-}"
    # ruleid: ps1-reads-virtual-env-prompt
    PS1="(${VIRTUAL_ENV_PROMPT//\\/\\\\}) ${PS1-}"
    # ruleid: ps1-reads-virtual-env-prompt
    PS1='(${VIRTUAL_ENV_PROMPT-}) '"${PS1-}"
    # ruleid: ps1-reads-virtual-env-prompt
    export PS1="($VIRTUAL_ENV_PROMPT) ${PS1-}"
    # ruleid: ps1-reads-virtual-env-prompt
    PS1+="$VIRTUAL_ENV_PROMPT"
    # ruleid: ps1-reads-virtual-env-prompt
    PROMPT="($VIRTUAL_ENV_PROMPT) ${PROMPT-}"
}

overwrite_escaped_prompt() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
        # ruleid: ps1-reads-virtual-env-prompt
        _VIRTUAL_PROMPT=$VIRTUAL_ENV_PROMPT
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

assign_before_escaping() {
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
}

drop_escaping_loop() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_PROMPT=x
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

drop_backslash_arm() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

escape_backslash_once() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

drop_backtick_pattern() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

zsh_without_psvar() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_CHAR=${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
            case $_VIRTUAL_CHAR in
                \\) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\\\\\\\" ;;
                \$ | \`) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT\\$_VIRTUAL_CHAR" ;;
                *) _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT$_VIRTUAL_CHAR" ;;
            esac
        done
        unset _VIRTUAL_REST _VIRTUAL_CHAR
    else
        _OLD_VIRTUAL_PSVAR="${psvar[9]-}"
        _VIRTUAL_PROMPT=x
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}
