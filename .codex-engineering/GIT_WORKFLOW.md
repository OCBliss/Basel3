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
READMEs, tests and journal evidence. Push immediately when the change is finished;
do not hold completed work for a later batch. Then pull and review:

```bash
git fetch origin
git log --oneline --left-right main...origin/main
# Integrate any new remote commits before pushing.
git push origin main
git pull --ff-only origin main
git rev-parse HEAD origin/main
git status --short --branch
```

After a completed push, the two printed revisions should match. A rejected push
needs diagnosis; do not report local commits as published. Inspect diffs and
exclude credentials, caches and unrelated generated data before staging.

Review the synchronized change, affected README commands and validation evidence.
Retrieve the changed files from GitHub and confirm their contents. If the pull
introduces other commits, review them and rerun affected checks. Correct findings
and repeat commit, push, pull and review before reporting completion.

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

## Persistent SSH on this Mac

`~/.ssh/config` now selects the existing Basel3 identity automatically. The prior
repository-local `core.sshCommand` override has been removed. Standard Git fetch,
push and pull use the SSH remote `git@github.com:OCBliss/Basel3.git`.

The installed configuration is:

```sshconfig
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/codex_basel3_ed25519
    IdentitiesOnly yes
    AddKeysToAgent yes
    PubkeyAuthentication yes
    BatchMode yes
    StrictHostKeyChecking yes
    UpdateHostKeys no
```

The configuration and private key have owner-only permissions (0600); the SSH
directory has 0700 permissions. The existing key authenticates directly from
disk without a passphrase prompt. `AddKeysToAgent` loads it automatically when
an agent is available, but authentication does not depend on an already-loaded
agent. No shell startup command or repeatedly entered identity option is needed.
Existing verified GitHub host keys are retained and strict checking stays enabled.

Verify from a new terminal session:

```bash
ssh -T git@github.com
git fetch origin
git push origin main
git pull --ff-only origin main
git rev-parse HEAD origin/main
```

GitHub's successful SSH greeting also says it does not provide shell access and
returns status 1 for that test. Actual Git fetch, push and pull must succeed.
Authentication was additionally verified in a fresh `zsh -f` shell with
`IdentityAgent=none`, `AddKeysToAgent=no`, and no explicit identity-file option.
This verifies use of the saved configuration without a warm agent; the computer
was not rebooted for the test.

The identity is a write-enabled deploy key for **OCBliss/Basel3**, not an
account-wide key for unrelated private repositories. Another machine needs its
own registered key and verified host configuration. Private keys and this Mac's
SSH configuration are outside the project and are never committed.

See GitHub's [SSH configuration guidance](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent?platform=mac).

## Private repository 404 in a browser

SSH and the connected GitHub integration authenticate independently of a browser.
The reported screenshot showed a **Sign in** button: that browser was signed out.
An unauthenticated request for this private repository can return 404 even when
SSH pushes and authenticated file retrieval succeed. Browser authentication does
not affect the automatic Git workflow above. See GitHub's
[404 authentication explanation](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api#404-not-found-for-an-existing-resource).
