from torch import nn
class BranchCell(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.alt=nn.Linear(8,8)
    def forward(self,x,choose=True):
        if choose:
            y=self.proj(x)
        else:
            y=self.alt(x)
        return y
class NestedCondition(nn.Module):
    def __init__(self):
        super().__init__()
        self.first=BranchCell()
        self.second=BranchCell()
        self.tail=nn.LayerNorm(8)
    def forward(self,x,flag=True,secondary=False):
        a=self.first(x,flag)
        if flag:
            b=self.second(a,secondary)
            if secondary:
                y=self.tail(a+b)
            else:
                y=self.tail(b)
        else:
            y=self.tail(a)
        return y
