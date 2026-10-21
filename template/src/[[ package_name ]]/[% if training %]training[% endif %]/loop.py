"""One training loop. Fabric does devices, precision, DDP/FSDP and checkpoint I/O; we keep the loop."""

from collections.abc import Callable, Sequence
from pathlib import Path

import torch
from lightning.fabric import Fabric
from torch import Tensor, nn

from .callbacks import Callback
from .state import TrainState

Batch = tuple[Tensor, Tensor]


def fit(
    model: nn.Module,
    optimizer_factory: Callable,
    loss_fn: Callable[[Tensor, Tensor], Tensor],
    batch_at: Callable[[int], Batch],
    *,
    fabric: Fabric,
    max_steps: int,
    ckpt_path: Path,
    callbacks: Sequence[Callback] = (),
) -> TrainState:
    """batch_at(step) -> batch: data that depends only on the step resumes exactly after a restart."""
    optimizer = optimizer_factory(model.parameters())
    model, optimizer = fabric.setup(model, optimizer)
    state = TrainState()
    objects = {"model": model, "optimizer": optimizer}
    if ckpt_path.exists():
        loaded = {**objects, "state": {}}  # modules/optimizers load in place; plain values are returned
        fabric.load(ckpt_path, loaded)
        state.load_state_dict(loaded["state"])

    model.train()
    while state.step < max_steps:
        x, y = (t.to(fabric.device) for t in batch_at(state.step))
        loss = loss_fn(model(x), y)
        optimizer.zero_grad()
        fabric.backward(loss)
        optimizer.step()
        state.step += 1
        state.loss = float(loss.detach())
        state.should_stop = state.step >= max_steps
        for cb in callbacks:
            cb.on_step_end(state, fabric, objects)
    return state


@torch.no_grad()
def evaluate(model: nn.Module, loss_fn: Callable[[Tensor, Tensor], Tensor], batch: Batch, fabric: Fabric) -> float:
    model.eval()
    x, y = (t.to(fabric.device) for t in batch)
    return float(loss_fn(model(x), y))
