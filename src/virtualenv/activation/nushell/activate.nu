# Setting all environment variables for the venv
let virtual_env = "__VIRTUAL_ENV__"

let is_windows = (sys).host.name == "Windows"
let path-sep = (if $is_windows { ";" } { ":" })

let venv-abs-dir = ($virtual_env | path expand)
let venv-name = ($venv-abs-dir | path basename)
let old-path = ($nu.path | str collect ($path-sep))

let new-path = (if ($is_windows) {
    let venv-path = ([$virtual_env "__BIN_NAME__"] | path join)
    let new-path = ($nu.path | prepend $venv-path | str collect ($path-sep))

    [[name, value]; [Path $new-path]]
} {
    let venv-path = ([$virtual_env "bin"] | path join)
    let new-path = ($nu.path | prepend $venv-path | str collect ($path-sep))

    [[name, value]; [PATH $new-path]]
}
)

let new-env = [[name, value]; [VENV_OLD_PATH $old-path] [VIRTUAL_ENV $venv-name]]

load-env ($new-env | append $new-path)

# Creating the new prompt for the session
let virtual_prompt = (if ("__VIRTUAL_PROMPT__" != "") {
    "__VIRTUAL_PROMPT__"
} {
    $virtual_env | path basename
}
)

let new_prompt = ($"build-string '(char lparen)' '($virtual_prompt)' '(char rparen) ' (config get prompt | str find-replace "build-string" "")")
let-env PROMPT_STRING = $new_prompt
