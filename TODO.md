# Todo

- only load modules depended on (directly or indirectly) by the directly-called module

- add `manifest [(--format|-f) FORMAT] <command> ...`

- add command to open the remote url of a project, or any sub-url of it, in a browser

---

- get a list of all unix/linux commands (that come pre-installed on at least one distro)
  - look in all folders on `$PATH`
    - ie. `echo "$PATH" | tr ':' '\n' | grep -v "^/mnt/c" | xargs -I{} sh -c 'printf "%s\n" "" "{}" "----------" ""; ls -Hl "{}"' > test.txt`

- categorise and summarise them

Look at:
- ST
- zsh
- PS1/PS2 (and 3 & 4 in some shells)
  - show if dirty git tree

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

  - usage
    - git config --global push.autosetupremote true

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

- common git commands
  - init
  - clone
  - status
  - add
  - commit
  - push
  - pull
  - branch
  - checkout
  - merge
  - diff
  - log

  - https://media.licdn.com/dms/image/D5622AQGyZVKG_zTdkg/feedshare-shrink_2048_1536/0/1709867659521?e=1713398400&v=beta&t=YYf2nC6L6YYy3A8u7lpP3CeTtsuBgv4sA9Vq-neZ03A

---

- maybe merge env and arg namespaces?
    def _merge_namespaces(self, ns1, ns2):
        return Namespace(**{**vars(ns1), **vars(ns2)})

- make log module include timestamp in message output
- rotate log + clean up old logs
- add logging to module invokation and all other relevant points

---

- TESTING

---

- support getting env vars without prefixing

---

- support contexts without a set of projects/project lists; can be used for eg:
  - **global contexts** (use `on_exit_manifest()` instead of `on_define_project()`/`on_define_project_set()`)
    - avoids nesting everything inside several top-level contexts
  - **decorators** (define `on_enter_context()` to set a state flag to true, and define `on_define_project()` and/or `on_define_project_set()` to check if the flag is true, and if so, set it to false then do whatever with the project/project set)
    - this avoids the need to wrap the project/project set in `{}`
  - **modes/imports/etc.** (define `on_enter_context()` to do something)
    - sets something at a given point
  - etc.

---

- Execute management commands against multiple projects, eg. `vcs for ...`

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
