# research-template

A [copier](https://copier.readthedocs.io/) template for research repositories: tracked, reproducible
experiments with a small amount of machinery that is tested once, here, instead of rebuilt in every project.

The process it implements is [`template/docs/process.md.jinja`](template/docs/process.md.jinja) (rendered
into each project as `docs/process.md`). In short:

- **One entry point** (Hydra). `uv run <pkg> ...` is a scratch run; `just run` / `just sweep` are tracked.
- **Tracked runs are tied to a clean commit**, tagged `sweep/<experiment>/<id>`, and refuse to run if the
  code moved while they were queued.
- **Each run writes its own directory**, which is the source of truth. Sweeps are directories too, so no
  process has to stay alive and any member can be resumed. Backends: `local`, `detached` (ssh box), `slurm`.
- **Stages with gates.** `sanity` → `pilot` → `confirm` → `final`. `confirm` needs a pilot decided GO
  (`just decide`, recorded in the log entry's header). Only `final` may read the test split.
- **Failures are never dropped silently.** Aggregates use DONE members and report failed, started and
  missing counts; partial results are flagged *preliminary*.
- **Notebooks read committed snapshots.** Their header (exact command, commit, configuration) is
  generated, and the description of the experiment above it is written before the run.
- **Reproduction** from a sweep or from a committed snapshot: a git worktree at the tag, rerun, compare.
- **Options:** remote box and/or SLURM, an MLflow viewer, Optuna worker pools, a Lightning-Fabric training loop.

## Setup guide

**Once per machine.**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv
uv tool install rust-just                           # just
sudo apt install gh && gh auth login                # GitHub CLI (issues, PRs)
git --version                                       # >= 2.31 recommended (Ubuntu 20.04 ships 2.25:
                                                    #   sudo add-apt-repository ppa:git-core/ppa && sudo apt install git)
```

**Once per project.**

```bash
uvx copier copy --trust ~/PycharmProjects/research-template ~/PycharmProjects/my-project   # answer the questions
cd ~/PycharmProjects/my-project
git init && git checkout -q -b main && just setup cpu local   # venv (cpu torch), git hooks, .env from envs/local.env.example
git add -A && git commit -m "Start from research-template"     # uv.lock included: tracked runs need a clean tree
gh repo create <user>/my-project --private --source . --push   # GitHub remote
just github-init                                    # issue labels: idea, experiment, infra, bug
just test && just smoke                             # everything works
```

Then fill in `README.md` (one sentence on the question), `CLAUDE.md` (current phase, project rules) and
replace the example pipeline `tasks/toy_regression.py` with your first real one.

**A GPU box over ssh** (option `remote`): set `<PKG>_REMOTE_HOST` (ssh alias) and `<PKG>_REMOTE_DIR` in `.env`,
then `just remote-setup` once. It creates the repo there, pushes HEAD over ssh, syncs the venv with the GPU
extra, and creates the box's `.env`. Afterwards: `just push`, `just remote sweep detached ...`, `just pull <experiment>`.

**A SLURM cluster** (option `slurm`): clone on the login node, `cp envs/slurm.env.example .env` (absolute
scratch paths, account, partition), `uv sync --extra <gpu extra> --frozen`, `pre-commit install --hook-type post-merge`;
update with `just sync-code`, launch with `just sweep slurm ...`.

## Workflow, step by step

`just status` shows where you are and the next steps; Claude shows the short form at the start of every
session and reminds you at natural checkpoints (the `workflow` skill).

1. **Idea.** Open an issue: `gh issue create --label idea` (or `experiment`, `bug`, `infra`). Issues are the
   backlog; an idea becomes an experiment once it has a question and a GO / NO-GO criterion.
2. **Branch.** From an up-to-date main: `git switch main && git pull --ff-only && git switch -c exp/<N>-<slug>`
   (`feat/`, `fix/` for non-experiments; `<N>` is the issue number).
3. **Set up the experiment.** `just new-experiment <name> "<question>"`; fill in the config, and write the
   notebook's description (what would mean GO / NO-GO) before anything runs.
4. **Try it cheaply.** Scratch runs (`uv run <pkg> experiment=<name> ...`) until it works; tests for anything
   results depend on (priors, metrics, losses, splits, statistics), not for plotting glue.
5. **Commit.** Small commits; the hook runs ruff and other checks (if it fixed files, `git add -u` and commit
   again). Tracked runs need a clean tree, so commit before every one.
6. **Push.** `git push` (first time `git push -u origin HEAD`) at the end of a session and before anything runs
   elsewhere; the pre-push hook runs the fast tests. Open a draft PR early: `gh pr create --draft --fill`,
   with `Closes #<N>` in the body.
7. **Spend compute in steps.** `just run local sanity ...` → a timing probe (state the cost: members × time)
   → `just sweep <backend> pilot ...` → `confirm` only after a pilot GO (enforced). Ask yourself before
   anything above about a GPU-hour.
8. **Results.** `just snapshot <sweep dir>`, `just notebook <nb>`, then `just decide <sweep dir> <verdict> "<reason>"`;
   a line in the log entry; commit notebook, snapshot and log; push.
9. **Merge.** Feature / fix: when `just test-all` passes. Experiment: when decided. GO merges code, config,
   notebook and snapshot; NO-GO merges notebook, log and snapshot (results are results) and drops the
   experimental code. `gh pr merge --squash --delete-branch`, then `git switch main && git pull --ff-only`.
   Sweep tags keep every run's commit reachable (`git push` carries them), so squashing is safe.
10. **Keep long branches current.** `git merge main` about weekly and before a confirm run.
11. **Machines with running sweeps.** Sweeps run from frozen worktrees, so pulling code is safe. `just sync-code`
    (cluster) and `just push` (GPU box) refuse dependency changes (`uv.lock`, `pyproject.toml`) while sweeps
    are active, unless you pass `force=1`; a plain `git pull` prints a warning instead.

## Update a project

```bash
cd ~/PycharmProjects/my-project
uvx copier update --trust          # merges template changes; conflicts show as git conflict markers
```

Project-owned files (README, CLAUDE.md, research_log/, references, experiment configs, tasks) are never
overwritten; see `_skip_if_exists` in [`copier.yml`](copier.yml).

## Develop the template

`template/` is rendered with `[[ ]]` / `[% %]` Jinja delimiters, because justfiles and GitHub Actions use
`{{ }}` themselves. Files ending in `.jinja` are rendered; others are copied verbatim (their *names* are
still rendered, which is how optional files are switched on and off).

```bash
uvx --with copier pytest tests -x      # renders minimal / default / everything, then in each project:
                                       # uv sync, ruff, pyright, full test suite (incl. slow), smoke run
```

Commit and tag (`git tag v0.x.y`) after changes, so `copier update` in projects can see them.
