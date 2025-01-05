LIMAR__STARTUP_FAILED='false'

# Define logging utils
# --------------------------------------------------

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

# Define other utils
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' ]; then
    limar__install_python_requirements() {
        local component="$1"
        limar__log "Installing python dependencies for component '$component'" \
            " from '$LIMAR__REPO/requirements-$component.txt'"
        "$LIMAR__PIP" install -r "$LIMAR__REPO/requirements-$component.txt" || return $?
    }

    limar__create_data_directory() {
        local dir="$1"

        limar__log "Creating${dir:+" '/$dir' in"} LIMAR data directory at" \
            " '$LIMAR__DATA_DIR/$dir'"
        mkdir "$LIMAR__DATA_DIR/$dir" && \
        chmod 755 "$LIMAR__DATA_DIR/$dir" || {
            limar__log "ERROR: Creating${dir:+" '/$dir' in"} data directory" \
                " failed"
            return 1
        }
    }

    limar__create_data_file() {
        local file="$1"
        if [ -z "$file" ]; then
            limar__log "ERROR: limar__create_data_file(): File not given"
            return 1
        fi

        limar__log "Creating '/$file' in LIMAR data directory at" \
            " '$LIMAR__DATA_DIR/$file'"
        touch "$LIMAR__DATA_DIR/$file" && \
        chmod 644 "$LIMAR__DATA_DIR/$file" || {
            limar__log "ERROR: Creating '/$file' in data directory failed"
            return 1
        }
    }

    limar__link_file() {
        local src="$1" dest="$2"
        echo "'$src' -> '$dest'"
        ln -sf "$dest" "$src"
    }
fi

# Define runner
# --------------------------------------------------

if [ "$LIMAR__STARTUP_FAILED" = 'false' ]; then
    limar() {
        local command="${1%%:*}"
        local component="${1#*:}"
        if [ "$component" = "$command" ]; then component=''; fi

        if [ "$command" = '/help' ]; then
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
                ' building dynamic components, installing user-specific files' \
                ' and directories, and linking any needed content in the data' \
                ' directory (including the LIMAR installation). `/init` will' \
                ' only perform each initialisation step if it needs' \
                ' (re-)performing (checked separately per-component).'

            limar__log -i -l \
                'limar /build' \
                'limar /rebuild' \
                'limar /clean'
            limar__log -i=4 -s 'Build dynamic components. `/build` will only' \
                ' build the components if they are not already built (checked' \
                ' separately per component). `/clean` will remove the built' \
                ' components without rebuilding them.'

            limar__log -i -l \
                'limar /install' \
                'limar /reinstall' \
                'limar /remove'
            limar__log -i=4 -s 'Install components into the user directory.' \
                ' `/install` will only install the components if they are not' \
                ' already installed (checked separately per component).' \
                ' `/remove` will remove the installed components without' \
                ' reinstalling them.'
            limar__log -i=4 'WARNING:'
            limar__log -i=6 -s 'Uninstalling with `/uninstall` has the same' \
                ' effects (and more) as unlinking with `/unlink`. See the' \
                ' warning on `/unlink` for details. If following the' \
                ' instructions there to re-link after an uninstall, rather' \
                ' than an unlink, then after re-enabling usage of the LIMAR' \
                ' bootstrap, but before re-linking, LIMAR must be' \
                ' re-installed with `limar /install`.'

            limar__log -i -l 'limar /linked'
            limar__log -i=4 -s 'Print the currently linked content for each' \
                ' component (including the LIMAR installation for the `core`' \
                ' component).'

            limar__log -i -l \
                'limar /link' \
                'limar /relink' \
                'limar /unlink'
            limar__log -i=4 -s 'Link relevant content for components in the' \
                ' LIMAR data directory. For the `core` component, link the' \
                ' LIMAR installation specified in $LIMAR__REPO (ie. set it as' \
                ' the one to use). `/link` will only perform linking if there' \
                ' is no currently linked content (checked separately per' \
                ' component). `/unlink` will unlink the currently linked' \
                ' content without re-linking the content.'
            limar__log -i=4 'WARNING:'
            limar__log -i=6 'Unlinking the `core` component with `/unlink`' \
                ' will make the LIMAR bootstrap no longer loadable in the' \
                ' normal way until a new installation is linked. If a new' \
                ' installation is not linked in the same shell session as' \
                ' the current one was unlinked, then to manually re-enable' \
                ' usage of the LIMAR bootstrap to perform the link, the' \
                ' `scripts` directory of a specific LIMAR installation must' \
                ' be added to PATH, and the `limar.def.sh` script must be' \
                ' re-sourced from that installation. This is similar to the' \
                ' process during initial installation of LIMAR:'
            limar__log -i=8 -l -s \
                'export LIMAR__REPO="/path/to/limar/installation"' \
                'export PATH="$LIMAR__REPO/scripts:$PATH"' \
                '. "$LIMAR__REPO/limar.def.sh"' \
                'limar /link'

            limar__log -i -l \
                'limar /reload' \
                'limar /unload'
            limar__log -i=4 -s 'Reload (or unload) the LIMAR bootstrap.' \
                ' Useful for testing changes to the boostrap.'

            limar__log -s 'COMPONENTS:'

            limar__log -i -l -s \
                '- core' \
                '- context' \
                '- manifest' \
                '- finance' \

        elif [ "$command" = '/env' ]; then
            echo "Core:"
            env | grep -E '^LIMAR__[^=]*'
            echo
            echo "Components:"
            env | grep -v '^LIMAR__' | grep -E '^LIMAR_[^=]*'

        elif [ "$command" = '/init' -o "$command" = '/reinit' ]; then
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

            # Create data dir
            if [ ! -d "$LIMAR__DATA_DIR" ]; then
                limar__create_data_directory || return $?
            else
                limar__log 'Data directory exists'
            fi

            # Build remaining components
            if [ "$command" = '/reinit' ]; then
                limar "/rebuild:$component" || return $?
            else
                limar "/build:$component" || return $?
            fi

            # Install any other files/dirs required
            if [ "$command" = '/reinit' ]; then
                limar "/reinstall:$component" || return $?
            else
                limar "/install:$component" || return $?
            fi

            # Link content in the data dir, including the installation of LIMAR
            if [ "$command" = '/reinit' ]; then
                limar "/relink:$component" || return $?
            else
                limar "/link:$component" || return $?
            fi

        elif [ "$command" = '/build' -o "$command" = '/rebuild' -o "$command" = '/clean' ]; then
            local manifest_lang_path="$LIMAR__REPO/modules/manifest_lang"

            # Install deps + build: core component
            if [ -z "$component" -o "$component" = 'core' ]; then
                if [ "$command" = '/build' -o "$command" = '/rebuild' ]; then
                    limar__install_python_requirements 'core'
                fi
            fi

            # Install deps + build: manifest component
            if [ -z "$component" -o "$component" = 'manifest' ]; then
                if [ "$command" = '/rebuild' -o "$command" = '/clean' ]; then
                    limar__log 'Cleaning LIMAR manifest parser build'
                    rm -rf "$manifest_lang_path/build"
                fi

                if [ \( "$command" = '/build' -a ! -d "$manifest_lang_path" \) -o "$command" = '/rebuild' ]; then
                    limar__install_python_requirements 'manifest'

                    limar__log 'Building LIMAR manifest parser in' \
                        " '$manifest_lang_path'"
                    failed='false'
                    cd "$manifest_lang_path" || {
                        limar__log 'ERROR: Failed to build parser: Could not' \
                            " change directory to '$manifest_lang_path'"
                        return 1
                    }
                    antlr4 -Dlanguage=Python3 -o ./build ./Manifest.g4 || failed='true'
                    cd - >/dev/null
                    if [ "$failed" = 'true' ]; then
                        limar__log 'ERROR: Failed to build parser'
                        return 1
                    fi

                elif [ "$command" = '/build' ]; then
                    limar__log 'LIMAR manifest parser already built, skipping' \
                        ' building'
                    limar__log 'Use `limar /rebuild` to force a rebuild, or' \
                        ' `limar /reinit` to force a full reinitialisation'
                fi
            fi

            # Install deps + build: finance component
            if [ -z "$component" -o "$component" = 'finance' ]; then
                if [ "$command" = '/build' -o "$command" = '/rebuild' ]; then
                    limar__install_python_requirements 'finance'
                fi
            fi

        elif [ "$command" = '/install' -o "$command" = '/reinstall' -o "$command" = '/remove' ]; then
            # Create files and directories: core component
            if [ -z "$component" -o "$component" = 'core' ]; then
                # bin directory (for linking to a LIMAR installation)
                if [ "$command" = '/reinstall' -o "$command" = '/remove' ]; then
                    limar__log 'Removing /bin from data directory'
                    rm -rf "$LIMAR__DATA_DIR/bin"
                fi
                if [ \( "$command" = '/install' -a ! -d "$LIMAR__DATA_DIR/bin" \) -o "$command" = '/reinstall' ]; then
                    limar__create_data_directory 'bin' || return $?
                elif [ "$command" = '/install' ]; then
                    limar__log '/bin in LIMAR data directory already exists'
                fi
            fi

            # Create files and directories: context component
            if [ -z "$component" -o "$component" = 'context' ]; then
                # tmp directory (for the context script)
                if [ "$command" = '/reinstall' -o "$command" = '/remove' ]; then
                    limar__log 'Removing /tmp from data directory'
                    rm -rf "$LIMAR__DATA_DIR/tmp"
                fi
                if [ \( "$command" = '/install' -a ! -d "$LIMAR__DATA_DIR/tmp" \) -o "$command" = '/reinstall' ]; then
                    limar__create_data_directory 'tmp' || return $?
                elif [ "$command" = '/install' ]; then
                    limar__log '/tmp in LIMAR data directory already exists'
                fi
            fi

            # Create files and directories: manifest component
            if [ -z "$component" -o "$component" = 'manifest' ]; then
                # manifest directory (for linking to manifest directories)
                if [ "$command" = '/reinstall' -o "$command" = '/remove' ]; then
                    limar__log 'Removing /manifest from data directory'
                    rm -rf "$LIMAR__DATA_DIR/manifest"
                fi
                if [ \
                    \( \
                        "$command" = '/install' -a ! \( \
                            -d "$LIMAR__DATA_DIR/manifest" -o \
                            -f "$LIMAR__DATA_DIR/manifest/.manifest-list.txt" \
                        \) \
                    \) -o "$command" = '/reinstall' \
                ]; then
                    limar__create_data_directory 'manifest' || return $?
                    limar__create_data_file 'manifest/.manifest-list.txt' || return $?
                elif [ "$command" = '/install' ]; then
                    limar__log '/manifest in LIMAR data directory already exists'
                fi
            fi

        elif [ "$command" = '/linked' ]; then
            if [ -z "$component" -o "$component" = 'core' ]; then
                if [ -L "$LIMAR__DATA_DIR/bin/limar.def.sh" ]; then
                    dirname "$(readlink "$LIMAR__DATA_DIR/bin/limar.def.sh")"
                else
                    limar__log 'No linked installation'
                fi
                limar__log
            fi

            if [ -z "$component" -o "$component" = 'manifest' ]; then
                if [ -d "$LIMAR__DATA_DIR/manifest" ]; then
                    for manifest_dir in "$LIMAR__DATA_DIR/manifest"/*; do
                        if [ -d "$manifest_dir" ]; then
                            if [ -L "$manifest_dir" ]; then
                                readlink "$manifest_dir"
                            else
                                echo "$manifest_dir"
                            fi
                        else
                            limar__log \
                                "WARNING: Non-directory '$manifest_dir' in" \
                                ' manifest link directory'
                        fi
                    done
                else
                    limar__log 'No linked manifests - manifest component not' \
                        ' installed (missing manifest link directory)'
                fi
                limar__log
            fi

        elif [ "$command" = '/link' -o "$command" = '/relink' -o "$command" = '/unlink' ]; then
            if [ -z "$component" -o "$component" = 'core' ]; then
                local limar_bin_path="$LIMAR__DATA_DIR/bin"
                if [ "$command" = '/relink' -o "$command" = '/unlink' ]; then
                    limar__log 'Unlinking currently linked LIMAR installation'
                    rm -f "$limar_bin_path"/*
                fi
                if [ \( "$command" = '/link' -a ! -L "$limar_bin_path/limar.def.sh" \) -o "$command" = '/relink' ]; then
                    # Check that the target is a valid LIMAR installation
                    if [ ! -f "$LIMAR__REPO/limar.def.sh" -o -L "$LIMAR__REPO/limar.def.sh" ]; then
                        limar__log "ERROR: '$LIMAR__REPO' is not a LIMAR" \
                            " installation"
                        return 1
                    fi
                    limar__log "Linking to LIMAR installation at '$LIMAR__REPO'"

                    # Link dependency and bootstrap scripts
                    local script
                    for script in "$LIMAR__REPO"/scripts/*; do
                        limar__link_file "$limar_bin_path/$(basename "$script")" "$script"
                    done
                    limar__link_file "$limar_bin_path/limar.def.sh" "$LIMAR__REPO/limar.def.sh"
                    limar__log -s "Linked to LIMAR installation '$LIMAR__REPO'."

                    # Remind users to update their vars if needed
                    limar__log 'NOTE:'
                    limar__log -i -s \
                        'If needed, remember to update your shell startup' \
                        ' script (.bashrc, .zshrc, etc.) with the new' \
                        ' environment variable values .'

                elif [ "$command" = '/link' ]; then
                    limar__log 'LIMAR installation already linked'
                    limar__log 'Use `limar /relink` to force a relink, or' \
                        ' `limar /reinit` to force a full reinitialisation'
                fi
            fi

            if [ -z "$component" -o "$component" = 'manifest' ]; then
                local limar_manifest_path="$LIMAR__DATA_DIR/manifest"
                if [ "$command" = '/relink' -o "$command" = '/unlink' ]; then
                    limar__log 'Unlinking all currently linked LIMAR manifest' \
                        ' directories'
                    rm -f "$limar_manifest_path"/*
                fi
                local manifests_linked="$(find "$limar_manifest_path" -name '*.manifest\.txt' -type f -printf '.' | wc -c)"
                if [ \( "$command" = '/link' -a -s "$limar_manifest_path/.manifest-list.txt" -a "$manifests_linked" = 0 \) -o "$command" = '/relink' ]; then
                    while read -r manifest_path; do
                        limar__link_file "$limar_manifest_path/$(basename "$manifest_path")" "$manifest_path"
                        limar__log -s "Linked to LIMAR manifest '$manifest_path'."
                    done < "$limar_manifest_path/.manifest-list.txt"
                    limar__log -s "Linked to LIMAR manifests."

                elif [ "$command" = '/link' ]; then
                    limar__log 'LIMAR manifests already linked, or no' \
                        ' manifests to link'
                    limar__log 'Use `limar /relink` to force a relink, or' \
                        ' `limar /reinit` to force a full reinitialisation'
                fi
            fi

        elif [ "$command" = '/reload' -o "$command" = '/unload' ]; then
            if [ -z "$component" -o "$component" = 'core' ]; then
                limar__log 'Unloading LIMAR bootstrap'
                # In reverse order of declaration
                unalias lm
                unset -f limar
                unset -f limar__link_file
                unset -f limar__create_data_file
                unset -f limar__create_data_directory
                unset -f limar__install_python_requirements
                if command -v limar__get_script_dir_bash >/dev/null 2>&1; then
                    unset -f limar__get_script_dir_bash
                fi
                # NOTE: Does not unset vars or env vars, or strip relevant
                #       locations from PATH, otherwise user settings in the
                #       shell's startup script (which is not reloaded) would be
                #       lost.

                if [ "$command" = '/reload' ]; then
                    limar__log 'Reloading LIMAR bootstrap from linked' \
                        ' installation'
                fi
                unset -f limar__log

                if [ "$command" = '/reload' ]; then
                    # Assumes it's already linked
                    . "$LIMAR__DATA_DIR/bin/limar.def.sh"
                fi
            fi

        else
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
