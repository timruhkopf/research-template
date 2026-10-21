"""Rerun a sweep at its tagged commit in a git worktree and compare the summary metrics.

Works from a sweep dir in runs/ or from a committed snapshot in results/ (which keeps the sweep's plan),
so a fresh clone can reproduce reported numbers.
"""

import datetime as dt
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from ..utils.env import repo_root, runs_root, var
from .provenance import git
from .sink import read_run
from .sweep import execute, jobs, read_sweep


def _missing(value: object) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


def _reference(source: Path) -> tuple[Path, dict[int, dict[str, float]]]:
    """(dir holding sweep.json + jobs.jsonl, summary metrics of each DONE member)."""
    if (source / "manifest.json").exists():  # a snapshot
        runs = pd.read_parquet(source / "runs.parquet")
        metrics = json.loads((source / "columns.json").read_text())["metrics"]
        rows = runs.loc[runs["status"] == "DONE", ["member", *metrics]].to_dict("records")
        summaries = {int(r["member"]): {m: float(r[m]) for m in metrics if not _missing(r[m])} for r in rows}
        return source / "sweep", summaries
    summaries = {}
    for m in jobs(source):
        if (source / str(m) / "DONE").exists():
            summaries[m] = read_run(source / str(m)).get("summary", {})
    return source, summaries


def reproduce(
    source: Path, *, sync: bool = True, members: Sequence[int] | None = None, rtol: float = 1e-5, atol: float = 1e-8
) -> bool:
    plan_dir, reference = _reference(source)
    meta = read_sweep(plan_dir)
    if meta.get("allow_dirty"):
        raise ValueError(f"{meta['id']} ran with uncommitted changes; it cannot be reproduced from a commit")
    stamp = f"{dt.datetime.now():%Y%m%d-%H%M%S}"
    worktree = runs_root() / "_reproduce" / f"{meta['id']}_{stamp}"
    git(repo_root(), "worktree", "add", "--detach", str(worktree), meta["tag"] or meta["commit"])
    try:
        env = dict(os.environ)
        if sync:
            extra = var("TORCH_EXTRA") or "cpu"
            subprocess.run(["uv", "sync", "--frozen", "--extra", extra], cwd=worktree, check=True)
            python = str(worktree / ".venv" / "bin" / "python")
        else:  # reuse this environment, import the package from the worktree
            python = sys.executable
            env["PYTHONPATH"] = str(worktree / "src")

        new_dir = runs_root() / meta["experiment"] / f"{meta['id']}_repro_{stamp}"
        new_dir.mkdir(parents=True)
        (new_dir / "sweep.json").write_text(
            json.dumps(
                meta | {"id": new_dir.name, "reproduces": meta["id"], "command": f"just reproduce {source}"},
                indent=1,
            )
        )
        shutil.copy2(plan_dir / "jobs.jsonl", new_dir / "jobs.jsonl")
        execute(new_dir, members or sorted(reference), python=python, cwd=worktree, env=env)
    finally:
        git(repo_root(), "worktree", "remove", "--force", str(worktree))

    ok = True
    for member in members or sorted(reference):
        old = reference.get(member, {})
        new = read_run(new_dir / str(member)).get("summary", {})
        for key in sorted(old):
            same = key in new and bool(np.isclose(old[key], new[key], rtol=rtol, atol=atol))
            ok &= same
            print(
                f"member {member} {key}: {old[key]:.6g} -> {new.get(key, float('nan')):.6g} "
                f"{'ok' if same else 'MISMATCH'}"
            )
    print(f"reproduction {'matches' if ok else 'DIFFERS'}: {new_dir}")
    return ok
