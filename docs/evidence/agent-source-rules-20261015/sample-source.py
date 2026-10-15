from torch import nn
class River(nn.Module):
 def __init__(self):
  super().__init__(); self.transforms=nn.ModuleList([nn.Identity()])
 def forward(self,values):
  result=[transform(values) for transform in self.transforms]
  return result
