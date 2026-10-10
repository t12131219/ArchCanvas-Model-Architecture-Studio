from torch import nn
class FernCell(nn.Module):
 def __init__(self):
  super().__init__(); self.projection=nn.Linear(4,4); self.activation=nn.GELU(); self.head=nn.Linear(4,2)
 def forward(self,x): return self.head(self.activation(self.projection(x)))
class UnknownFern(nn.Module):
 def __init__(self,config):
  super().__init__(); self.enabled=config.alternative; self.left=FernCell(); self.right=FernCell()
 def forward(self,x):
  if self.enabled: x=self.left(x)
  else: x=self.right(x)
  return x
