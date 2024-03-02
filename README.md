# Git Source Manager

Git Source Manager (though the command is called `vcs`) is a system primarily designed to manage many git repositories quickly and easily.

To get it installed, see [Installation](#installation).

## TODO

- Execute management commands against multiple projects, eg. `vcs for ...`

- Extract data about code elements (try to reuse existing libs where possible), eg:
  - Terraform resource files, types, names, properties, etc.

- Rearrange into LIMAR (Local Information Management, Architecture, and Representation system)

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

```
... manifest resolve \
  [--project-set PROJ_SET_PATTERN] \
  [-l {local,remote}] \
  [-r {root,manifest,current}] \
  PATTERN
```

### `for`

#### Synopsys

```
... for [-only] [-q QUANTIFIER] [-o ORDER] SET COMMAND ARGS...
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

## Building from Source

To build the ANTLR4 language (after installing the packages in requiremetns):

```sh
antlr4 -Dlanguage=Python3 -o src/manifest/build src/manifest/Manifest.g4
```

## Running Tests

To run unit tests:

```sh
python -m unittest discover -s src
```
