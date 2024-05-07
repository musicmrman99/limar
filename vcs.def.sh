vcs() {
    if [[ "$1" == 'init' ]]; then
        "$VCS_PIP" install -r "$VCS_REPO/requirements.txt"
    else
        local script_file="$(mktemp "/tmp/vcs-source-$(basename "$SHELL").XXXXXXXX")"
        "$VCS_PYTHON" "$VCS_REPO/main.py" --shell-script "$script_file" "$@"
        source "$script_file"
        rm "$script_file"
    fi
}

vcs_profile() {
    local script_file="$(mktemp "/tmp/vcs-source-$(basename "$SHELL").XXXXXXXX")"
    "$VCS_PYTHON" -m cProfile -o "$VCS_REPO/vcs.prof" "$VCS_REPO/main.py" --shell-script "$script_file" "$@"
    source "$script_file"
    rm "$script_file"
}
