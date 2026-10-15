from torch import nn
raise RuntimeError("STATIC_ONLY_SENTINEL_MUST_NOT_EXECUTE")

class CobaltMap(nn.Module):
    def __init__(self):
        super().__init__()
        self.projection = nn.Linear(4, 4)

    def forward(self, batch):
        return {tag: self.projection(vector) for tag, vector in batch if vector is not None}
