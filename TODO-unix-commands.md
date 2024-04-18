system and services
====================

## info
- uname - show system information
  - arch - equivalent to `uname -m`
- lsb_release - release info for 'standard linux base' (LSB)
- lspci - list PCI devices
- lsusb - list USB devices
- dmidecode - description of system's hardware components
- biosdecode - description of system's bios/uefi
- dmesg - show the contents of the kernel message buffer
- uptime - show how long the system has been running

## management

### kernel
- sysctl - show and modify linux kernel parameters while the kernel is running
- modprobe [-r] - add and remove modules from the linux kernel
- lsmod - list active modules in the running linux kernel
- insmod - insert a module into the running linux kernel
- rmmod - remove a module from the running linux kernel

### general and services
- service - manage the system and services (older; don't use if running on systemd)
- systemctl - manage the system and services; aliases for `systemctl ...`:
  - shutdown - shut down the system
  - halt - halt the system
  - poweroff - power off the system
  - reboot - reboot the system
- journalctl - manage the systemd journal

security
====================

- sestatus - get status of SELinux
- semanage - manage various things in SELinux
- getenforce - print the current enforcement status of SELinux
- setenforce - set the enforcement status of SELinux

users and groups
====================

## info
- whoami - show the username of the currently logged in user
- finger / pinky - show info about a given user (reads `.plan` files where available)
- last [-l username] - show last login time of a user
  - eg. `last --fullnames --fulltimes --system --dns`
- groups - show groups that the current or a specified user is a member of
- id - show UID of a user and GIDs of all groups that user is a member of)
- users - show names of users currently logged on (on that host)
- who - show info about who's logged on, including the connection source address
- w - show info about who's logged on, including what they're currently running

## modify
- su - become the superuser or another user
- sudo - become the superuser or another user temporarily while executing a given command
- visudo - safely modify the sudoers file

processes
====================

## info
- ps - list info about processes
  - ptree - show processes as a hierarchy (solaris only - ps can do this in linux)
- top - interactive view of info about processes
- htop - interactive view of info about processes

## modify
- kill - send the SIGTERM signal, or another signal, to a given process
- killall

filesystems
====================

## info

### general
- du - show disk usage info (can filter by file or directory)
- df - show filesystem usage info (can filter by file or directory)

### specific
- ls - list files
- find (search) - find file
- ff (search) - 'find files' (anywhere on the system)

## modify

### general
- mount - show and modify mounted filesystems
  - fstyp - show filesystem types (only available on some systems, can usually use `mount` for this too)
- umount - unmount a mounted filesystem

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

## modify
- ifconfig - show and modify network interface configuration
- ip - show and modify network interface configuration (the newer version of `ifconfig`)

## single-system communication
- talk - single-system text chat
- write - single-system text chat (one line per message)

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

## modify
- cd - change directory
  - options?
- clear - clear the screen
- export - make environment variable available to programs
  - setenv (csh, unused) - csh-style equivalent of the bash-style `export`
- alias - show aliases (without args) or define an alias
- unalias - remove an alias
- function - define a shell function

Temp
==================================================

### networking
- iptables
- netstat
- traceroute
- ping - repeatedly send ICMP packets to a give host and output responses
- ufw

### user and group management
- groupadd
- useradd
- adduser
- passwd - change a user's password (usually your own)

### doing standardised commands based on file type
- run-mailcap (and its aliases: view, see, edit, compose, print)

misc
====================

- lynx - a CLI browser
- elm - a CLI email system
- webster - a CLI dictionary lookup (uses the webster dictionary)

### processes
nice - process priority
renice
pmap - process mem usage
pfiles (solaris only) - process open files
lsof - list open files
fuser [--mount] - show users using given files, filesystems, or block devices

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

### network
netstat
curl

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
batch - command scheduling
crontab

### utils
test / [ - evaluate an expression and returns 0 if true or 1 if false
bc - calculator (arbitrary precision)
expr - limited arithmetic and string expression evaluator [best to use bc]
factor - factor numbers

### programming
cc / c99 / gcc - C compiler
cflow - generate a C call graph
fort77 - fortran compiler [!]
make

lex - generate a lexer (I would suggest using a more modern one, like ANTLR4)
yacc - generate a parser (I would suggest using a more modern one, like ANTLR4)

### version control
git
svn

### text processing
cut
expand / unexpand - convert tabs to spaces and vice versa
fold - line folding (wrapping) program
join - joins lines of files on a common field (like SQL JOIN)
fmt - formats text

### misc
false / true - commands that do nothing, but return non-zero and zero, respectively
fc - fix command (shell builtin), used to quickly correct a previously entered command

### hashing
md5sum
sha1sum
sha224sum
sha256sum
sha384sum
sha512sum
cksum - generate file checksum

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
