vcs() {
    if [[ "$1" == 'init' ]]; then
        "$VCS_PIP" install -r "$VCS_REPO/requirements.txt"
    else
        local source_file="$(mktemp "/tmp/vcs-source-$(basename "$SHELL").XXXXXXXX")"
        "$VCS_PYTHON" "$VCS_REPO/main.py" --mm-source-file "$source_file" "$@"
        source "$source_file"
        rm "$source_file"
    fi
}

vcs_profile() {
    local source_file="$(mktemp "/tmp/vcs-source-$(basename "$SHELL").XXXXXXXX")"
    "$VCS_PYTHON" -m cProfile -o "$VCS_REPO/vcs.prof" "$VCS_REPO/main.py" --mm-source-file "$source_file" "$@"
    source "$source_file"
    rm "$source_file"
}
