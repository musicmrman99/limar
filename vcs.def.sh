vcs() {
    if [[ "$1" == 'init' ]]; then
        "$VCS_PIP" install -r "$VCS_REPO/requirements.txt"
    else
        "$VCS_PYTHON" "$VCS_REPO/src/main.py" "$@"
    fi
}
