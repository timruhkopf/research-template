from dataclasses import asdict, dataclass


@dataclass
class TrainState:
    step: int = 0
    loss: float = float("nan")
    should_stop: bool = False

    def state_dict(self) -> dict:
        return asdict(self)

    def load_state_dict(self, d: dict) -> None:
        self.step, self.loss = int(d["step"]), float(d["loss"])
