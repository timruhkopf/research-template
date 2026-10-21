"""Render the template for several option combinations; each rendered project must lint, type-check and
pass its own full test suite (incl. slow tests) from a clean commit, exactly as its CI would.

    uvx --with copier pytest tests -x      # a few minutes per combination
"""

import os
import subprocess
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parents[1]
COMBINATIONS = {
    "minimal": {"compute": "[]", "mlflow": "false", "optuna": "false", "training": "false"},
    "default": {},
    "everything": {"compute": '["remote", "slurm"]', "mlflow": "true", "optuna": "true", "training": "true"},
}


def sh(cmd: list[str], cwd: Path) -> str:
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"{' '.join(cmd)}\n{proc.stdout[-3000:]}\n{proc.stderr[-3000:]}"
    return proc.stdout


@pytest.mark.parametrize("name", COMBINATIONS)
def test_rendered_project(name: str, tmp_path: Path) -> None:
    dst = tmp_path / "demo-proj"
    data = {"project_name": "demo-proj", "author": "Test Author", "email": "test@example.com", **COMBINATIONS[name]}
    answers = [arg for k, v in data.items() for arg in ("-d", f"{k}={v}")]
    sh(["copier", "copy", "--trust", "--defaults", "--vcs-ref=HEAD", *answers, str(TEMPLATE), str(dst)], tmp_path)
    assert not list(dst.rglob("*.jinja")), "unrendered files"

    git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
    sh(["git", "init", "-q"], dst)
    sh(["uv", "sync", "--extra", "cpu", "--group", "notebooks"], dst)
    sh(["git", "add", "-A"], dst)
    sh([*git, "commit", "-qm", "rendered"], dst)  # the uv.lock is committed: provenance needs a clean tree

    run = ["uv", "run", "--no-sync"]
    sh([*run, "ruff", "check", "."], dst)
    sh([*run, "ruff", "format", "--check", "."], dst)
    sh([*run, "pyright"], dst)
    out = sh([*run, "python", "-m", "pytest", "-m", "", "-q", "-p", "no:cacheprovider"], dst)
    assert "skipped" not in out, out[-2000:]
    sh([*run, "python", "-m", "demo_proj.main", "experiment=debug"], dst)  # the smoke run
