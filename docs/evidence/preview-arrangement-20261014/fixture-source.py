from torch import nn

class Inner(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner_act = nn.Sigmoid()
    def forward(self, features):
        return self.inner_act(features)

class ArrangementSmoke1791958981138(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)
        self.act = nn.ReLU()
        self.norm = nn.LayerNorm(4)
        self.nested = Inner()
    def forward(self, features):
        value = self.project(features)
        value = self.act(value)
        value = self.norm(value)
        return self.nested(value)
