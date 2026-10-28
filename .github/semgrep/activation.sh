restore_on_deactivate() {
    # ok: ps1-before-prompt-escaping
    PS1="$_OLD_VIRTUAL_PS1"
}

assign_after_escaping() {
    if [ -n "${BASH_VERSION-}" ]; then
        _VIRTUAL_REST=$VIRTUAL_ENV_PROMPT
        _VIRTUAL_PROMPT=
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_PROMPT="$_VIRTUAL_PROMPT${_VIRTUAL_REST%"${_VIRTUAL_REST#?}"}"
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
        done
    else
        psvar[9]="$VIRTUAL_ENV_PROMPT"
        _VIRTUAL_PROMPT='%9v'
    fi
    # ok: ps1-before-prompt-escaping, ps1-reads-virtual-env-prompt
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}

read_raw_prompt() {
    # ruleid: ps1-reads-virtual-env-prompt
    _VIRTUAL_PROMPT=$VIRTUAL_ENV_PROMPT
    # ruleid: ps1-before-prompt-escaping, ps1-reads-virtual-env-prompt
    PS1='(${VIRTUAL_ENV_PROMPT-}) '"${PS1-}"
    # ruleid: ps1-before-prompt-escaping, ps1-reads-virtual-env-prompt
    PROMPT="($VIRTUAL_ENV_PROMPT) ${PROMPT-}"
}

assign_before_escaping() {
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
    if [ -n "${BASH_VERSION-}" ]; then
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
        done
    else
        psvar[9]="$VIRTUAL_ENV_PROMPT"
    fi
}

assign_without_zsh_escaping() {
    if [ -n "${BASH_VERSION-}" ]; then
        while [ -n "$_VIRTUAL_REST" ]; do
            _VIRTUAL_REST=${_VIRTUAL_REST#?}
        done
    else
        _VIRTUAL_PROMPT=$_VIRTUAL_REST
    fi
    # ruleid: ps1-before-prompt-escaping
    PS1="(${_VIRTUAL_PROMPT}) ${PS1-}"
}
