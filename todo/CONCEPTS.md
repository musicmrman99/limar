# Concepts

## Subjects and Providers

A **subject** is anything you may want to know about or manipulate using `limar`, such as:

- Projects
- Project Sets

- Sources (source code, assets, etc.)
- Artifacts (binaries, archives/packages, bundles, etc.)
- Deployments (instances of a piece of software)
- Configurations (parameter bindings for a given deployment)

- Changes (file history, tagged versions, tasks, (the act of) deployments, etc.)
- Quality (tests, validity, integrity, 7 Cs, etc.)
- Knowledge (comments, documentation strings, readmes, licencing, design information and visualisations, etc.)

A **provider** is a module that adds the ability to view, modify, and otherwise
manipulate one or more subjects using a specific tool. For example, the `git`
provider adds various commands for manipulating git repositories, mainly within
the `changes` subject.

---

Check Areas of Competence for anything else I might have missed

- ./ IDEs (Deployment of the IDE)
- ./ local-only configs
- ./ dependencies and their managers (deps are Artifacts, their managers are Deployments of the manager / tools)
- ./ builds
- ./ secrets (a form of configuration)
- test outputs
- runtime outputs - ./configs, ? logs, ? output files

## Aspects of Quality (the 7 Cs)

- correctness (ie. validity, discovered by testing, validation, monitoring, alerting)
- comprehensiveness
- consistency
- coherence (ie. utility)
- conciseness
- clarity (also aids Knowledge)
- completeness (eg. is it releasable?)

## Software Engineering Common Tasks

- docs generation
- validation, tests (inc. performance)
- infrastructure, pipelines, monitoring/alerting
- ID+T, certs
- docker
- machine image builds

- data manipulation (`tr`)

## Areas of SE

- Binding Time, and associated actions/interests:
  - standards (generic component of target)
  - design (target)
  - delivery (implementation)
  - support (runtime)
  - evaluation (cycle)

- System:
  - Context ()
  - Information (things)
  - Action (changes)

- Considerations for Digital Systems (ie. inner/static system)
  - All systems
    - infrastructure and deployment (what services run on, and how they are deployed)
    - communication (inc. networking, remote API calls, messaging, events, notification)
    - security and compliance (CIA triad and legal/ethical aspects, inc. ID&T/IAM (inc. authn/authz), encryption (in transit, at rest), GDPR, change approvals)
    - validation (inc. of code (ie. testing), data)
    - performance (inc. caching, scaling up and down, financial management)
    - failure management (inc. detection, handling, storage, recovery)
    - monitoring and alerting (inc. audit, logging, instrumentation, tracing (ie. request/event tracing through many systems), runtime intelligence (ie. usage, patterns, analytics, visualisation, etc.), what/where/how)
    - presentation and interaction (inc. data formats, learnability, UI/UX; of both the system itself and its supporting systems)

  - Some systems
    - discovery (inc. of systems, services, available data)
    - configuration management (esp. in microservices)
    - transaction management (inc. distributed agreement, ACID-ity)
    - localisation (inc. natural language translation)

- Considerations for Human Systems (ie. outer/cyclic system)
  - who (Person, Group, Organisation, etc.)
  - what (the definitions of System things, eg. code, IaC, data, etc.)
  - where (physical and digital spaces)
  - when (the concept of Time, as it relates to both Tasks and Binding Time)
  - why (context & purpose, documentation, etc.)
  - how (processes, learnability)

  - agility (reacting to changes of context)
    - Software design principles - YAGNI, SOLID, DRY, UX principles

  - value = benefit - cost
    - often, benefit and cost aren't even in the same units, so cannot be straightforwardly subtracted
    - the reality will be based on context (eg. what's important to you) and intuation

    - should LIMAR even try to 'informationalise' value?
      - is that what LIMAR is in the first place?

### References

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
