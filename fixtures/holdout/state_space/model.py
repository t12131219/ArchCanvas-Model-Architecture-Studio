"""Unseen state-space cell used for generic recovery acceptance."""

from torch import nn


class SelectiveStateCell(nn.Module):
    def __init__(self, d_model: int = 24):
        super().__init__()
        self.input_projection = nn.Linear(d_model, d_model)
        self.state_transition = nn.Linear(d_model, d_model)
        self.output_projection = nn.Linear(d_model, d_model)

    def forward(self, signal, state):
        driven = self.input_projection(signal)
        carried = self.state_transition(state)
        next_state = driven + carried
        output = self.output_projection(next_state)
        return output
