# Todo - Git / Version Control

- git - version control system
- svn - version control system [?]

## Notes

- https://www.youtube.com/watch?v=Md44rcw13k4

---

- https://stackoverflow.com/questions/57265785/whats-the-difference-between-git-switch-and-git-checkout-branch
- git checkout/switch/restore

- git rebase --update-refs
  - updates refs to commits that were on the commit set you're rebasing
  - https://adamj.eu/tech/2022/10/15/how-to-rebase-stacked-git-branches/
  - https://medium.com/@alexanderjukes/stacked-diffs-vs-trunk-based-development-f15c6c601f4b
  - git config --global rebase.updateRefs true

- https://www.youtube.com/watch?v=0BNVkMoLJxc
  - git is very slow for large monorepos (albeit with some significant improvements from MS recently)
  - people often use monorepos these days
  - monorepos allow you to speed up your dev process by reducing the amount of cross-project management you have to do
  - stacked diffs allow you to develop multiple, backwards-dependent features simultaneously

  - other interesting things:
    - map commands between similar systems
    - Phabricator - a GH/GL alternative, ie. a suite of integrated tools:
      - repo browser, code review, change monitoring, bug tracker, wiki
    - Graphite - a tool for managing stacked diffs in git/GH

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

repo = git log --abbrev-commit --format=oneline --graph --all
repo-l = git log --abbrev-commit --format=oneline --graph --all
repo-b = git log --oneline --graph default_branch..HEAD

repo-d = git log --oneline --graph --all --format='%C(yellow)%<|(15)%h %C(cyan)%<|(30)%ad %C(yellow)%<|(50)%an %C(reset)%s%C(auto)%d'
repo-ld = git log --oneline --graph --format='%C(yellow)%<|(15)%h %C(cyan)%<|(30)%ad %C(yellow)%<|(50)%an %C(reset)%s%C(auto)%d'

diff = diff-l
diff-s = git diff --stat
diff-l = git diff
diff-w = git diff --word-diff
diff-c = git diff --word-diff --word-diff-regex='.'

show = show-l
show-s = git show --stat
show-sr = diff-s HEAD^..HEAD
show-l = git show
show-lr = diff-l HEAD^..HEAD
show-w = git show --word-diff
show-wr = diff-w HEAD^..HEAD
show-c = git show --word-diff --word-diff-regex='.'
show-cr = diff-c HEAD^..HEAD

---

- GitLab
  - https://github.com/python-gitlab/python-gitlab

- GitHub
- Azure
- Concourse - CI system

- Remote repo state
  - eg. archive status (auto-tag?)

---

- flow patterns
  - atomic commits (https://dev.to/samuelfaure/how-atomic-git-commits-dramatically-increased-my-productivity-and-will-increase-yours-too-4a84)
    - linked from https://dev.to/samuelfaure/how-to-be-a-great-software-engineer-without-using-your-brain-1g5k
