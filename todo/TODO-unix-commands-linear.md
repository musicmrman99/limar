# Todo - Unix
Mainly Linux/Mac

System Entities - Creation, Information, Management, and Destruction (CRUD)
================================================================================

Hosts, Kernels, and Processes
====================

### services and operations

#### show metadata
- ps          /process         - list info about processes
- ptree       /process         - show processes as a hierarchy [solaris only; `ps` can do this in linux]
- top         /process, is: /app - interactive view of info about processes
- htop        /process, is: /app - interactive view of info about processes
- pgrep       /process         - search for processes by name or other attributes

#### show resources
- fuser       /process, /filesystem, /file - show info about (or kill) processes using files, filesystems, or ports/sockets
- lsof        /process, /file  - show open files of process(es) by name, user, etc. [mac, linux, bsd, and solaris only]
- pfiles      /process, /file  - show open files of a process by name, user, etc. [solaris only]
- pmap        /process         - show process's raw memory

#### create
- env         /process, /process/environment - create process with modified environment (vars, cur dir, signals, etc.), or show environment
- chroot      /process, /process/environment - create a process with a special root directory
- nice        /process, /process/parameter - create process with modified scheduling priority

- strace      /process         - runs a command in trace mode, providing detailed output of system calls
- watch       /process         - runs a command periodically, replacing the output of previous runs
- xargs       /process, /command - create processes from commands interpolated using each line of its input

- time        /process, /time  - create a process and time how long it takes
- timeout     /process, /time  - create a process then wait until it's finished or for set duration, whichever comes first

- at          /process, /time  - set a process to be created at a particular time
- atq         /process, /time  - view the outstanding jobs added by 'at'
- atrm        /process, /time  - remove an outstanding job added by 'at'
- batch       /process, /time  - schedule process(es) to be created when resources are available
- crontab     /process, /time  - manage when a process is scheduled to be created

#### openers
- run-mailcap /process, /file  - open file with configured app for category
- view        /process, /file  - open file with configured app for category [run-mailcap w/ default action]
- see         /process, /file  - open file with configured app for category [run-mailcap w/ default action]
- edit        /process, /file  - open file with configured app for category [run-mailcap w/ default action]
- compose     /process, /file  - open file with configured app for category [run-mailcap w/ default action]
- print       /process, /file  - open file with configured app for category [run-mailcap w/ default action]
- open        /process, /file, /dir, /url - open file or uri with associated app [Mac only?]

#### signal
- kill        /process         - send SIGTERM or another signal to a given process
- killall     /process         - send SIGTERM or another signal to process(es) (by name, path, or other criteria)
- pkill       /process         - send signal to process (by name or other attributes)

#### set attrs
- renice      /process         - set the scheduling priority of a running process

#### wait
- wait        /process/state   - wait for process to exit (ie. reach the stopped state)
- pidwait     /process/state   - wait on process searched for by name or other attributes

Applications
====================

### shells
@tags (
  /command,             # Can interpolate commands
  /process,             # Can start processes
  /process/environment, # Can view and modify its environment (eg. vars, cd, chroot, etc.)
  /process/parameter,   # Can modify its parameters (shopt), and set those of processes
  /process/channel,     # Can set (via redirect, pipes, command substitution, etc.) the input and redirect the output of created processes
  /process/state,       # Can determine the status of processes it started (ie. if still blocking, or job status)
  is: /app
) {
- sh                           - the Bourne Shell (and other shells)
- bash                         - Bourne Again Shell
- zsh                          - Z Shell
- ash                          - Almquist Shell
- dash                         - Debian Almquist Shell
- ksh                          - Korn Shell
- fish                         - Friendly Interactive Shell
- csh                          - C Shell
- tcsh                         - TENEX C Shell
  - [and many others ...]

- ssh         /host            - secure shell (alias: `slogin`)
- rsh         /host            - remote shell (alias: `rlogin`)
- telnet      /host            - remote shell
}

- read        /process/channel - reads user input from a shell and stores it in a variable
- tmux        /process/channel - terminal multiplexer

- fc          /process/channel, /process/log - fix command (shell builtin), used to quickly correct a previously entered command
- history     /process/channel, /process/log - output shell command history

### other apps
- lynx        /url, is: /app   - a CLI browser
- elm         /email, is: /app - a CLI email system [not on WSL by default]
- webster     /word            - a CLI dictionary lookup (uses the webster dictionary)

Channels
====================

### show configuration
- netstat     /host/channel, /host/channel/config - show network connections, routing tables, interface statistics, masquerade connections, and multicast memberships

### configuration
- ifconfig    /host/channel/config  - show and modify network interface configuration
- ip          /host/channel/config  - show and modify network interface configuration (the newer version of `ifconfig`)
- iptables    /host/channel/config  - configure firewall, routing, and NAT
- ufw         /host/channel/config  - show info about and configure the 'uncomplicated firewall'

### discovery
- ping        /host/channel    - repeatedly send ICMP packets to a given host and output responses
- traceroute  /host/channel    - try to find the sequence of hosts, including routers, that a packet goes through on its round trip to/from a given host

## human-to-human
- talk        /process/channel - single-system text chat
- write       /process/channel - single-system text chat (one line per message)

Identity and Trust
====================

### basic info
- finger      /user, __OLD     - show info about a given user (reads `.plan` files where available)
- pinky       /user            - show info about a given user (reads `.plan` files where available ??)
- groups      /user, /group    - show groups that the current or a specified user is a member of
- id          /user, /group    - show UID of a user and GIDs of all groups that user is a member of)

### contextual info
- whoami      /process/user    - show the username of the currently logged in user
- last        /user            - show last login time of a user, eg. `last --fullnames --fulltimes --system --dns`
- users       /user            - show names of users currently logged on (on that host)
- who         /user            - show info about who's logged on, including the connection source address
- w           /user            - show info about who's logged on, including what they're currently running

### management
- groupadd    /group           - create a group
- useradd     /user            - create a user
- adduser     /user            - create a user
- passwd      /user            - set a user's password (usually your own)
- visudo      /user, /operation/config - safely modify the sudoers file

### switch
- su          /process/user    - become root or another user (stands for 'super user')
- sudo        /process/user    - become root or another user to run a given command (stands for 'super user do')

Data Entities - Producers and Processors
================================================================================

Paths
====================

### path processors
- dirname     /path            - output only the path leading up to the file or directory a path refers to
- basename    /path            - output only the name of the file or directory a path refers to

Process State
====================

### status code producers
- true        /operation/state - return zero exit code
- false       /operation/state - return non-zero exit code

Text
====================

### producers
- echo        /text            - print a given string
- printf      /text            - format and print a given string
- yes         /text            - print a given string (or the word `yes` by default) repeatedly
- seq         /text            - print a sequence of numbers

### character level processors
- tr          /text            - translate all occurances of a given character to another character
- expand      /text            - convert tabs to spaces
- unexpand    /text            - convert spaces to tabs

### within-line level processors
- cut         /text            - extract fields separated by a delimiter from each line of input
- fold        /text            - line folding (wrapping) program
- join        /text            - joins lines of files on a common field (like SQL JOIN)
- fmt         /text            - formats text

### whole-line level processors
- head        /text            - output only the first N lines or characters of a file or stdin
- tail        /text            - output only the last N lines or characters of a file or stdin
- sort        /text            - sort the lines of the given file or stdin by various metrics
- tsort       /text            - topological sort (ie. ordering nodes of a graph based on their deps)
- uniq        /text            - deduplicate, keep only duplicate (-d), or discard duplicate (-u) consecutive lines
- wc          /text            - count characters, words, or lines in the given file or stdin

### processor languages
- sed         /text            - text processing language (stands for 'stream editor')
- awk         /text            - text processing language

### hashing/checksums
- md5sum      /text            - create checksum of a file or stdin using md5
- sha1sum     /text            - create checksum of a file or stdin using sha1
- sha224sum   /text            - create checksum of a file or stdin using sha224
- sha256sum   /text            - create checksum of a file or stdin using sha256
- sha384sum   /text            - create checksum of a file or stdin using sha384
- sha512sum   /text            - create checksum of a file or stdin using sha512
- cksum       /text            - create checksum of and count bytes in a file

Numbers
====================

### expression languages
- test        /expression      - evaluate an expression and returns 0 if true or 1 if false (alias: `[`)
- bc          /expression      - calculator (arbitrary precision)
- expr        /expression      - limited arithmetic and string expression evaluator [best to use bc]
- factor      /expression      - factor numbers

Time
====================

### time/date
- date        /time            - show time and date, and do calculations with them
- cal         /time            - show a calendar (arguments determine month/year, and other things)

### wait for time
- sleep       /time            - wait for a given duration

Unknown Categorisation
================================================================================

### Programming

Should these be moved into their own manifest, or merged with other build tools, eg. maven (which is currently categorised as a package manager)?

- cc / c99 / gcc - C compiler
- cflow - generate a C call graph
- fort77 - fortran compiler [!]
- make - follow steps to build an application

- lex - generate a lexer (I would suggest using a more modern one, like ANTLR4)
- yacc - generate a parser (I would suggest using a more modern one, like ANTLR4)

### SELinux [?]
- sestatus    /config/security [?]           - get status of SELinux
- semanage    /config/security [?], /service - manage various things in SELinux
- getenforce  /config/security [?]           - print the current enforcement status of SELinux
- setenforce  /config/security [?]           - set the enforcement status of SELinux

Archaic and Unknown
================================================================================

- unman - ???
- ncftp - 'anonymous ftp'
- quota - manage disk quotas

printing to a physical printer:
- lpr - 'line printer'
- lpq - 'line printer queue'
- lprm jobnum - 'line printer remove'
- lp - sometimes an alias to lpr or vice versa

Refs
================================================================================

- https://www.digitalocean.com/community/tutorials/linux-commands
- https://www.math.utah.edu/lab/unix/unix-commands.html
- https://mally.stanford.edu/~sr/computing/basic-unix.html
- https://www.unixtutorial.org/basic-unix-commands
- https://www.unixtutorial.org/advanced-unix-commands
- https://www.unixtutorial.org/reference
- https://www.unixtutorial.org/linux-commands
- https://www.cmu.edu/computing/services/comm-collab/collaboration/afs/how-to/unix-commands.pdf
- https://en.wikipedia.org/wiki/List_of_POSIX_commands
- https://en.wikipedia.org/wiki/List_of_GNU_Core_Utilities_commands
