# Basel3 engineering instructions

## Project boundary

The sole project root is this `Basel3_repo` directory. Set the working directory
explicitly before project commands. Do not scan or modify the parent `Basel_III`
folder or sibling projects. Keep fixtures, scratch files, caches, environments,
logs and research artifacts inside this repository. Check resolved paths and
symlinks before executing scripts. Preserve existing user edits and source data.

## Research and implementation

Read `.codex-engineering/CURRENT_TASK.md`, `.codex-engineering/JOURNAL.md`, recent
commits and the relevant complete execution paths before choosing work. Resume
an unfinished capability first. Select one substantive analytical or engineering
capability, implement it, test it against independent expectations and existing
consumers, and iterate on failures until the selected milestone is complete.
Routine repairs and documentation can support a milestone but do not satisfy
the recurring capability-development assignment on their own.

For RWA, read `PDF/Recursive IRR Model.pdf` and the existing implementation.
The author's clarification requires applying the calibration to the estimated
mu, theta and sigma histories across all maturities, with coupled treatment of
ridge conditions. Preserve the distinction between estimation noise and latent
parameter dynamics. The finite hierarchy is a completed baseline, not the full
recursive model or an RWA valuation implementation.

Choose methods from the research question and evidence. Understand the existing
JSD distribution comparisons across cohorts, horizons and bin specifications;
do not replace that reasoning with a default preference for industry convention
or low-order moments. Validate distributional behavior, dependence and tails
where relevant. Do not claim novelty or superiority without evidence.

## GitHub workflow: standing user authorization

Use `main` for ongoing work so the user can follow it on GitHub. Ordinary commits,
fetches, pushes and integration of this repository's branches are explicitly
authorized. Fetch at the start, before integration, and before publishing a
meaningful checkpoint. Inspect incoming changes and preserve concurrent work.
Commit coherent source, tests, documentation and journal evidence; push completed
checkpoints to `origin/main` and verify the remote commit. A local commit alone
does not meet the synchronization requirement. Do not force-push or rewrite shared
history. Do not stage credentials, private keys, caches or unrelated artifacts.

Required completion cycle: finish the change and relevant tests, commit and push
immediately, pull from GitHub, then review the synchronized code and documentation.
Do not hold completed work for a later batch or scheduled run. After pushing,
use git pull --ff-only origin main when history permits. Review incoming changes,
confirm local/remote revisions match, and retrieve affected files and READMEs
from GitHub. Correct review findings and repeat the cycle before reporting
completion. Resolve divergence without discarding work or force-pushing.

All existing `refactor` work has been integrated into `main`. Keep developing on
`main`; after a capability is stable and verified, integrate it into `refactor`
with a normal merge or fast-forward, resolve conflicts and verify both branches,
then return to `main`. Do not transfer unfinished changes as if they were stable.
Git publication authorization does not extend to package releases, deployments,
destructive operations or machine-wide configuration changes.

## Documentation and evidence

Maintain a README in every authored code component, with purpose, prerequisites,
commands from the repository root, inputs, outputs and significant limitations.
Update affected guides whenever behavior changes. Use relative Markdown links
inside repository documents so they work in GitHub and a fresh clone.

Append dated journal entries for substantive attempts, failures, revisions,
validation and accomplishments. Update the current checkpoint after meaningful
progress or interruption. Retain useful evidence and exact reproduction commands.
Check existing regression evidence before repeating expensive unchanged tests;
run checks appropriate to each actual change. Never report an unrun test or an
unpublished commit as complete.
