# Todo - Unix
Mainly Linux/Mac

Tag Info (static for now)
================================================================================

/hardware

/store (hardware? alias: data)
  > store-host/attachment
/host (hardware? alias: proccess or proc)

data (store? path (optional)?) {
  /filesystem (alias: fs)
  /directory (alias: dir)
  /file
}

process-data (store? path?) {
  /project
  /package (project? version?)
  /install (package?)
  /config (package? installation (optional)?)
}

/environment (alias: env)
/command

proccess (host? install? config?) {
  /kernel
  /service (kernel? operations?)
  /operation (kernel? service (optional)?)

  content {
    /in/param
    /out/log

    /module (parent process?)
  }
}

idt (alias: identity-and-trust, iam, identity-and-access) {
  /user
  /group
}

/time

meta:
- DUP (duplicate)
- OLD (should no longer be used)

Commands
================================================================================

Hardware
====================

### hardware
- biosdecode  /host            - description of system's bios/uefi
- dmidecode   /host            - description of system's hardware components
- lspci       /host            - list PCI devices
- lsusb       /host            - list USB devices

Hosts, Kernels, and Processes
====================

### kernel
- uname       /kernal/package  - show system information
- arch        /kernel/package  - equivalent to `uname -m`
- lsb_release /kernal/package  - release info for 'standard linux base' (LSB)
- modprobe    /kernel/module   - add or remove (`-r`) modules from the linux kernel
- lsmod       /kernel/module   - list active modules in the running linux kernel
- insmod      /kernel/module   - insert a module into the running linux kernel
- rmmod       /kernel/module   - remove a module from the running linux kernel
- sysctl      /kernel/in/param - show and modify linux kernel parameters while the kernel is running
- dmesg       /kernel/out/log  - show the contents of the kernel message buffer

### boot and service
- service     /kernal, /service, /service/config, OLD - manage the system and services (don't use on systemd systems)
- systemctl   /kernel, /service, /service/config - manage the system and services (see: `systemctl --help`)
- journalctl  /kernel/log, /service/log - manage the systemd journal
- uptime      /kernel          - show how long the system has been running
- shutdown    /kernel          - shut down the system; alias for `systemctl shutdown`
- halt        /kernel          - halt the system; alias for `systemctl halt`
- poweroff    /kernel          - power off the system; alias for `systemctl poweroff`
- reboot      /kernel          - reboot the system; alias for `systemctl reboot`

### processes (services and operations)

#### show metadata
- ps          /process         - list info about processes
- ptree       /process         - show processes as a hierarchy [solaris only; `ps` can do this in linux]
- top         /process, interactive - interactive view of info about processes
- htop        /process, interactive - interactive view of info about processes
- pgrep       /process         - search for processes by name or other attributes

#### show resources
- fuser       /process, /file  - show info about (or kill) processes using files, filesystems, or ports/sockets
- lsof        /process, /file  - show open files of process(es) by name, user, etc. [mac, linux, bsd, and solaris only]
- pfiles      /process, /file  - show open files of a process by name, user, etc. [solaris only]
- pmap        /process         - show process memory data

#### signal
- kill        /process         - send SIGTERM or another signal to a given process
- killall     /process         - send SIGTERM or another signal to process(es) (by name, path, or other criteria)
- pkill       /process         - send signal to process (by name or other attributes)

#### create
- env         /process         - create process with modified environment (vars, cur dir, signals, etc.), or show environment
- nice        /process         - create process with modified scheduling priority
- chroot      /process, /environment - start a process with a special root directory

#### set attrs
- renice      /process         - set the scheduling priority of a running process

#### wait
- pidwait     /process         - wait on process searched for by name or other attributes

Identity and Trust
====================

### basic info
- finger      /user, OLD       - show info about a given user (reads `.plan` files where available)
- pinky       /user            - show info about a given user (reads `.plan` files where available ??)
- groups      /user, /group    - show groups that the current or a specified user is a member of
- id          /user, /group    - show UID of a user and GIDs of all groups that user is a member of)

### temporal info
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
- compress    /file, /dir      - compress (gzip?) file or all files in dir recursively (`-r`), adding `.Z` extension
- uncompress  /file            - uncompress (gzip?) file or all files in dir recursively (`-r`), removing `.Z` extension

### modify
- truncate    /file            - shrink or extend size of file (`-s [+-<>/%]INT([K,M,G,T,P,E,Z,Y][B])`)
- patch       /file            - apply a diff to a file
- tee         /file            - both write (overwrite or append) input to a file, and output the input unchanged

### copy
- cp          /file, /dir      - copy a file/dir (file-level)
- dd          /file, /dir      - copy (and convert) a file (or dir??) (stream-level)

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

installation
====================

### installations
- whereis     /installation - searches for binary, source, and man pages for a command
- which       /installation, /environment - show where a command's program is, based on the current $PATH

environment
====================

### terminal
- tty         /environment - return terminal name, eg. '/dev/tty4' (run on WSL)
- stty        /environment - get or set terminal options
- clear       /environment - clear the screen
- reset       /environment - reset terminal (see `tput`)
- tput        /environment - terminal-specific capabilities
  - [most of the user-level uses of this are covered by ncurses or ANSI codes]

### shell
- bg          /process, /environment - put a process into the background of a shell
- fg          /process, /environment - put a process into the foreground of a shell

### files and filesystem
- pwd         /environment - print working directory
- cd          /environment - change directory
- umask       /environment - set the file permissions mask (ie. excluded perms) for creating files

### environment variables
- export      /environment - make environment variable available to programs [sh and dirivatives]
- setenv      /environment - csh-style equivalent of the bash-style `export` [csh and dirivatives]
- [see /process - env]

### history
- history     /environment - output shell command history

### user
- whoami      /environment, /user         - show the username of the currently logged in user
- su          /environment, /user         - become root or another user (stands for 'super user')
- sudo        /environment, /user         - become root or another user to run a given command (stands for 'super user do')

command
====================

### show
- whatis      /command               - shows the one-line summary of a command
- type        /command, /environment - show how a command would be interpreted in the current environment
  - X is a shell keyword
  - X is a shell builtin
  - X is aliased to `Y'
  - X is a function
  - X is hashed (/path/to/X)
  - X is /path/to/X
  - -bash: type: X: not found

### create
- alias       /command, /environment - create an alias, or show aliases
- function    /command, /environment - create a shell function

### delete
- unalias     /command, /environment - remove an alias

Unknown Categorisation
================================================================================

### SELinux [?]
- sestatus    /config/security [?]           - get status of SELinux
- semanage    /config/security [?], /service - manage various things in SELinux
- getenforce  /config/security [?]           - print the current enforcement status of SELinux
- setenforce  /config/security [?]           - set the enforcement status of SELinux

Todo
================================================================================

environment
====================

read - [not really environment, but eh]
tmux - [terminal-related]

shells and commands
====================

- man - show usage manual for a given command

- sh   - the Bourne Shell (and other shells)
- bash - Bourne Again Shell
- zsh  - Z Shell
- ash  - Almquist Shell
- dash - Debian Almquist Shell
- ksh  - Korn Shell
- fish - Friendly Interactive Shell
- csh  - C Shell
- tcsh - TENEX C Shell
  - [and many others ...]

- xargs
- watch
- strace

time and scheduling
====================

## info
- date - show time and date, and do calculations with them
- cal  - show a calendar (arguments determine month/year, and other things)

## operations
- sleep   - wait for a given duration
- wait    - wait for process to exit
- time    - time a command's duration
- timeout - run command with a time limit

### commands
- batch   - batch schedule commands
- crontab - schedule command

text manipulation
====================

## producers
- echo   - print a given string
- printf - format and print a given string
- yes    - print a given string (or the word `yes` by default) repeatedly
- seq    - print a sequence of numbers

## processors

### specific
- tr       - translate all occurances of a given character to another character
- head     - output only the first N lines or characters of a file or stdin
- tail     - output only the last N lines or characters of a file or stdin
- sort     - sort the lines of the given file or stdin by various metrics
- tsort    - topological sort (ie. ordering nodes of a graph based on their deps)
- uniq     - filter out duplicate lines of the given file or stdin, or only output duplicate (-d) or unique (-u) lines
- wc       - count characters, words, or lines in the given file or stdin
- dirname  - output only the path leading up to the file or directory a path refers to
- basename - output only the name of the file or directory a path refers to

- cut      /operation - extract fields separated by a delimiter from each line of input
- expand   /operation - convert tabs to spaces
- unexpand /operation - convert spaces to tabs
- fold     /operation - line folding (wrapping) program
- join     /operation - joins lines of files on a common field (like SQL JOIN)
- fmt      /operation - formats text

### languages
- sed - text processing language (stands for 'stream editor')
- awk - text processing language

### hashing/checksums
- md5sum    /operation - create checksum of a file or stdin using md5
- sha1sum   /operation - create checksum of a file or stdin using sha1
- sha224sum /operation - create checksum of a file or stdin using sha224
- sha256sum /operation - create checksum of a file or stdin using sha256
- sha384sum /operation - create checksum of a file or stdin using sha384
- sha512sum /operation - create checksum of a file or stdin using sha512
- cksum     /operation - create checksum of and count bytes in a file

## viewers
- less
- more

## editors
- ed
- nano
- vi / vim
- emacs

expression languages
====================

- test   - evaluate an expression and returns 0 if true or 1 if false (alias: `[`)
- bc     - calculator (arbitrary precision)
- expr   - limited arithmetic and string expression evaluator [best to use bc]
- factor - factor numbers

misc
====================

- true  - return zero exit code
- false - return non-zero exit code
- fc    - fix command (shell builtin), used to quickly correct a previously entered command

networking
====================

## info
- hostname
- host
- netstat - show network connections, routing tables, interface statistics, masquerade connections, and multicast memberships

## configure
- ifconfig - show and modify network interface configuration
- ip       - show and modify network interface configuration (the newer version of `ifconfig`)
- iptables - configure firewall, routing, and NAT
- ufw      - uncomplicated firewall (show info and configure firewall)

## human-to-human communication
- talk  - single-system text chat
- write - single-system text chat (one line per message)

## test tools
- ping       - repeatedly send ICMP packets to a give host and output responses
- traceroute - try to find the sequence of hosts, including routers, that a packet goes through on its round trip to/from a given host

## remote shell
- ssh (alias: slogin) - secure shell
- rsh (alias: rlogin) - remote shell
- telnet              - remote shell

## file transfer
- ftp  - transfer files and directories using FTP
- sftp - transfer files and directories using SFTP (FTP + SSL/TLS)
- rcp  - remote file copy over RSH
- scp  - secure remote file copy over SSH
- wget - fetch a file from a remote resource over HTTP or HTTPS
- curl - fetch a file from a remote resource over HTTP or HTTPS

package management
====================

## packaging
- zip    - package and compress files and directories into zip (`.zip`) file
- unzip  - decompress and unpackage zip file
- gzip   - package and compress files and directories into gzip (`.gz`) file
- gunzip - decompress and unpackage gzip file

## managers
- dpkg
- apt
  - apt-get
  - apt-cache
- pacman
- yum
- rpm

version control
====================

- git - version control system
- svn - version control system

programming
====================

- cc / c99 / gcc - C compiler
- cflow - generate a C call graph
- fort77 - fortran compiler [!]
- make - follow steps to build an application

- lex - generate a lexer (I would suggest using a more modern one, like ANTLR4)
- yacc - generate a parser (I would suggest using a more modern one, like ANTLR4)

applications
====================

- lynx    ?, interactive - a CLI browser
- elm     ?, interactive - a CLI email system [not on WSL]
- webster ?       - a CLI dictionary lookup (uses the webster dictionary)

openers/runners
====================

- run-mailcap (and its aliases: view, see, edit, compose, print)

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
