LIMAR__STARTUP_FAILED='false'

# Define defaults and set PATH
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' ]; then
    if [ -z "$LIMAR__PYTHON" ]; then
        export LIMAR__PYTHON='python3'
    fi
    if [ -z "$LIMAR__PIP" ]; then
        export LIMAR__PIP='pip3'
    fi
    if [ -z "$LIMAR__DATA_DIR" ]; then
        export LIMAR__DATA_DIR="$HOME/.limar"
    fi
    if [ -z "$LIMAR__PERFORMANCE_PROFILING_ENABLED" ]; then
        export LIMAR__PERFORMANCE_PROFILING_ENABLED='false'
    fi

    # Note: It doesn't matter if this directory exists yet
    case "$PATH" in
        *"$LIMAR__DATA_DIR/bin"*) ;;
        *) export PATH="$PATH:$LIMAR__DATA_DIR/bin" ;;
    esac
fi

# Determine shell environment
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' ]; then
    # Yes, I know whatshell.sh detects many more shells than this script supports
    if command -v whatshell.sh >/dev/null 2>&1; then
        export LIMAR__SHELL="$(whatshell.sh | cut -d' ' -f1)"
    else
        echo 'ERROR: whatshell.sh not installed.'
        echo
        echo 'LIMAR depends on whatshell.sh (which is bundled with LIMAR in the' \
            ' "scripts" directory) being available on your PATH. This is a script' \
            ' that determines which shell you are running. It is from here:'
        echo '  https://www.in-ulm.de/~mascheck/various/whatshell/whatshell.sh.html'
        echo
        echo 'LIMAR has a way of installing the script into its own config directory' \
            'that works on most systems:'
        echo '  LIMAR__REPO="/wherever/you/put/limar"'
        echo '  export PATH="$LIMAR__REPO/scripts:$PATH"'
        echo '  . "$LIMAR__REPO/limar.def.sh"'
        echo '  limar init'
        echo
        echo 'Then close and reopen your terminal.'
        LIMAR__STARTUP_FAILED='true'
    fi
fi

# Determine repo location
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' -a -z "$LIMAR__REPO" ]; then
    limar__get_script_dir_bash() {
        # The following is a modified version of this: http://stackoverflow.com/a/246128
        # resolve $source until the file is no longer a symlink
        local dir source="${BASH_SOURCE[0]}"
        while [ -h "$source" ]; do
            dir="$(cd -P -- "$(dirname "$source")" && pwd)"
            source="$(readlink "$source")"

            # If $source was a relative symlink, we need to resolve it relative
            # to the path where the symlink file was located.
            [[ $source != /* ]] && source="$dir/$source"
        done
        cd -P -- "$(dirname "$source")"
        pwd
    }

    # See: https://stackoverflow.com/a/29835459/16967315 (and others)
    case "$LIMAR__SHELL" in
        'bash') export LIMAR__REPO="$(limar__get_script_dir_bash)" ;;
        'zsh')  export LIMAR__REPO="${0:A:h}" ;;
    esac

    if [ -z "$LIMAR__REPO" ]; then
        echo 'ERROR: LIMAR__REPO is not already defined, and could not' \
            'determine how to automatically determine its value (unknown shell).'
        echo 'Before LIMAR will run, you must define the LIMAR__REPO' \
            'environment variable as the absolute canonical path of the' \
            'LIMAR repository.'
        echo 'This should be done in your shell startup script (.bashrc,' \
            '.zshrc, .profile, etc).'
        LIMAR__STARTUP_FAILED='true'
    fi
fi

# Define runner
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' ]; then
    limar__link_file() {
        echo "'$1' -> '$2'"
        ln -sf "$2" "$1"
    }

    limar() {
        if [ "$1" = '/env' ]; then
            echo "LIMAR__SHELL='$LIMAR__SHELL'"
            echo "LIMAR__PYTHON='$LIMAR__PYTHON'"
            echo "LIMAR__PIP='$LIMAR__PIP'"
            echo "LIMAR__DATA_DIR='$LIMAR__DATA_DIR'"
            echo "LIMAR__REPO='$LIMAR__REPO'"
            echo "LIMAR__PERFORMANCE_PROFILING_ENABLED='$LIMAR__PERFORMANCE_PROFILING_ENABLED'"

        elif [ "$1" = '/init' ]; then
            if ! command -v "$LIMAR__PYTHON" >/dev/null 2>&1; then
                echo "ERROR: Configured python version (\$LIMAR__PYTHON) '$LIMAR__PYTHON' not found."
                return 1
            fi
            if ! command -v "$LIMAR__PIP" >/dev/null 2>&1; then
                echo "ERROR: Configured pip version (\$LIMAR__PIP) '$LIMAR__PIP' not found."
                return 1
            fi

            if [ ! -d "$LIMAR__DATA_DIR" ]; then
                echo "Creating LIMAR data directory at '$LIMAR__DATA_DIR'"
                mkdir \
                    "$LIMAR__DATA_DIR" \
                    "$LIMAR__DATA_DIR/bin" \
                    "$LIMAR__DATA_DIR/tmp"

                chmod 755 \
                    "$LIMAR__DATA_DIR" \
                    "$LIMAR__DATA_DIR/bin" \
                    "$LIMAR__DATA_DIR/tmp"

                limar /link "$LIMAR__REPO"
            else
                echo 'Data directory already exists, skipping creation and linking'
            fi

            echo "Installing LIMAR python dependencies from '$LIMAR__REPO/requirements.txt'"
            "$LIMAR__PIP" install -r "$LIMAR__REPO/requirements.txt"

        elif [ "$1" = '/link' ]; then
            local limar_repo="$2"
            if ! find "$limar_repo" -mindepth 1 -maxdepth 1 -name 'limar.def.sh' >/dev/null 2>&1; then
                echo "ERROR: '$2' is not a LIMAR repository"
                return 1
            fi
            echo "Linking to LIMAR repository at '$limar_repo'"

            local script
            for script in "$limar_repo"/scripts/*; do
                limar__link_file "$LIMAR__DATA_DIR/bin/$(basename "$script")" "$script"
            done
            limar__link_file "$LIMAR__DATA_DIR/bin/limar.def.sh" "$limar_repo/limar.def.sh"

            echo "Linking complete."
            echo
            echo 'If `limar init` (when you originally installed LIMAR) said' \
                'that you needed to set LIMAR__REPO manually, then remember' \
                'to update your shell startup script (.bashrc, .zshrc, etc.)' \
                'with the new repository path.'
            echo

        else
            local script_file="$(mktemp "$LIMAR__DATA_DIR/tmp/limar-source-$(basename "$SHELL").XXXXXXXX")"
            if [ "$LIMAR__PERFORMANCE_PROFILING_ENABLED" = 'true' ]; then
                "$LIMAR__PYTHON" -m cProfile -o "$LIMAR__REPO/limar.prof" "$LIMAR__REPO/main.py" --shell-script "$script_file" "$@"
            else
                "$LIMAR__PYTHON" "$LIMAR__REPO/main.py" --shell-script "$script_file" "$@"
            fi
            source "$script_file"
            rm "$script_file"
        fi
    }
    alias lm='limar'
fi
