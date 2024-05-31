# Todo - Unix
Mainly Linux/Mac

Tag Info (static for now)
================================================================================

**NOTE**: Should differentiate between what a thing *is* and what a thing *operates on*.

meta:
- DUP (duplicate)
- OLD (should no longer be used)

----------

```
/hardware

/store (hardware?)
  > store-host/attachment
/host (hardware?)

/transient-data {
  # Address of persistent-data
  /path

  # Address of process
  /command

  /text
  /number
  /time
}

/persistent-data (store? path?) {
  /host/image (project? version?)

  /filesystem (alias: fs)
  /directory (alias: dir)
  /file

  /project
  /package (project? version?)
  /installation (package? alias: install)
  /configuration (package? installation (optional)? alias: config)
}

/channel {
  /host/channel
  /process/channel
}

/proccess (host? installation? configuration? command? identity? alias: proc) {
  /kernel
  /service     (kernel? async operations?)
  /application (kernel? sync operations? alias: app)
  /operation   (kernel? service (optional)? alias: op)

  content {
    # subprocess that depends on and augments a parent process
    /module

    # per-process /configuration ('pushed in')
    /parameter (alias: param)
    # per-process context, like env vars, current dir, vfs root, etc. ('pulled in')
    /environment (alias: env)

    # current state (including status)
    /state
    # historical state
    /log

    # synchronous I/O (stdin/out/err, keyboard, mouse, etc.)
    /input
    /output
  }
}

/identity (alias: identity and trust, identity and access, iam) {
  /user
  /group
  /role
}
```

System Entities - Creation, Information, Management, and Destruction (CRUD)
================================================================================

**Notes**:
- Tags without a name represent the target entities of the command
- Unless overridden, all items are assumed to be `is: /operation`.

Hardware
====================

### hardware
- biosdecode  /hardware        - description of system's bios/uefi
- dmidecode   /hardware        - description of system's hardware components
- lspci       /hardware        - list PCI devices
- lsblk       /hardware        - list block devices
- lsusb       /hardware        - list USB devices

Storage, Filesystems, Directories, and Files
====================

### filesystem
- df          /filesystem      - show filesystem storage space, mounts, etc. info (stands for 'disk filesystem')
- fstyp       /filesystem      - show filesystem types [only available on some systems; can usually use `mount` for this]

- mkfs        /filesystem      - create a filesystem of the given type
- cryptsetup  /filesystem      - create and set up a LUKS encrypted filesystem

- growfs      /filesystem      - enlarge a ufs filesystem [bsd only]
- tune2fs     /filesystem      - adjust filesystem parameters [ext2/3/4]

- fsck        /filesystem      - check filesystem for errors and other issues, and attempt to fix them

- sync        /filesystem      - flush filesystem buffers

- mount       /filesystem      - show info about mounts of, mount, or unmount a filesystems
- umount      /filesystem      - unmount a filesystem

### storage space
- du          /file            - show file/dir storage space info (stands for 'disk usage')

### search
- grep        /file            - search for files containing patterns
- egrep       /file            - search for files containing patterns
- find        /file, /dir      - search for files by name/pattern, attributes, etc. or list files with filters
- ff          /file, /dir      - search for files by name (and others? anywhere on the system; stands for 'find files')

### show metadata
- ls          /file, /dir      - show file files in a directory and show file attributes
- file        /file, /dir      - show file/dir type
- stat        /file, /dir      - show inode metadata

### show content
- readlink    /file            - show symbolic link content
- cat         /file            - concatenate files and output results
- tac         /file            - cat, then reverses the order of the output [GNU only]
- zcat        /file            - show contents of gzip compressed file
- xzcat       /file            - show contents of xz compressed file
- bzcat       /file            - show contents of bzip compressed file
- zzcat       /file            - show contents of zip compressed file
  - [and a number of others]

- less        /file, is: /app  - view one or more files
- more        /file, is: /app  - view one or more files

## editors
- ed          /file, is: /app - edit one or more files
- nano        /file, is: /app - edit one or more files
- vi / vim    /file, is: /app - edit one or more files
- emacs       /file, is: /app - edit one or more files

### compare
- diff        /file, /dir      - compare files
- cmp         /file            - compare files byte-by-byte
- comm        /file            - compare sorted files for common/uncommon lines

### create
- mknod       /file            - create char/block device files & other special files
- mkdir       /dir             - create dir
- touch       /file            - create file (and set timestamps)
- ln          /file            - create symbolic link file
- mkfifo      /file            - create named pipe file

- ar          /file            - create an archive
- tar         /file            - create a tar archive
- zip         /file            - package and compress files/dirs into zip (`.zip`) file
- unzip       /file            - decompress and unpackage zip file
- gzip        /file            - package and compress files/dirs into gzip (`.gz`) file
- gunzip      /file            - decompress and unpackage gzip file
- compress    /file, /dir      - compress (gzip?) file or all files in dir recursively (`-r`), adding `.Z` extension
- uncompress  /file            - uncompress (gzip?) file or all files in dir recursively (`-r`), removing `.Z` extension

### modify
- truncate    /file            - shrink or extend size of file (`-s [+-<>/%]INT([K,M,G,T,P,E,Z,Y][B])`)
- patch       /file            - apply a diff to a file
- tee         /file            - both write (overwrite or append) input to a file, and output the input unchanged

### copy
- cp          /file, /dir      - copy a file/dir
- dd          /file, /dir      - copy (and convert) a file (or dir??) (as a stream)

- ftp         /file, /dir, /host/channel - transfer files/dirs to/from another host using FTP
- sftp        /file, /dir, /host/channel - transfer files/dirs to/from another host using SFTP (FTP + SSL/TLS)
- rcp         /file, /dir, /host/channel - transfer files/dirs to/from another host using RSH (stands for 'remote copy')
- scp         /file, /dir, /host/channel - transfer files/dirs to/from another host using SSH (stands for 'secure copy')
- wget        /file, /dir, /host/channel - fetch a file from another host using HTTP or HTTPS
- curl        /file, /dir, /host/channel - fetch a file from another host using HTTP or HTTPS

### move
- mv          /file, /dir      - move a file/dir

### set
- chown       /file, /dir      - set ownership of file/dir
- chgrp       /file, /dir      - set group ownership [use `chown` instead]
- chmod       /file, /dir      - set mode (ie. permissions) of file/dir

### delete
- rm          /file, /dir      - delete file/dir
- unlink      /file, /dir      - delete file/dir (lower-level version of `rm`) [use `rm` instead]
- rmdir       /dir             - delete an empty dir [use `rm` instead]
- shred       /file, /dir      - overwrite a file several times to hide its contents

### synchronise
- rsync       /file, /dir      - sync files/dirs (optionally over the network)

Packages and Installations
====================

### system package managers

#### global
- dpkg        /package, /installation - manage deb packages
- apt-get     /package, /installation - manage deb packages
- apt-cache   /package, /installation - manage the APT cache
- apt         /package, /installation - manage deb packages and the APT chache
- aptitute    /package, /installation - manage deb packages
- yum         /package, /installation - manage rpm packages
- rpm         /package, /installation - manage rpm packages
- pacman      /package, /installation - manage tar packages
- brew        /package, /installation - manage build scripts ('formulae') and binary packages ('bottles')

#### namespaced
- flatpak     /package, /installation - manage flatpack packages
- snap        /package, /installation - manage snap packages

### language package managers
- npm         /package, /installation - node and JS package manager
- yarn        /package, /installation - node and JS package manager
- pip         /package, /installation - python package manager
- cargo       /package, /installation - rust package manager
- gem         /package, /installation - ruby package manager
- composer    /package, /installation - PHP package manager
- maven       /package, /installation - Java package manager
- gradle      /package, /installation - Java package manager
- nuget       /package, /installation - .NET package manager

### environment managers
- conda       /package, /installation, /process/environment - multi-language package and environment manager

### host image managers
- docker      /host/image, /host - Docker container image and instance manager

### search
- whereis     /installation    - searches for binary, source, and man pages for a command
- which       /installation, /process/environment - show where a command's program is, based on the current $PATH

Commands
====================

### show
- whatis      /command, /process/environment - shows the one-line summary of a command
- type        /command, /process/environment - show how a command would be interpreted in the current environment
  - X is a shell keyword
  - X is a shell builtin
  - X is aliased to `Y'
  - X is a function
  - X is hashed (/path/to/X)
  - X is /path/to/X
  - -bash: type: X: not found

- man         /command, /process/environment - show usage manual for a given command

### create
- alias       /command         - create a command alias, or show aliases
- function    /command         - create a shell function

### delete
- unalias     /command         - remove an alias

Hosts, Kernels, and Processes
====================

### kernel
- uname       /kernel/package  - show system information
- arch        /kernel/package  - equivalent to `uname -m`
- lsb_release /kernel/package  - release info for 'standard linux base' (LSB)
- modprobe    /kernel/module   - add or remove (`-r`) modules from the linux kernel
- lsmod       /kernel/module   - list active modules in the running linux kernel
- insmod      /kernel/module   - insert a module into the running linux kernel
- rmmod       /kernel/module   - remove a module from the running linux kernel
- sysctl      /kernel/param    - show and modify linux kernel parameters while the kernel is running
- dmesg       /kernel/log      - show the contents of the kernel message buffer

### boot and service
- service     /kernel, /service, /service/config, OLD - manage the system and services (don't use on systemd systems)
- systemctl   /kernel, /service, /service/config - manage the system and services (see: `systemctl --help`)
- journalctl  /kernel/log, /service/log - manage the systemd journal
- uptime      /kernel          - show how long the system has been running
- shutdown    /kernel          - shut down the system; alias for `systemctl shutdown`
- halt        /kernel          - halt the system; alias for `systemctl halt`
- poweroff    /kernel          - power off the system; alias for `systemctl poweroff`
- reboot      /kernel          - reboot the system; alias for `systemctl reboot`

### names and addresses
- hostname    /host            - show hostname of current host
- host        /host            - resolve DNS records of given hostname

### services and operations

#### show metadata
- ps          /process         - list info about processes
- ptree       /process         - show processes as a hierarchy [solaris only; `ps` can do this in linux]
- top         /process, is: /app - interactive view of info about processes
- htop        /process, is: /app - interactive view of info about processes
- pgrep       /process         - search for processes by name or other attributes

#### show resources
- fuser       /process, /filesystem, /file  - show info about (or kill) processes using files, filesystems, or ports/sockets
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
- open        /process, /file, /dir, /web-resource - open file or uri with associated app [Mac only?]

#### signal
- kill        /process         - send SIGTERM or another signal to a given process
- killall     /process         - send SIGTERM or another signal to process(es) (by name, path, or other criteria)
- pkill       /process         - send signal to process (by name or other attributes)

#### set attrs
- renice      /process         - set the scheduling priority of a running process

#### wait
- wait        /process/state   - wait for process to exit (ie. reach the stopped state)
- pidwait     /process/state   - wait on process searched for by name or other attributes

Process Environment
====================

### terminal
- tty         /process/environment - return terminal name, eg. '/dev/tty4' (run on WSL)
- stty        /process/environment - get or set terminal options
- clear       /process/environment - clear the screen
- reset       /process/environment - reset terminal (see `tput`)
- tput        /process/environment - terminal-specific capabilities
  - [most of the user-level uses of this are covered by ncurses or ANSI codes]

### shell
- bg          /process/environment - resume a process in the background of a shell
- fg          /process/environment - put a process into the foreground of a shell

### files and filesystem
- pwd         /process/environment - print working directory
- cd          /process/environment - change directory
- umask       /process/environment - set the file permissions mask (ie. excluded perms) for creating files

### environment variables
- export      /process/environment - make environment variable available to programs [sh and dirivatives]
- setenv      /process/environment - csh-style equivalent of the bash-style `export` [csh and dirivatives]
- [see /process - env]

Applications
====================

### shells
@tags (
  /command,             # Can interpolate commands
  /process,             # Can start processes
  /process/environment, # Can view and modify its environment (eg. vars, cd, chroot, etc.)
  /process/parameter,   # Can modify its parameters (shopt), and set those of processes
  /process/input,       # Can set (via redirect, pipes, command substitution, etc.) the input of created processes
  /process/output,      # Can redirect the output of created processes
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

- read        /app/input       - reads user input from a shell and stores it in a variable
- tmux        /app/input       - terminal multiplexer

- fc          /app/input, /app/log - fix command (shell builtin), used to quickly correct a previously entered command
- history     /app/input, /app/log - output shell command history

### other apps
- lynx        /web-resource, is: /app - a CLI browser
- elm         /email, is: /app - a CLI email system [not on WSL by default]
- webster     /word            - a CLI dictionary lookup (uses the webster dictionary)

Channels
====================

### show configuration
- netstat     /channel/config, /host/channel - show network connections, routing tables, interface statistics, masquerade connections, and multicast memberships

### configuration
- ifconfig    /channel/config  - show and modify network interface configuration
- ip          /channel/config  - show and modify network interface configuration (the newer version of `ifconfig`)
- iptables    /channel/config  - configure firewall, routing, and NAT
- ufw         /channel/config  - show info about and configure the 'uncomplicated firewall'

### discovery
- ping        /host/channel    - repeatedly send ICMP packets to a given host and output responses
- traceroute  /host/channel    - try to find the sequence of hosts, including routers, that a packet goes through on its round trip to/from a given host

## human-to-human
- talk        /process/channel - single-system text chat
- write       /process/channel - single-system text chat (one line per message)

Identity and Trust
====================

### basic info
- finger      /user, OLD       - show info about a given user (reads `.plan` files where available)
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
- sed         /text - text processing language (stands for 'stream editor')
- awk         /text - text processing language

### hashing/checksums
- md5sum      /text - create checksum of a file or stdin using md5
- sha1sum     /text - create checksum of a file or stdin using sha1
- sha224sum   /text - create checksum of a file or stdin using sha224
- sha256sum   /text - create checksum of a file or stdin using sha256
- sha384sum   /text - create checksum of a file or stdin using sha384
- sha512sum   /text - create checksum of a file or stdin using sha512
- cksum       /text - create checksum of and count bytes in a file

Numbers
====================

### expression languages
- test        /expression - evaluate an expression and returns 0 if true or 1 if false (alias: `[`)
- bc          /expression - calculator (arbitrary precision)
- expr        /expression - limited arithmetic and string expression evaluator [best to use bc]
- factor      /expression - factor numbers

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
