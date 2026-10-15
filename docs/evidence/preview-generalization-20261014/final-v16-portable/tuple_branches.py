from torch import nn

class Branch(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(4, 4)
        self.relu = nn.ReLU()
    def forward(self, x):
        return self.relu(self.linear(x))

class TupleBranches(nn.Module):
    def __init__(self):
        super().__init__()
        self.shared = nn.Linear(4, 4)
        self.left = Branch()
        self.right = Branch()
    def forward(self, x):
        shared = self.shared(x)
        left = self.left(shared)
        right = self.right(shared)
        total = left + right
        return left, right, total
