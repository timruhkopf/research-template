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

## Create a project

```bash
uvx copier copy --trust ~/PycharmProjects/research-template ~/PycharmProjects/my-project
cd ~/PycharmProjects/my-project
git init && just setup cpu local                 # needs uv and just (uv tool install rust-just)
git add -A && git commit -m "Start from research-template"
just test && just smoke
```

Questions: project and package name, author, description, Python version (3.12), GPU torch extra
(`cu126`; checked to work on ulysses' driver 550 with an RTX 3090), compute (`remote`, `slurm`), `mlflow`,
`optuna`, `training`.

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
