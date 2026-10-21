import torch
from jaxtyping import Float
from torch import Tensor, nn


class MLP(nn.Module):
    """Example model. The jaxtyping annotations are checked (by beartype) whenever tests run."""

    def __init__(self, in_dim: int, hidden: int, out_dim: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(), nn.Linear(hidden, out_dim))

    def forward(self, x: Float[Tensor, "batch in_dim"]) -> Float[Tensor, "batch out_dim"]:
        return self.net(x)


def mse(pred: Float[Tensor, "batch 1"], target: Float[Tensor, "batch 1"]) -> Float[Tensor, ""]:
    return torch.mean((pred - target) ** 2)
