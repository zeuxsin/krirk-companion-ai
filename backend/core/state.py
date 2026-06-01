from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class AISystemState(str, Enum):
    IDLE = "idle"
    THINKING = "thinking"
    SPEAKING = "speaking"
    LISTENING = "listening"
    EXECUTING = "executing"


@dataclass
class AIState:
    current: AISystemState = AISystemState.IDLE
    started_at: datetime = field(default_factory=datetime.now)
    _callbacks: list = field(default_factory=list, repr=False)

    def set(self, state: AISystemState):
        self.current = state
        self.started_at = datetime.now()
        for cb in self._callbacks:
            cb(state.value)

    def on_change(self, callback):
        self._callbacks.append(callback)

    def is_busy(self) -> bool:
        return self.current != AISystemState.IDLE
