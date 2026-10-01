from torch import nn


class Model:
    def __init__(self):
        self.projection = nn.Linear(16, 16)

    def forward(self, left, right):
        left_result = self.projection(left)
        right_result = self.projection(right)
        return left_result + right_result
