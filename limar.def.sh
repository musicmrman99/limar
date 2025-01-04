LIMAR__STARTUP_FAILED='false'

limar__log() {
    local indent=0
    local line_end=''
    local section_end='\n'
    while [ -n "$1" ]; do
        case "$1" in
            '-i='*) indent="${1#'-i='}"; shift ;;
            '-l='*) line_end="${1#'-l='}"; shift ;;
            '-s='*) section_end="${1#'-s='}"; shift ;;

            '-i') indent=2; shift ;;
            '-l') line_end='\n'; shift ;;
            '-s') section_end='\n\n'; shift ;;
            *) break ;;
        esac
    done

    {
        printf "%s${line_end}" "$@"
        printf "${section_end#"$line_end"}"
    } | fold -s -w "$((80 - "$indent"))" | sed "s/^/$(printf "%${indent}s")/"
}

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
        limar__log -s 'ERROR: whatshell.sh not installed.'

        limar__log 'LIMAR depends on whatshell.sh (which is bundled with' \
            ' LIMAR in the "scripts" directory) being available on your PATH.' \
            ' This is a script that determines which shell you are running.' \
            ' It is from here:'
        limar__log -i -s \
            'https://www.in-ulm.de/~mascheck/various/whatshell/whatshell.sh.html'

        limar__log 'LIMAR has a way of installing the script into its own' \
            ' config directory that works on most systems:'
        limar__log -i -l -s \
            'LIMAR__REPO="/wherever/you/put/limar"' \
            'export PATH="$LIMAR__REPO/scripts:$PATH"' \
            '. "$LIMAR__REPO/limar.def.sh"' \
            'limar /init'

        limar__log 'Then close and reopen your terminal.'
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
        limar__log -s 'ERROR: LIMAR__REPO is not already defined, and could' \
            ' not determine how to automatically determine its value (unknown' \
            ' shell).'
        limar__log 'Before LIMAR will run, you must define the LIMAR__REPO' \
            ' environment variable as the absolute canonical path of the' \
            ' LIMAR installation. This should be done in your shell startup' \
            ' script (.bashrc, .zshrc, .profile, etc).'
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
        if [ "$1" = '/help' ]; then
            limar__log -s 'DESCRIPTION:'

            limar__log -i -s 'The LIMAR bootstrap is the wrapper script(s)' \
                ' around LIMAR that support installing and uninstalling its' \
                ' parts, switching between active versions, and running it in' \
                ' various environments and shells.'

            limar__log -i -s 'Running the LIMAR bootstrap without using any' \
                ' of the below bootstrap commands will run LIMAR itself,' \
                ' passing all arguments along.'

            limar__log -i -s 'NOTE: This bootstrap aliases `limar` to `lm`,' \
                ' so all usages of `limar` below can be shortened to `lm`.'

            limar__log -s 'COMMANDS:'

            limar__log -i -l 'limar /help'
            limar__log -i=4 -s 'Show help text for the LIMAR bootstrap.'

            limar__log -i -l 'limar /env'
            limar__log -i=4 -s 'List the names and values of all environment' \
                ' variables used by the LIMAR boostrap (some of which are' \
                ' also used by LIMAR itself).'

            limar__log -i -l \
                'limar /init' \
                'limar /reinit'
            limar__log -i=4 -s 'Initialise LIMAR by installing dependencies,' \
                ' building dynamic components, creating user-specific' \
                ' installation files and directories, and linking the active' \
                ' LIMAR installation. `/init` will only perform each' \
                ' initialisation step if it needs (re-)performing.'

            limar__log -i -l \
                'limar /build' \
                'limar /rebuild' \
                'limar /clean'
            limar__log -i=4 -s 'Build dynamic components. `/build` will only' \
                ' build the components if they are not already built.' \
                ' `/clean` will remove the built components without' \
                ' rebuilding them.'

            limar__log -i -l 'limar /linked'
            limar__log -i=4 -s 'Print the currently linked LIMAR installation'

            limar__log -i -l \
                'limar /link <limar_installation_directory>' \
                'limar /relink <limar_installation_directory>' \
                'limar /unlink'
            limar__log -i=4 -s 'Link to the given LIMAR installation (ie. set' \
                ' the given LIMAR installation as the one to use). `/link`' \
                ' will only perform the link if there is no currently linked' \
                ' installation. `/unlink` will unlink the currently linked' \
                ' installation without linking a new one.'
            limar__log -i=4 'WARNING:'
            limar__log -i=6 'Unlinking with `/unlink` will make the LIMAR' \
                ' bootstrap no longer loadable in the normal way until a new' \
                ' installation is linked. If a new installation is not linked' \
                ' in the same shell session as unlinking, then to manually' \
                ' re-enable usage of the LIMAR bootstrap to perform the link,' \
                ' the `scripts` directory of a specific LIMAR installation' \
                ' must be added to PATH, and the `limar.def.sh` script must' \
                ' be re-sourced from that installation. This is similar to' \
                ' the process for initialisation when installing LIMAR:'
            limar__log -i=8 -l -s \
                'export LIMAR__REPO="/path/to/limar/installation"' \
                'export PATH="$LIMAR__REPO/scripts:$PATH"' \
                '. "$LIMAR__REPO/limar.def.sh"' \
                'limar /link "$LIMAR__REPO"'

            limar__log -i -l \
                'limar /reload' \
                'limar /unload'
            limar__log -i=4 -s 'Reload (or unload) the LIMAR bootstrap.' \
                ' Useful for testing changes to the boostrap.'

        elif [ "$1" = '/env' ]; then
            echo "LIMAR__SHELL='$LIMAR__SHELL'"
            echo "LIMAR__PYTHON='$LIMAR__PYTHON'"
            echo "LIMAR__PIP='$LIMAR__PIP'"
            echo "LIMAR__DATA_DIR='$LIMAR__DATA_DIR'"
            echo "LIMAR__REPO='$LIMAR__REPO'"
            echo "LIMAR__PERFORMANCE_PROFILING_ENABLED='$LIMAR__PERFORMANCE_PROFILING_ENABLED'"

        elif [ "$1" = '/init' -o "$1" = '/reinit' ]; then
            # Check python and pip versions
            if ! command -v "$LIMAR__PYTHON" >/dev/null 2>&1; then
                limar__log 'ERROR: Configured python version ($LIMAR__PYTHON)' \
                    " '$LIMAR__PYTHON' not found."
                return 1
            fi
            if ! command -v "$LIMAR__PIP" >/dev/null 2>&1; then
                limar__log 'ERROR: Configured pip version ($LIMAR__PIP)' \
                    " '$LIMAR__PIP' not found."
                return 1
            fi

            # Install python dependencies (for build and run)
            limar__log 'Installing LIMAR python dependencies from' \
                " '$LIMAR__REPO/requirements.txt'"
            "$LIMAR__PIP" install -r "$LIMAR__REPO/requirements.txt" || return $?

            # Build remaining components
            if [ "$1" = '/reinit' ]; then
                limar /rebuild || return $?
            else
                limar /build || return $?
            fi

            # Create data directory
            if [ ! -d "$LIMAR__DATA_DIR" ]; then
                limar__log "Creating LIMAR data directory at '$LIMAR__DATA_DIR'"

                mkdir "$LIMAR__DATA_DIR" && \
                chmod 755 "$LIMAR__DATA_DIR" || {
                    limar__log 'ERROR: Creating data directory failed'
                    return 1
                }
            else
                limar__log 'Data directory exists'
            fi

            # Link to the installation of LIMAR
            if [ "$1" = '/reinit' ]; then
                limar /relink "$LIMAR__REPO" || return $?
            else
                limar /link "$LIMAR__REPO" || return $?
            fi

        elif [ "$1" = '/build' -o "$1" = '/rebuild' -o "$1" = '/clean' ]; then
            local manifest_lang_path="$LIMAR__REPO/modules/manifest_lang"

            if [ "$1" = '/rebuild' -o "$1" = '/clean' ]; then
                limar__log 'Cleaning LIMAR manifest parser build'
                rm -rf "$manifest_lang_path/build"
            fi

            if [ \( "$1" = '/build' -a ! -d "$manifest_lang_path" \) -o "$1" = '/rebuild' ]; then
                limar__log 'Building LIMAR manifest parser in' \
                    " '$manifest_lang_path'"
                failed='false'
                cd "$manifest_lang_path" || {
                    echo "ERROR: Failed to build parser: Could not change directory to '$manifest_lang_path'"
                    return 1
                }
                antlr4 -Dlanguage=Python3 -o ./build ./Manifest.g4 || failed='true'
                cd - >/dev/null
                if [ "$failed" = 'true' ]; then
                    echo "ERROR: Failed to build parser"
                    return 1
                fi

            elif [ "$1" = '/build' ]; then
                limar__log \
                    'LIMAR manifest parser already built, skipping building'
                limar__log \
                    'Use `limar /rebuild` to force a rebuild, or' \
                    ' `limar /reinit` to force a full reinitialisation'
            fi

        elif [ "$1" = '/linked' ]; then
            if [ -L "$LIMAR__DATA_DIR/bin/limar.def.sh" ]; then
                dirname "$(readlink "$LIMAR__DATA_DIR/bin/limar.def.sh")"
            else
                echo "No linked installation"
            fi
        elif [ "$1" = '/link' -o "$1" = '/relink' -o "$1" = '/unlink' ]; then
            local limar_bin_path="$LIMAR__DATA_DIR/bin"

            # Create bin directory
            if [ ! -d "$limar_bin_path" ]; then
                limar__log \
                    "Creating /bin in LIMAR data directory at '$LIMAR__DATA_DIR'"
                mkdir "$limar_bin_path" && \
                chmod 755 "$limar_bin_path" || {
                    limar__log 'ERROR: Creating /bin in data directory failed'
                    return 1
                }
            fi

            # Unlink
            if [ "$1" = '/relink' -o "$1" = '/unlink' ]; then
                limar__log 'Unlinking currently linked LIMAR installation'
                rm -f "$limar_bin_path"/*
            fi

            # Link or relink
            if [ \( "$1" = '/link' -a ! -L "$limar_bin_path/limar.def.sh" \) -o "$1" = '/relink' ]; then
                # Check that the target is a valid LIMAR installation
                local limar_repo="$2"
                if [ ! -f "$limar_repo/limar.def.sh" -o -L "$limar_repo/limar.def.sh" ]; then
                    limar__log "ERROR: '$limar_repo' is not a LIMAR installation"
                    return 1
                fi
                limar__log "Linking to LIMAR installation at '$limar_repo'"

                # Link dependency and bootstrap scripts
                local script
                for script in "$limar_repo"/scripts/*; do
                    limar__link_file "$limar_bin_path/$(basename "$script")" "$script"
                done
                limar__link_file "$limar_bin_path/limar.def.sh" "$limar_repo/limar.def.sh"

                # Remind users to update their vars if needed
                limar__log -s "Linked to LIMAR installation '$limar_repo'."
                limar__log 'NOTE (possible manual step):'
                limar__log -i -s \
                    'If `limar /init` (when you originally installed LIMAR)' \
                    ' said that you needed to set LIMAR__REPO manually, then' \
                    ' remember to update your shell startup script (.bashrc,' \
                    ' .zshrc, etc.) with the new installation path.'
            elif [ "$1" = '/link' ]; then
                limar__log 'LIMAR installation already linked'
                limar__log 'Use `limar /relink <limar_inst_path>` to force a' \
                    ' relink, or `limar /reinit` to force a full' \
                    ' reinitialisation (which will use $LIMAR__REPO as the' \
                    ' installation path)'
            fi

        elif [ "$1" = '/reload' -o "$1" = '/unload' ]; then
            limar__log 'Unloading LIMAR bootstrap'
            # In reverse order of declaration
            unalias lm
            unset -f limar
            unset -f limar__link_file
            if command -v limar__get_script_dir_bash >/dev/null 2>&1; then
                unset -f limar__get_script_dir_bash
            fi
            # NOTE: Does not unset vars or env vars, or strip relevant locations
            #       from PATH, otherwise user settings in the shell's startup
            #       script (which is not reloaded) would be lost.

            if [ "$1" = '/reload' ]; then
                limar__log 'Reloading LIMAR bootstrap from linked installation'
            fi
            unset -f limar__log

            if [ "$1" = '/reload' ]; then
                # Assumes it's already linked
                . "$LIMAR__DATA_DIR/bin/limar.def.sh"
            fi

        else
            # Make tmp directory
            if [ ! -d "$LIMAR__DATA_DIR/tmp" ]; then
                limar__log \
                    "Creating /tmp in LIMAR data directory at '$LIMAR__DATA_DIR'"
                mkdir "$LIMAR__DATA_DIR/tmp" && \
                chmod 755 "$LIMAR__DATA_DIR/tmp" || {
                    limar__log 'ERROR: Creating /tmp in data directory failed'
                    return 1
                }
            fi

            # Set up context script, run LIMAR, and source context script
            local script_file="$(mktemp "$LIMAR__DATA_DIR/tmp/limar-source-$(basename "$SHELL").XXXXXXXX")"
            if [ "$LIMAR__PERFORMANCE_PROFILING_ENABLED" = 'true' ]; then
                "$LIMAR__PYTHON" -m cProfile -o "$LIMAR__REPO/limar.prof" "$LIMAR__REPO/main.py" --shell-script "$script_file" "$@"
            else
                "$LIMAR__PYTHON" "$LIMAR__REPO/main.py" --shell-script "$script_file" "$@"
            fi
            . "$script_file"
            rm "$script_file"
        fi
    }
    alias lm='limar'
fi
