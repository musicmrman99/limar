# Done

- ./ fix "Attempt to proceed to STOPPING ModuleLifecycle phase before the RUNNING phase" when argparse throws an ArgumentError because argument parsing failed

- ./ add 'console' module
  - ./ add console printer to MM

- ./ support getting env vars without prefixing

- ./ update MM docstring

- X add `manifest [(--format|-f) FORMAT] <command> ...`
  - ./ moved formatting to `tr` module instead

- X maybe merge env and arg namespaces?
    def _merge_namespaces(self, ns1, ns2):
        return Namespace(**{**vars(ns1), **vars(ns2)})

  - ./ No, I think it's best to keep them separate

- ./ fix help text after splitting into two ModuleLifecycles

# Todo

- TESTING

Develop ModuleManager
--------------------------------------------------

- define appropriate custom exceptions for the different abstraction boundaries within VCS:
  - ModuleError
  - VCSError
  - etc.

---

- only load modules depended on (directly or indirectly) by the directly-called module

Develop Core Modules
--------------------------------------------------

- make log module include timestamp in message output
- rotate log + clean up old logs
- add logging to module invokation and all other relevant points

Develop Existing Modules
--------------------------------------------------

- do something with tag values in `manifest`

- add a way of viewing the cache, like:
```sh
python -c '
import glob, pathlib, pickle, json
glob_path = "manifest/projects.manifest.*.pickle"
path = glob.glob(glob_path)[0]
data_txt = pathlib.Path(path).read_bytes()
data_py = pickle.loads(data_txt)
data_json = json.dumps(data_py)
print(data_json)
'
```

Add More Modules
--------------------------------------------------

- add command to open the remote url of a project, or any sub-url of it, in a browser

- execute management commands against multiple projects, eg. `vcs for ...`
  - how is it best to do this? `jq`-style using FP-like branching perhaps?

- Add an `alias` module

---

- get a list of all unix/linux commands (that come pre-installed on at least one distro)
  - look in all folders on `$PATH`
    - ie. `echo "$PATH" | tr ':' '\n' | grep -v "^/mnt/c" | xargs -I{} sh -c 'printf "%s\n" "" "{}" "----------" ""; ls -Hl "{}"' > test.txt`

- categorise and summarise them

Look at:
- ST ('simple terminal', presumably)
- zsh
- PS1/PS2 (and 3 & 4 in some shells)
  - show if dirty git tree

---

- add subversion support
  - https://en.wikipedia.org/wiki/Apache_Subversion
  - uses a different mental model of software versioning:
    - cares about versions, not the changes between them

- Extract data about code elements (try to reuse existing libs where possible), eg:
  - Terraform resource files, types, names, properties, etc.

- creating graphs (for from the extracted info):
  - https://mermaid.js.org/intro/

- Rearrange into LIMAR (Local Information Management, Architecture, and Representation system)
  - management - the continuous adjustment of the more mutable configuration of a system to meet the needs of its stakeholders
  - architecture - the less mutable configuration of a system
  - representation - the display of the configuration of a system and changes to it in a comprehensible manner

  - in this context, configuration = structure and function (to meet context)
    - as in "the configuration of the living room" (the components, their orientation, and their functions, that as a whole make the room fit for purpose)
    - management = organising the structure and function to effectively fit into the context

---

- tmux
  - https://hackaday.com/2020/05/01/linux-command-line-productivity-with-tmux/

- github CLI & gitlab CLI (or gitlab API, because its CLI isn't great)
  - https://hackaday.com/2020/02/15/github-goes-gui-less/

- modern replacements for traditional unix tools
  - https://hackaday.com/2018/08/29/linux-fu-modernize-your-command-line/
  - https://hackaday.com/2023/05/24/linux-fu-making-progress/
  - https://hackaday.com/2022/12/24/corefreq-gives-peek-at-cpu-performance-info-on-linux/
  - https://hackaday.com/2022/10/26/cat9-and-lash-want-to-change-your-linux-command-line/
    - https://arcan-fe.com/2022/10/15/whipping-up-a-new-shell-lashcat9/
  - https://hackaday.com/2021/06/21/a-collection-of-linux-tools-on-steroids/
  - https://hackaday.com/2018/10/24/linux-fu-marker-is-a-command-line-menu/

Consider How Modules are Structured and Used
--------------------------------------------------

- consider the 7 Cs and SGCV
  - temporal scope/granualrity could be a useful way of categorising:
    - areas of code (eg. terraform resources)
    - commands (eg. whether data is something related to the current environment, or persistent)
    - other things?

# Scratchpad

## Concepts

### Subjects and Providers

A subject is anything you may want to know about or manipulate using `vcs`, such
as:

- Projects
- Project Sets

- Sources (source code, assets, etc.)
- Artifacts (binaries, archives/packages, bundles, etc.)
- Deployments (instances of a pieces of software)

- Changes (file history, tagged versions, tasks, (the act of) deployments, etc.)
- Quality (tests, validity, integrity, 7 Cs, etc.)
- Knowledge (comments, documentation strings, readmes, licencing, design information and visualisations, etc.)

Quality:
- correctness (ie. validity, discovered by testing, validation, monitoring, alerting)
- comprehensiveness
- consistency
- coherence (ie. utility)
- conciseness
- clarity (also aids Knowledge)
- completeness (eg. is it releasable?)

Check Areas of Competence for anything else I might have

**TODO**: Check git presentation for specific things you may want to control (that are usually put on the `.gitignore`).

A provider is a module that adds the ability to view, modify, and otherwise
manipulate one or more subjects using a specific tool. For example, the `git`
provider adds various commands for manipulating git repositories, mainly within
the `changes` subject.

### Software Engineering Common Tasks

- docs generation
- validation, tests (inc. performance)
- infrastructure, pipelines, monitoring/alerting
- ID+T, certs
- docker
- machine image builds

- data manipulation
  - jq / yq

### Areas of SE

Confirmed
--------------------

- All systems
  - communication (inc. networking, remote API calls, messaging, events, notification)
  - security and compliance (inc. ID&T/IAM (inc. authn/authz), encryption (in transit, at rest), GDPR, approvals)
  - performance (inc. caching)
  - error handling (inc. detection, handling, storage, resolution)
  - monitoring and alerting (inc. audit, logging, instrumentation, tracing (ie. request/event tracing through many systems), runtime intelligence (ie. usage, patterns, analytics, visualisation, etc.), what/where/how)

- Some systems
  - configuration management (esp. in microservices)
  - discovery (inc. of systems, services, available data)
  - transaction management (inc. distributed agreement, ACID-ity)
  - localisation (inc. natural language translation)

Scratchpad
--------------------------------------------------

- validation (inc. of data, code (ie. testing))
- infrastructure (what services run on)

----------

- standards, design, delivery, and support

- availability, scalability, performance, fault tolerance, reliability, security, elasticity (scalability), deployability, testability, agility, recoverability, learnability
  - https://itechnolabs.ca/software-architecture-5-principles-you-should-know/

--------------------

- general software design principles:
  - SOLID
  - UX principles
  - DRY
  - obvious things (aka. YAGNI - don't spend more time/effort/money on something than needed)

- value = benefit - cost
  - often, benefit and cost aren't even in the same units, so cannot be straightforwardly subtracted
  - the reality will be based on context (eg. what's important to you) and intuation

- who is involved?

References
--------------------

- https://www.google.co.uk/search?q=cross-cutting+concerns+in+software+management
- https://www.google.co.uk/search?q=cross-cutting+concerns+in+software+organisation

- https://maven.apache.org/guides/introduction/introduction-to-the-lifecycle.html#Lifecycle_Reference

- Aspects of development:
  - https://medium.com/techmonks/cross-cutting-concerns-for-an-enterprise-application-ef9884e6bed3
  - https://docs.firstdecode.com/architecture/cross-cutting-concerns-2/
  - https://www.youtube.com/watch?app=desktop&v=Q06XIV2AR2I
  - https://www.c-sharpcorner.com/blogs/cross-cutting-concepts-in-a-multilayer-application
  - https://www.sketchbubble.com/en/presentation-cross-cutting-concerns.html
  - https://www.cshandler.com/2015/10/managing-cross-cutting-concerns-logging.html
  - https://www.linkedin.com/posts/milan-jovanovic_cross-cutting-concerns-are-software-aspects-activity-7169315567454113792-hIPz/
  - https://www.researchgate.net/figure/Banking-system-cross-cutting-concerns_fig1_332881268
    - also appears on the youtube vid above
  - https://itechnolabs.ca/software-architecture-5-principles-you-should-know/
  - https://guidanceshare.com/wiki/Application_Architecture_Guide_-_Chapter_1_-_Fundamentals_of_Application_Architecture#Approach_to_Architecture
    - see below for whole Wiki
  - https://medium.com/@mithunsasidharan/aspect-oriented-programming-overview-6c03235e666a
  - https://en.wikipedia.org/wiki/Instrumentation_(computer_programming)

- also: https://guidanceshare.com/wiki/Main_Page
  - same idea I had of making a wiki of this stuff
