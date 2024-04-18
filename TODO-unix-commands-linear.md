# Todo - Unix
Mainly Linux/Mac

Notes
==================================================

aliases:
- boot = kernel/run
- process = command/run

technically:
- `kernel` is a type of `service` is a type of `program`
- but also, `program` depends on `service` depends on `kernel`

Tag Info (static for now)
==================================================

object:
- hardware (the system's hardware)
- kernel (the system's kernel)
- boot (an instance of the system's kernel)
- service (a process that provides functionality while active)

actions:
- data      - info, set, add, remove
- processes - start, restart, stop
- messages  - send, receive

meta:
- DUP (duplicate)
- OLD (should no longer be used)

Commands
==================================================

### hardware
- `biosdecode`  (hardware: info)              - description of system's bios/uefi
- `dmidecode`   (hardware: info)              - description of system's hardware components
- `lspci`       (hardware: info)              - list PCI devices
- `lsusb`       (hardware: info)              - list USB devices

### kernel
- `uname`       (kernel/package: info)        - show system information
- `arch`        (kernel/package: info, DUP)   - equivalent to `uname -m`
- `lsb_release` (kernel/package: info)        - release info for 'standard linux base' (LSB)
- `dmesg`       (kernel/run/log: info)        - show the contents of the kernel message buffer
- `sysctl`      (kernel/run/parameter: info,
                 kernel/run/parameter: set)   - show and modify linux kernel parameters while the kernel is running
- `modprobe`    (kernel/run/module: info,
                 kernel/run/module: add,
                 kernel/run/module: remove)   - add or remove (-r) modules from the linux kernel
- `lsmod`       (kernel/run/module: info)     - list active modules in the running linux kernel
- `insmod`      (kernel/run/module: add)      - insert a module into the running linux kernel
- `rmmod`       (kernel/run/module: remove)   - remove a module from the running linux kernel

### boot and service
- `service`     (service/run: info,
                 service/run: start,
                 service/run: restart,
                 service/run: stop,
                 OLD)                         - manage the system and services (don't use on systemd systems)
- `journalctl`  (kernel/run: log,
                 service/run: log)            - manage the systemd journal
- `uptime`      (kernel/run: info)            - show how long the system has been running
- `systemctl`   (kernel/run: ?,
                 service: ?,
                 service/run: ?)              - manage the system and services (see: `systemctl --help`)
- `shutdown`    (kernel/run: stop)            - shut down the system; alias for `systemctl shutdown`
- `halt`        (kernel/run: stop)            - halt the system; alias for `systemctl halt`
- `poweroff`    (kernel/run: stop)            - power off the system; alias for `systemctl poweroff`
- `reboot`      (kernel/run: restart)         - reboot the system; alias for `systemctl reboot`

### SELinux [?]
- `sestatus`    (system/security: ?)          - get status of SELinux
- `semanage`    (system/security: ?)          - manage various things in SELinux
- `getenforce`  (system/security: ?)          - print the current enforcement status of SELinux
- `setenforce`  (system/security: ?)          - set the enforcement status of SELinux

### users and groups
- `finger`      (user: info, OLD)             - show info about a given user (reads `.plan` files where available)
- `pinky`       (user: info)                  - show info about a given user (reads `.plan` files where available ??)
- `groups`      (user: info,
                 group: info)                 - show groups that the current or a specified user is a member of
- `id`          (user: info,
                 group: info)                 - show UID of a user and GIDs of all groups that user is a member of)

- `last`        (user{dyn}: info)             - show last login time of a user, eg. `last --fullnames --fulltimes --system --dns`
- `users`       (user{dyn}: info)             - show names of users currently logged on (on that host)
- `who`         (user{dyn}: info)             - show info about who's logged on, including the connection source address
- `w`           (user{dyn}: info)             - show info about who's logged on, including what they're currently running

- `groupadd`    (group: create)               - ?
- `useradd`     (user: create)                - ?
- `adduser`     (user: create)                - ?
- `passwd`      (user/password: set)          - change a user's password (usually your own)

- `visudo`      (user/perms: set,
                 file: edit)                  - safely modify the sudoers file

## program runs (ie. processes)
- `ps`          (program/run: info)           - list info about processes
- `ptree`       (program/run: info,
                 DUP)                         - show processes as a hierarchy (solaris only - `ps` can do this in linux)
- `top`         (program/run: info,
                 interactive)                 - interactive view of info about processes
- `htop`        (program/run: info,
                 interactive)                 - interactive view of info about processes

- `kill`        (program/run: send)           - send SIGTERM, or another signal, to a given process
- `killall`     (program/run: send)           - send SIGTERM, or another signal, to zero or more processes (by name, path, or other criteria)

filesystems
====================

## info

### general
- `du` - show disk usage info (can filter by file or directory)
- `df` - show filesystem usage info (can filter by file or directory)

### specific
- `ls` - list files
- `find` (search) - find file
- `ff` (search) - 'find files' (anywhere on the system)

## modify

### general
- `mount` - show and modify mounted filesystems
  - `fstyp` - show filesystem types (only available on some systems, can usually use `mount` for this too)
- `umount` - unmount a mounted filesystem

### specific
- mkdir - create directory
- chown - set ownership of file or directory
  - chgrp (unused) - change group ownership [an use `chown`]
- chmod - set mode (permissions) of file or directory

files
====================

## info

### show
- cat - concatenate files and output results
- tac (GNU) - cat, then reverses the order of the output
- zcat - show contents of gzip compressed file
- xzcat - show contents of xz compressed file
- bzcat - show contents of bzip compressed file
- zzcat - show contents of zip compressed file
- ... and a number of others

### search
- grep
- egrep

### compare
- diff - compare files
- cmp - compare files byte-by-byte
- comm - compare sorted files

## modify
- ln
- touch
- cp - copy a file (file-level)
- dd - convert and copy a file (stream-level)
- mv
- rm - remove file or directory
  - unlink (unused) - lower-level version of `rm`
  - rmdir (unused) - remove an empty directory (can use `rm` instead)
- ar - create an archive
- tar - create a tar archive
- rsync (network) - synchronise directories (optionally over the network)

shells and commands
====================

## info
- man - show usage manual for a given command

### shells
- sh - the Bourne Shell (and other shells)
- bash - Bourne Again Shell
- zsh - Z Shell
- ash - Almquist Shell
- dash - Debian Almquist Shell
- ksh - Korn Shell
- fish - Friendly Interactive Shell
- csh - C Shell
- tcsh - TENEX C Shell
- ... etc.

### wrapper commands
- xargs

networking
====================

## info
- hostname
- netstat - show network connections, routing tables, interface statistics, masquerade connections, and multicast memberships

## configure
- ifconfig - show and modify network interface configuration
- ip - show and modify network interface configuration (the newer version of `ifconfig`)
- iptables - configure firewall, routing, and NAT
- ufw - uncomplicated firewall (show info and configure firewall)

## human-to-human communication
- talk - single-system text chat
- write - single-system text chat (one line per message)

## test tools
- ping - repeatedly send ICMP packets to a give host and output responses
- traceroute - try to find the sequence of hosts, including routers, that a packet goes through on its round trip to/from a given host

## remote shell
- ssh (alias: slogin) - secure shell
- rsh (alias: rlogin) - remote shell
- telnet - remote shell

## file transfer
- ftp - transfer files and directories using FTP
- sftp - transfer files and directories using SFTP (FTP + SSL/TLS)
- rcp - remote file copy over RSH
- scp - secure remote file copy over SSH
- wget - fetch a file from a remote resource over HTTP or HTTPS
- curl - fetch a file from a remote resource over HTTP or HTTPS

package management
====================

## packaging
- zip - package and compress files and directories into zip (`.zip`) file
- unzip - decompress and unpackage zip file
- gzip - package and compress files and directories into gzip (`.gz`) file
- gunzip - decompress and unpackage gzip file

## managers
- dpkg
- apt
  - apt-get
  - apt-cache
- pacman
- yum
- rpm

time and scheduling
====================

## info
- date - show time and date, and do calculations with them
- cal - show a calendar (arguments determine month/year, and other things)

## operations
- sleep - wait for a given duration
- wait - wait for process to exit
- time - time a command's duration
- timeout - run command with a time limit

text manipulation
====================

## producers
- echo - print a given string
- printf - format and print a given string
- yes - print a given string (or the word `yes` by default) repeatedly
- seq - print a sequence of numbers

## processors

### specific
- tr - translate all occurances of a given character to another character
- head - output only the first N lines or characters of a file or stdin
- tail - output only the last N lines or characters of a file or stdin
- sort - sort the lines of the given file or stdin by various metrics
- tsort - topological sort (ie. ordering nodes of a graph based on their deps)
- uniq [-u] - filter out duplicate lines of the given file or stdin, or only output unique lines (with -u)
- wc - count characters, words, or lines in the given file or stdin
- dirname - output only the path leading up to the file or directory a path refers to
- basename - output only the name of the file or directory a path refers to

### general
- sed
- awk

## viewers
- less
- more

## editors
- ed
- nano
- vi / vim
- emacs

environment
====================

## info
- pwd - print working directory
- history - output shell command history
- which - show where a command's program is
- whereis - searches for binary, source, and man pages for a command
- whatis - shows the one-line summary of a command
- type - show how a command would be interpreted
  - X is a shell keyword
  - X is a shell builtin
  - X is aliased to `Y'
  - X is a function
  - X is hashed (/path/to/X)
  - X is /path/to/X
  - -bash: type: X: not found

- `whoami`      (env/user: info)              - show the username of the currently logged in user
- `su`          (env/user: set)               - become the superuser or another user
- `sudo`        (env/user: set)               - become the superuser or another user temporarily while executing a given command

## modify
- cd - change directory
  - options?
- clear - clear the screen
- export - make environment variable available to programs
  - setenv (csh, unused) - csh-style equivalent of the bash-style `export`
- alias - show aliases (without args) or define an alias
- unalias - remove an alias
- function - define a shell function

misc
====================

- lynx - a CLI browser
- elm - a CLI email system
- webster - a CLI dictionary lookup (uses the webster dictionary)

Temp
==================================================

### processes
nice - process priority
renice
pmap - process mem usage
pfiles (solaris only) - process open files
lsof - list open files

### filesystems
fsck
growfs
tune2fs [ext2/3]
mkfs
cryptsetup - LUKS encrypted FS setup
sync - flush FS buffers

### files
readlink

mkfifo - create named pipe file
mknod - create char/block device files & other special files
tee

file - determine file type
stat - print data about an inode

comm - show common/uncommon lines from two sorted files

compress / uncompress
patch
truncate [-s size] - shrink or extend size of file
  - size : [+-<>/%]INT([K,M,G,T,P,E,Z,Y][B])
shred - overwrite a file several times to hide its contents

### environment
read
env
bg / fg - background/foreground a process
tput / reset - terminal-specific capabilities
  - Note: most of the user-level uses of this are covered by ncurses or ANSI codes
umask
tmux
chroot

tty - return terminal name, eg. '/dev/tty4' (run on WSL)
stty - get or set terminal options

### scheduling
batch - batch schedule commands
crontab - schedule command

### utils
test / [ - evaluate an expression and returns 0 if true or 1 if false
bc - calculator (arbitrary precision)
expr - limited arithmetic and string expression evaluator [best to use bc]
factor - factor numbers

### programming
cc / c99 / gcc - C compiler
cflow - generate a C call graph
fort77 - fortran compiler [!]
make - follow steps to build an application

lex - generate a lexer (I would suggest using a more modern one, like ANTLR4)
yacc - generate a parser (I would suggest using a more modern one, like ANTLR4)

### version control
git - version control system
svn - version control system

### text processing
cut
expand / unexpand - convert tabs to spaces and vice versa
fold - line folding (wrapping) program
join - joins lines of files on a common field (like SQL JOIN)
fmt - formats text

### running standard actions based on file type
- run-mailcap (and its aliases: view, see, edit, compose, print)

### user-to-file/fs/blk relationships
fuser [--mount] - show users using given files, filesystems, or block devices

### misc
false / true - commands that do nothing, but return non-zero and zero, respectively
fc - fix command (shell builtin), used to quickly correct a previously entered command

### hashing
`md5sum`
`sha1sum`
`sha224sum`
`sha256sum`
`sha384sum`
`sha512sum`
`cksum` - generate checksum of and count bytes in a file

Archaic and Unknown
==================================================

- unman - ???
- ncftp - 'anonymous ftp'
- quota - manage disk quotas

printing to a physical printer:
- lpr - 'line printer'
- lpq - 'line printer queue'
- lprm jobnum - 'line printer remove'
- lp - sometimes an alias to lpr or vice versa

Refs
==================================================

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
