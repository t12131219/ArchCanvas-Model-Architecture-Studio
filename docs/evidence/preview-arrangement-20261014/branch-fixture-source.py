from torch import nn

class BranchArrangementSmoke1791958989204(nn.Module):
    def __init__(self):
        super().__init__()
        self.project = nn.Linear(4, 4)
        self.act = nn.ReLU()
        self.norm = nn.LayerNorm(4)
    def forward(self, features):
        left = self.project(features)
        middle = self.act(features)
        right = self.norm(features)
        return left, middle, right
