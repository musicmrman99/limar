# Git Source Manager

Git Source Manager (though the command is called `vcs`) is a system primarily designed to manage many git repositories quickly and easily.

To get it installed, see [Installation](#installation).

## Usage

`vcs` has a veriety of sub-commands for different purposes:

| Command        | Summary                                                            |
|----------------|--------------------------------------------------------------------|
| `vcs manifest` | Manage the vcs manifest file                                       |
| `vcs clone`    | Manage your local clones of repos                                  |
| `vcs update`   | Fetch upstream changes and sync your local refs                    |
| `vcs many`     | Execute a supported sub-command against many repos at once         |
| `vcs cd`       | `cd` directly to a repo based on pattern matching of your manifest |
| `vcs info`     | Show various information about a repo's state                      |
| `vcs mr`       | Manage PR/MR-ing branches into the upstream and cleaning up after  |
| `vcs git`      | Execute a raw git command against a repo                           |
| `vcs sh`       | Execute a raw shell command against a repo                         |

### `vcs manifest`

```sh
vcs manifest [-show] [-build]
```

## Installation

Install with:
```sh
# Customise as you wish ...

# Set the location of the repo
VCS_REPO="$HOME/Source/vcs" # Or wherever you want it

# Clone the repo
git clone https://github.com/musicmrman99/vcs "$VCS_REPO"

# Set up to enable on shell startup
cat <<EOF >> "$HOME/.bashrc" # Or .zshrc, etc.

# Git Source Manger (aka. \`vcs\`)
export VCS_REPO="$VCS_REPO"
export VCS_MANIFEST="$VCS_REPO/manifest"
export VCS_PYTHON='python3'
export VCS_PIP='pip3'

. "\$VCS_REPO/vcs.def.sh"
EOF

# Re-source your shell init file
. "$HOME/.bashrc" # Or .zshrc, etc.

# Initialise vcs (install dependencies, check environment, etc.)
# If you need to customise the initialisation more than just python version,
# then edit the `vcs.def.sh` script.
vcs init
```

## Building from Source

To build the ANTLR4 language (after installing the packages in requiremetns)

```sh
antlr4 -Dlanguage=Python3 -o "$VCS_REPO/src/manifest/build" "$VCS_REPO/src/manifest/Manifest.g4"
```
