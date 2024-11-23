# Done

- ./ Change:
  - ./ the location that commands are parsed (info -> @query/@action)
    - ./ or @command? it's common to queries and actions, so move `command: ...` parsing there?

# Quick Notes and Misc

- make all assertion explanations use f-strings that use `[self.]function_name.__name__` references in place of literal method names (allows for easier refactoring)
- TESTING

- Rearrange into LIMAR (Local Information Management, Architecture, and Representation system)
  - goals:
    - management - the continuous adjustment of the more mutable configuration of a system to meet the needs of its stakeholders
    - architecture - the less mutable configuration of a system
    - representation - the display of the configuration of a system and changes to it in a comprehensible manner

    - in this context, configuration = structure and function (to meet context)
      - as in "the configuration of the living room" (the components, their orientation, and their functions, that as a whole make the room fit for purpose)
      - management = organising the structure and function to effectively fit into the context

  - design the LIMAR model to meet these goals in a REST-like way
    - entity types and actions (what entities are needed for the above goals in the currently understood context?)
    - entity relationships (how do they relate to each other?)
    - entity identity (what uniquely distinguishes between entities of the same type?)

  - understand how the existing modules and manifest declarations fit into the LIMAR model
    - core modules and `cache` are technical support tools
    - `manifest` manually curated input tool
    - `info` and `env` are data collection and management tools
    - `tr` and `finance` are data processing tools, of varying levels of specialisation (ie. information binding)

    - `lspci` (done) and `lsblk` (partial)
    - `git` (partial)

# Todo

## Develop Existing Modules

- `limar info`
  - templating (perameterising) commands in the command manifests using data from:
    - CLI input (eg. command-line arguments/options)
    - forwarded data
    - other commands in the command  manifest
    - other sources in LIMAR (eg. manifest, env, cache, phase, etc.)

  - think about the implications of templating, ie.
    - "parameterisation is generic, not compositional"
    - what makes a generic component composable?

    - b() {x(), y()}; a(), b(), c()
    -   vs.
    - b() {a(), x(), y(), c()}; b()

    - the more a component 'knows' and does, the more information is bound to it, and therefore the narrower its possible context of use
    - composable components have this characteristic to a lesser extent by *knowing less (or nothing) about the other components they can be combined with*

## Develop ModuleManager

- add branching, async, and continuous forwarding, eg. `[-\]][-/X][-\[]`, where:
  - `/` = async (ie. don't wait until the previous call is finished before starting the next call, and pass the data to the next call as and when the previous call makes data available to pass. This implies a temporary stream, but the previous call is still synchronous)
  - `X` = async continuous (ie. whether to keep the previous command running (or run it repeatedly) until it terminates by throwing StopIteration or something, and continuously forwarding data to the next module in a stream)

  - Or something. This would need some thought

- define appropriate custom exceptions for the different abstraction boundaries within LIMAR:
  - ModuleError
  - LIMARError
  - MMError
  - etc.

---

- only load modules depended on (directly or indirectly) by the directly-called module
- allow LIMAR to be run as a 'server', so that it starts up, waits for calls, then shuts down when asked (or when the shell terminates)
  - note that this is similar to a REPL, but allows backgrounding the process
  - this should be doable using the shell's built-in job control, though ofc. it depends on which shell the user has
  - https://www.digitalocean.com/community/tutorials/how-to-use-bash-s-job-control-to-manage-foreground-and-background-processes

## Develop Core Modules

- make log module include timestamp in message output
- rotate log + clean up old logs
- add logging to module invokation and all other relevant points

## Add More Modules

- `limar task` - add workload context manager
  - commit (job) [for (job)] (description)
  - wait [job:top(jobs)]
  - assign (user)
  - resume [job:top(jobs)]
  - bump (job)
  - reorder [job:bottom(jobs)]
    - like rebase

  - two stacks - active and blocked

- `limar open` - add command to open the remote url of a project, or any sub-url of it, in a browser

- `limar for` - execute management commands against multiple projects
  - how is it best to do this? `jq`-style using FP-like branching perhaps?

- `limar alias` - add an `alias` module to do things like `limar alias cd='env cd'`

---

- get a list of all unix/linux commands (that come pre-installed on at least one distro)
  - look in all folders on `$PATH`
    - ie. `echo "$PATH" | tr ':' '\n' | grep -v "^/mnt/c" | xargs -I{} sh -c 'printf "%s\n" "" "{}" "----------" ""; ls -Hl "{}"' > test.txt`
  - categorise and summarise them

- for `env`, look at:
  - zsh
  - environment vars
  - PS1/PS2 (and 3 & 4 in some shells)
    - eg. show if dirty git tree

## Tools

- **subversion**
  - https://en.wikipedia.org/wiki/Apache_Subversion
  - uses a different mental model of software versioning:
    - cares about versions, not the changes between them

- **ST**
  - 'simple terminal', presumably

- **tmux**
  - https://hackaday.com/2020/05/01/linux-command-line-productivity-with-tmux/

- **tig**
  - https://github.com/jonas/tig

- **github** CLI & **gitlab** CLI (or gitlab API, because its CLI isn't great)
  - https://hackaday.com/2020/02/15/github-goes-gui-less/

- modern replacements for traditional unix tools
  - https://hackaday.com/2018/08/29/linux-fu-modernize-your-command-line/
  - https://hackaday.com/2023/05/24/linux-fu-making-progress/
  - https://hackaday.com/2022/12/24/corefreq-gives-peek-at-cpu-performance-info-on-linux/
  - https://hackaday.com/2022/10/26/cat9-and-lash-want-to-change-your-linux-command-line/
    - https://arcan-fe.com/2022/10/15/whipping-up-a-new-shell-lashcat9/
  - https://hackaday.com/2021/06/21/a-collection-of-linux-tools-on-steroids/
  - https://hackaday.com/2018/10/24/linux-fu-marker-is-a-command-line-menu/

- **mermaid**:
  - https://mermaid.js.org/intro/
  - could be used to create graphs for `info` and other information sources

- **codeql**
  - https://codeql.github.com/docs/codeql-language-guides/basic-query-for-python-code/

- **jq** / **yq**
  - https://jqlang.github.io/jq/
  - https://mikefarah.gitbook.io/yq

### Things to investigate tools for

- Extract data about code elements (try to reuse existing libs where possible), eg:
  - Terraform resource files, types, names, properties, etc.

## Consider How Modules are Structured and Used

- consider the 7 Cs and SGCV
  - temporal scope/granualrity could be a useful way of categorising:
    - areas of code (eg. terraform resources)
    - commands (eg. whether data is something related to the current environment, or persistent)
    - other things?
