from torch import nn
raise RuntimeError("STATIC_ONLY_SENTINEL_MUST_NOT_EXECUTE")

class GoldenIndex(nn.Module):
    def __init__(self):
        super().__init__()
        self.mapper = nn.Linear(4, 4)

    def forward(self, records):
        return {name: self.mapper(embedding) for name, embedding in records if embedding is not None}
