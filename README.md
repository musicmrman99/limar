# Git Source Manager

Git Source Manager (though the command is called `vcs`) is a system primarily designed to manage many git repositories quickly and easily.

To get it installed, see [Installation](#installation).

## TODO

- ./ rename CommandSet -> ModuleSet, cmd/_cmd -> mod/_mod
- ./ change module.setup_args() signature to setup_args(*, parser, root_parser)

- ./ create multi-phase module system like:
  - ./ __init__()
    - called once for all modules during registration

  - ./ configure_args(env, parser, root_parser)
    - called once for all modules during registration

  - ./ configure(mod, env, args)
    - called once for all modules after all modules have done basic initialisation
    - X other configure_*() methods (except the special ones mentioned above) of
      other modules may be called here *without* invoking the module.
      - handled differently, but task is done.

  - ./ start(mod, env, args)
    - called once the first time the module is invoked (if it is invoked)

  - ./ invoke(phase, mod, env, args)
    - called each time the module is invoked, regardless of whether or how it is used

  - ./ stop(mod, env, args)
    - called once the first time the module is invoked (if it is invoked)

- ./ don't re-register a module if it's already been registered
- ./ set module phases

- ./ improve state handling in modulemanager
  - ./ env vs. self._env is a mess
  - ./ same with args vs. self._args
  - ./ same with self._phase

- ./ use Test.configure(mod, **) to call Manifest.configure_context_hooks()
- ./ use Manifest.start() instead of Manifest._load_manifest()
  - ./ and remove Manifest._load_manifest() from module methods

---

- ./ transition to use argparse.Namespace for env parsing, rather than a custom Evironment
  - ./ convert Environment into envparse
  - fix modules

- ./ envparse:
  - ./ root_parser = envparse.EnvironmentParser()
  - X subparsers = root_parser.subparsers()

  - ./ parser = subparsers.add_parser(...)
  - ./ provide the parser and a root_parser (a subparser has automatic var name prefixing)

  - ./ env = root_parser.parse_env(cli_env)
  - ./  OR
  - ./ env = root_parser.parse_env()

VCS_VERBOSITY           -> unused
VCS_LOG_VERBOSITY       -> same
VCS_REPO                -> unused
VCS_MANIFEST            -> VCS_MANIFEST_ROOT
VCS_DEFAULT_PROJECT_SET -> VCS_MANIFEST_DEFAULT_PROJECT_SET

---

- maybe merge env and arg namespaces?
    def _merge_namespaces(self, ns1, ns2):
        return Namespace(**{**vars(ns1), **vars(ns2)})

- make log module include timestamp in message output
- rotate log + clean up old logs
- add logging to module invokation and all other relevant points
- TESTING

---

- setup ssh
  - ssh-keygen -t ed25519 -C 'your.email@address.com'
    > enter a strong password for your key

- set up repository hosting provider
  - put your pubkey onto the provider (usage type: authentication and signing)
  - [if needed] set up a token to access other systems in the provider, eg. repositories, web hosting, etc.

- set up git
  - tools
    - git config --global core.editor nano

  - aliases
    - git config --global alias.repo 'log --oneline --graph --all'
    - git config --global alias.repo-l 'log --oneline --graph'
    - git config --global alias.repo-b 'log --oneline --graph develop..HEAD'
      - ideally, this would be relative to the repo's default branch

  - user
    - git config --global user.name 'Your Name'
    - git config --global user.email 'your.email@address.com'

  - commit signing
    - git config --global commit.gpgsign true
    - git config --global gpg.format ssh
    - git config --global user.signingkey ~/.ssh/id_ed25519.pub

- set up your ssh-agent (in each shell instance)
  - eval `ssh-agent`
  - ssh-add
    > enter your key's password

---

Ideas from: https://www.youtube.com/watch?v=aolI_Rz0ZqY

git blame -wCCCL <range_start>,<range_end> <path/to/file>
git log [--full-diff] -L <range_start>,<range_end>:<path/to/file>
git log -S <search_string>
git reflog - history of current commit
git diff --word-diff --word-diff-regex='.'

git push --force-with-lease (not -f)

git config --global rerere.enabled true (re-apply resolutions to conflicts, etc.)
git config --global fetch.writeCommitGraph true (compute the commit graph on fetch, rather than on `git log --graph`)

git clone --filter=blob:none

git maintenance start (adds a cron job to do maintenance on repos)

---

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
