limar() {
    if [[ "$1" == 'init' ]]; then
        "$LIMAR_PIP" install -r "$LIMAR_REPO/requirements.txt"
    else
        local script_file="$(mktemp "/tmp/limar-source-$(basename "$SHELL").XXXXXXXX")"
        "$LIMAR_PYTHON" "$LIMAR_REPO/main.py" --shell-script "$script_file" "$@"
        source "$script_file"
        rm "$script_file"
    fi
}
alias lm='limar'

limar_profile() {
    local script_file="$(mktemp "/tmp/limar-source-$(basename "$SHELL").XXXXXXXX")"
    "$LIMAR_PYTHON" -m cProfile -o "$LIMAR_REPO/limar.prof" "$LIMAR_REPO/main.py" --shell-script "$script_file" "$@"
    source "$script_file"
    rm "$script_file"
}
