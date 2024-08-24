# LIMAR

LIMAR (the Local Information Management, Architecture, and Representation System; `limar` or `lm`) is an easy-to-use system for discovering and managing contexts, tasks, projects, tools (git, git hosting provider tools, build systems, dependency managers, cloud provider tools, etc.), workflows (gitflow, github flow, etc.), and much more.

To get it installed, see [Installation](#installation).

## Overview

LIMAR has a variety of sub-commands for different purposes:

| Area    | Usable? | In Dev? | Command    | Summary                                                         |
|---------|---------|---------|------------|-----------------------------------------------------------------|
| Data    | &check; | &check; | `manifest` | Manage data declared in manifest files, eg. project definitions |
| Data    | &check; | &check; | `info`     | Manage data discoverable using available commands               |
| Util    |         |         | `for`      | Execute a supported LIMAR against many repos at once            |
| Util    | &check; | &check; | `tr`       | Transforms data using any of various available tools            |
| Context | &check; | &check; | `env`      | Manage the shell environment, eg. current dir, env vars, etc.   |
| Project |         |         | `repo`     | Get info about repositories and manage repo instances and state |
| Project |         |         | `git`      | Execute a raw git command against a repo                        |
| Project |         |         | `sh`       | Execute a raw shell command against a repo                      |
| Misc    | &check; | &check; | `finance`  | Manage accounts and transactions, and run queries on them       |

It also has various other modules that provide configuration and supporting services to the commands above. Some of these modules require configuration, and so have been included in the below list.

## `cache`

### Environment

```sh
export LIMAR_CACHE_ROOT="$HOME/Documents/LIMAR/cache` # Required
```

### Synopsis

```
limar cache list
limar cache get ENTRY_NAME
limar cache delete ENTRY_NAME
limar cache clear
```

### Description

Provides storage services to other modules. Configuration of this module is
required for any modules that use it to function.

Has commands for listing, showing, and deleting the resulting cached data. Has
no command for setting cached data because no modules would use new files, and
the structure of existing files is considered an implementation detail of the
modules that create them.

## `manifest`

### Environment

```sh
export LIMAR_MANIFEST_ROOT="$HOME/Documents/LIMAR/manifest" # Required
export LIMAR_MANIFEST_DEFAULT_PROJECT_SET='some-set'        # Optional, default: all projects
```

### Synopsis

```
limar manifest item [--item-set PATTERN] PATTERN
limar manifest item-set [-s] PATTERN
```

### Description

Provides commands and plumbing methods for accessing declared information about
items (which can be various kinds of things, eg. commands, projects, etc.) and
sets of items. Items and items sets are named.

`manifest item` returns the first item whose name (aka. ref) matches the given
`PATTERN`.

`manifest item-set` returns the first item set whose name (aka. ref) matches the
given `PATTERN`. If `-s` (or `--item-set-spec`) is given, then interpret
`PATTERN` as an item set specification and output the items included in a new
temporary item set declared using that specification in the context of *all*
items from *all* manifests. This option allows complex runtime querying of the
global manifest. See the "Declarations" section of `limar manifest --docs` for
details on the format of an item set specification.

For details about how to write a manifest file to declare items and item sets,
see `limar manifest --docs`. To find what manifest files there are, see the
manifest root directory (which is given in the `LIMAR_MANIFEST_ROOT` environment
variable). To find how the items, item sets, and contexts of each manifest are
interpreted, see the docs of the module(s) that interpret the relevant
manifest(s) using the `--docs` option of those modules.

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

**Note**: LIMAR requires Python 3.9+

To install, run the following in a new terminal (customise as you wish):
```sh
# Set the location of the repo, and optionally where you want the LIMAR data
# directory to be.
export LIMAR__REPO="$HOME/Source/limar"
#export LIMAR__DATA_DIR="$HOME/.limar" # This is the default

# Clone the repo (TODO: rename project to `limar`)
git clone https://github.com/musicmrman99/vcs "$LIMAR__REPO"

# Initialise LIMAR (check environment, install dependencies, link to repo paths,
# etc.). If you need to customise the initialisation more than changing the
# python version, then edit the `limar.def.sh` script's `/init` command.
export PATH="$LIMAR__REPO/scripts:$PATH"
. "$LIMAR__REPO/limar.def.sh"
limar /init

# Set up LIMAR on shell startup
cat <<EOF >> "$HOME/.bashrc" # Or .zshrc, etc.

# LIMAR
# Global overrides (may be required, depending on your setup):
# - If \`limar init\` said you needed to add this (ie. if you're using a shell for which LIMAR can't automatically set the location), then set this.
#export LIMAR__REPO="$LIMAR__REPO"
# - If you need something different, then set these as needed.
#export LIMAR__PYTHON='$LIMAR__PYTHON'
#export LIMAR__PIP='$LIMAR__PIP'
#export LIMAR__DATA_DIR='$LIMAR__DATA_DIR'
# - If you want to profile LIMAR's performance, then set this to true
#export LIMAR__PERFORMANCE_PROFILING_ENABLED='false'

# Any module-specific environment variables go here ...

. "$LIMAR__DATA_DIR/bin/limar.def.sh"
EOF
```

Test the setup by opening a new terminal and running `limar /env`.

### Moving Data Directory

If you ever want to move the data directory, you only have to move the directory and update your shell startup script (.bashrc, .zshrc, etc.) to point to the new location when sourcing `limar.def.sh`.

### Moving Repo Directory

If you ever want to use a different LIMAR repo directory (eg. with a different checked-out version of LIMAR), then run:
```sh
limar /link '/new/path/to/limar'
. "$LIMAR__DATA_DIR/bin/limar.def.sh"
```

If you ever want to move an existing repo directory, then:

1. Open a shell that loads LIMAR.
2. Move the LIMAR repo directory.
3. In the shell you opened, run the same script as above to link to the new location.

If you move the repo directory without a shell with LIMAR loaded, then any new shells you start will be unable to find LIMAR's bootstrap script that is needed to run the `limar /link` command above. This is easiest to fix by moving the repo directory back and following the above process.

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
