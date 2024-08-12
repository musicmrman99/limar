# Local Information Management, Architecture, and Representation (LIMAR) System

LIMAR (`limar` or `lm`) is a system for discovering and managing mental contexts, tasks, projects, tools (git, git hosting provider tools, build systems, dependency managers, cloud provider tools, etc.), workflows (gitflow, github flow, custom flows), and much more.

To get it installed, see [Installation](#installation).

## Overview

`limar` has a variety of sub-commands for different purposes:

| Area    | Usable? | In Dev? | Command    | Summary                                                         |
|---------|---------|---------|------------|-----------------------------------------------------------------|
| Data    | &check; | &check; | `manifest` | Manage manifest files, eg. project definitions                  |
| Meta    |         |         | `for`      | Execute a supported sub-command against many repos at once      |
| Context | &check; | &check; | `env`      | Manage the shell environment, eg. current dir, env vars, etc.   |
| Project |         |         | `repo`     | Get info about repositories and manage repo instances and state |
| Project |         |         | `git`      | Execute a raw git command against a repo                        |
| Project |         |         | `sh`       | Execute a raw shell command against a repo                      |
| Misc    | &check; | &check; | `finance`  | Manage accounts and transactions, and run queries on them       |

## `manifest`

### Environment

```sh
LIMAR_MANIFEST_PATH = "$HOME/manifest.txt"      # Required
LIMAR_MANIFEST_DEFAULT_PROJECT_SET = 'some-set' # Optional, default: all projects
```

### Synopsis

```
limar manifest project [-p PROPERTY] [--project-set PROJECT_SET_PATTERN] PATTERN
limar manifest project-set [-p PROPERTY] PATTERN
```

### Description

Provides commands and plumbing methods for accessing declared information about
projects and sets of projects.

## `env`

### Synopsis

```
limar env cd PROJECT_PATTERN
limar [-cd PROJECT_PATTERN] ...
```

### Description

Provides commands relating to the shell environment. Currently includes:

- The ability to change directory to the root of the first project in the
  manifest to match the given pattern, either temporarily while executing
  another command by using the global `-cd` option, or permanently with the
  `env cd` command.

## `repo`

### Synopsis

```
limar repo instance [--project PROJECT_PATTERN]
limar repo update [--project PROJECT_PATTERN]
limar repo info [--project PROJECT_PATTERN]
limar repo (mr|pr) [--project PROJECT_PATTERN]
```

### Description

Provides commands relating to repository management.

## `for`

### Synopsis

```
limar for [-only] [-q QUANTIFIER] [-o ORDER] SET COMMAND ARGS...
```

### Description

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
limar for -only -order last -at-least 5 iac git status
```

## Installation

Requires Python 3.9+

Install with:
```sh
# Customise as you wish ...

# Set the location of the repo
LIMAR_REPO="$HOME/Source/limar" # Or wherever you want it

# Clone the repo (TODO: rename project to `limar`)
git clone https://github.com/musicmrman99/vcs "$LIMAR_REPO"

# Set up to enable on shell startup
cat <<EOF >> "$HOME/.bashrc" # Or .zshrc, etc.

# LIMAR
export LIMAR_REPO="$LIMAR_REPO"
export LIMAR_MANIFEST="$LIMAR_REPO/manifest"
export LIMAR_PYTHON='python3'
export LIMAR_PIP='pip3'

. "\$LIMAR_REPO/limar.def.sh"
EOF

# Re-source your shell init file
. "$HOME/.bashrc" # Or .zshrc, etc.

# Initialise LIMAR (install dependencies, check environment, etc.)
# If you need to customise the initialisation more than just python version,
# then edit the `limar.def.sh` script.
limar init
```

## Development

### Building from Source

To build the ANTLR4 language (after installing the packages in `requirements.txt` with `limar init`):

```sh
cd modules/manifest_lang && \
  antlr4 -Dlanguage=Python3 -o ./build ./Manifest.g4 && \
  cd ../..
```

### Running Tests

To run unit tests:

```sh
python -m unittest discover -s modules
```

### Checking the grammar of a manifest file

When developing ANTLR4 grammars, you can visualise the parse tree of a file for a particular grammar with:

```sh
antlr4-parse modules/manifest_lang/Manifest.g4 manifest -gui <file>
```

For example:

```sh
antlr4-parse modules/manifest_lang/Manifest.g4 manifest -gui manifest/manifest.txt
```
