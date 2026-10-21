"""Everything that can be a callback is one (logging, checkpointing, preemption), not a branch in fit()."""

import signal
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from lightning.fabric import Fabric

from ..tracking.sink import Preempted, Run
from .state import TrainState


@runtime_checkable
class Callback(Protocol):
    def on_step_end(self, state: TrainState, fabric: Fabric, objects: dict[str, Any]) -> None: ...


class LogMetrics:
    def __init__(self, run: Run, every: int, key: str = "train/loss"):
        self.run, self.every, self.key = run, every, key

    def on_step_end(self, state: TrainState, fabric: Fabric, objects: dict[str, Any]) -> None:
        if state.step % self.every == 0 and fabric.is_global_zero:
            self.run.log_metric(self.key, state.loss, state.step)


class Checkpoint:
    """Saves last.ckpt every `every` steps, and on SIGUSR1 (SLURM's warning before the time limit):
    then it saves and raises Preempted, so the member stays STARTED and resumes after requeue."""

    def __init__(self, path: Path, every: int):
        self.path, self.every, self._preempted = path, every, False
        signal.signal(signal.SIGUSR1, self._on_signal)

    def _on_signal(self, signum: int, frame: Any) -> None:
        self._preempted = True

    def on_step_end(self, state: TrainState, fabric: Fabric, objects: dict[str, Any]) -> None:
        if state.step % self.every == 0 or self._preempted or state.should_stop:
            fabric.save(self.path, {**objects, "state": state.state_dict()})
        if self._preempted:
            raise Preempted(f"checkpointed at step {state.step}")
