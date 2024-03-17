# Git Source Manager

Git Source Manager (though the command is called `vcs`) is a system primarily designed to manage many git repositories quickly and easily.

To get it installed, see [Installation](#installation).

## Usage

`vcs` has a veriety of sub-commands for different purposes:

| Command        | Summary                                                            |
|----------------|--------------------------------------------------------------------|
| `vcs manifest` | Manage the vcs manifest file and project references                |
| `vcs clone`    | Manage your local clones of repos                                  |
| `vcs update`   | Fetch upstream changes and sync your local refs                    |
| `vcs for`      | Execute a supported sub-command against many repos at once         |
| `vcs cd`       | `cd` directly to a repo based on pattern matching of your manifest |
| `vcs info`     | Show various information about a repo's state                      |
| `vcs mr`       | Manage PR/MR-ing branches into the upstream and cleaning up after  |
| `vcs git`      | Execute a raw git command against a repo                           |
| `vcs sh`       | Execute a raw shell command against a repo                         |

### `manifest`

#### Environment

```sh
VCS_MANIFEST_PATH = "$HOME/manifest.txt"      # Required
VCS_MANIFEST_DEFAULT_PROJECT_SET = 'some-set' # Optional, default: all projects
```

#### Synopsys

```sh
vcs manifest project [-p PROPERTY] [--project-set PROJECT_SET_PATTERN] PATTERN
vcs manifest project-set [-p PROPERTY] PATTERN
```

#### Description

Provides commands and plumbing methods for accessing declared information about
projects and sets of projects.

### `env`

#### Synopsys

```sh
vcs env cd PROJECT_PATTERN
vcs [-cd PROJECT_PATTERN] ...
```

#### Description

Provides commands relating to the shell environment. Currently includes:

- The ability to change directory to the root of the first project in the
  manifest to match the given pattern, either temporarily while executing
  another command by using the global `-cd` option, or permanently with the
  `env cd` command.

### `for`

#### Synopsys

```sh
vcs for [-only] [-q QUANTIFIER] [-o ORDER] SET COMMAND ARGS...
```

#### Description

`-only` determines whether to short-circuit and yield the result as soon as the
QUANTIFIER's condition has been met.

`-q QUANTIFIER` determines how many projects with the TAG for which the given
COMMAND must yield true for the overall `for` command to yield true. The default
is `all`. It can be one of:

| Quantifier                | As Expr | Result is true if COMMAND yields true for ...                     |
|---------------------------|---------|-------------------------------------------------------------------|
| `no`                      | ` = 0`  | No project that yields a result                                   |
| `one`                     | ` = 1`  | Exactly one project that yields a result                          |
| `any`                     | `>= 1`  | At least one project that yields a result                         |
| `all`                     | ` = N`  | All projects that yield a result                                  |
| `exactly (NUM \| NUM%)`   | ` = X`  | Exactly NUM projects or NUM% of projects that yield a result      |
| `at-least (NUM \| NUM%)`  | `>= X`  | NUM projects or NUM% of projects or more that yield a result      |
| `at-most (NUM \| NUM%)`   | `<= X`  | No more than NUM projects or NUM% of projects that yield a result |
| `more-than (NUM \| NUM%)` | `>  X`  | More than NUM projects or NUM% of projects that yield a result    |
| `less-than (NUM \| NUM%)` | `<  X`  | Less than NUM projects or NUM% of projects that yield a result    |

`-o ORDER` determines which projects in the SET the COMMAND should be executed
against. The default ORDER is `first`. It can be one of:

| Order    | Execute the given COMMAND against each project ...             |
|----------|----------------------------------------------------------------|
| `first`  | In the order that projects are defined in the manifest         |
| `last`   | In the reverse order that projects are defined in the manifest |
| `random` | In a random order                                              |

`SET` is the set of projects to run the COMMAND against. It can be any tag or
tag set, whether static or dynamic.

`COMMAND` is the command to run against the projects. It can be any registered
command.

`ARGS...` are the arguments (one or more) to pass to the command.

Example:
```sh
vcs for -only -order last -at-least 5 iac git status
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

## Development

### Building from Source

To build the ANTLR4 language (after installing the packages in `requirements.txt` with `vcs init`):

```sh
cd src/manifest && \
  antlr4 -Dlanguage=Python3 -o ./build ./Manifest.g4 && \
  cd ../..
```

### Running Tests

To run unit tests:

```sh
python -m unittest discover -s src
```
