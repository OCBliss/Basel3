# GitHub synchronization and SSH

Run commands from `Basel3_repo`. Active work is on `main`, which now contains all
existing `refactor` work. The user has authorized regular commits, fetches, pushes
and branch integration in this repository. Keep coherent progress visible on
GitHub rather than accumulating completed work only on the local machine.

## Work on main

```bash
git fetch origin
git status --short --branch
git switch main
git log --oneline --left-right main...origin/main
```

Inspect uncommitted and incoming changes before integrating. If the working tree
is clean and `main` is only behind, use `git merge --ff-only origin/main`. If both
sides advanced, review and merge normally, resolve conflicts and run affected
checks. Preserve user edits; do not reset them or force-push.

After implementing and checking a coherent change, stage its explicit paths,
inspect the staged diff, and commit with a descriptive message. Include affected
READMEs, tests and journal evidence. Then publish and verify:

```bash
git fetch origin
git log --oneline --left-right main...origin/main
# Integrate any new remote commits before pushing.
git push origin main
git fetch origin
git rev-parse HEAD origin/main
git status --short --branch
```

After a completed push, the two printed revisions should match. A rejected push
needs diagnosis; do not report local commits as published. Inspect diffs and
exclude credentials, caches and unrelated generated data before staging.

## Transfer a stable milestone to refactor

Only after implementation and appropriate regression/integration checks, start
with a clean working tree and fetch both branches. Inspect their differences,
then integrate without rewriting shared history:

```bash
git fetch origin
git switch refactor
git merge origin/refactor
git merge main
# Resolve any conflicts and run the affected checks before publishing.
git push origin refactor
git switch main
git merge refactor
git push origin main
git fetch origin
```

The final merge carries any refactor-only concurrent work back to the active
branch. Stop to resolve errors before continuing subsequent commands. Recheck
the working tree and remote revisions when finished.

## The SSH failure and its fix on the current Mac

The existing key is `~/.ssh/codex_basel3_ed25519`. It was not among SSH's default
identity filenames, and the SSH agent had no loaded identities. GitHub accepted
the key when explicitly selected; no new key was required. This repository's
local configuration now selects it and uses the SSH remote.

To inspect or reproduce the repository-local configuration on this Mac:

```bash
git remote -v
git config --local --get core.sshCommand
git config --local core.sshCommand \
  'ssh -i ~/.ssh/codex_basel3_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no'
git remote set-url origin git@github.com:OCBliss/Basel3.git
git fetch origin
```

This configuration is stored in `.git/config`, not committed. A fresh clone or
another computer needs its own valid GitHub credential and verified host key.
Never copy private keys into the repository. The current identity authenticates
to `OCBliss/Basel3`; successful fetching and pushing were verified.

For diagnosis, GitHub's [public-key troubleshooting guide](https://docs.github.com/en/authentication/troubleshooting-ssh/error-permission-denied-publickey)
explains the explicit `ssh -i` test. GitHub's successful SSH test message also says
it does not provide shell access; that text is expected and is not an error in
Git repository access.
