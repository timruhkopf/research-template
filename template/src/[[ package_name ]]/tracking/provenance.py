"""Git state of the package's repository: tracked runs refuse uncommitted changes that can affect results."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..utils.env import repo_root

# Changes here cannot affect results, so they don't block a tracked launch. Everything else does,
# including untracked files, uv.lock, pyproject.toml, justfile and scripts/.
ALLOWED_DIRTY = (
    "research_log/",
    "notebooks/",
    "results/",
    "reports/",
    "docs/",
    "references.md",
    "references.bib",
    "README.md",
    "CLAUDE.md",
)


class DirtyTreeError(RuntimeError):
    pass


@dataclass(frozen=True)
class GitState:
    commit: str
    branch: str
    dirty_paths: tuple[str, ...]

    @property
    def dirty(self) -> bool:
        return bool(self.dirty_paths)


def git(repo: Path, *args: str) -> str:
    # -C: never rely on the cwd (Hydra may chdir into the run dir).
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def git_state(repo: Path | None = None) -> GitState:
    repo = repo or repo_root()
    try:
        commit = git(repo, "rev-parse", "HEAD")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return GitState(commit="none", branch="none", dirty_paths=("<not a git repository or no commit>",))
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    porcelain = subprocess.check_output(  # not git(): stripping would eat the first line's status column
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"], text=True
    )
    paths = []
    for line in porcelain.splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if not path.startswith(ALLOWED_DIRTY):
            paths.append(path)
    return GitState(commit=commit, branch=branch, dirty_paths=tuple(paths))


def require_clean(repo: Path | None = None) -> GitState:
    state = git_state(repo)
    if state.dirty:
        listing = "\n  ".join(state.dirty_paths[:20])
        raise DirtyTreeError(
            f"uncommitted changes that can affect results:\n  {listing}\n"
            "Commit them first (or use a scratch run: `uv run <package> ...`)."
        )
    return state


def tag(name: str, commit: str, repo: Path | None = None) -> None:
    git(repo or repo_root(), "tag", name, commit)
