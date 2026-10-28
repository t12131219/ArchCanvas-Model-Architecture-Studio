from torch import nn
class Fork(nn.Module):
    def __init__(self):
        super().__init__()
        self.alpha=nn.Linear(8,8)
        self.beta=nn.Sequential(nn.Linear(8,8),nn.Tanh())
    def forward(self,x):
        return self.alpha(x),self.beta(x)
class TupleCrossing(nn.Module):
    def __init__(self):
        super().__init__()
        self.fork=Fork()
        self.other=Fork()
        self.join=nn.Linear(8,8)
    def forward(self,x,y):
        a,b=self.fork(x)
        c,d=self.other(y)
        e=self.join(a+d)
        return {"primary":e,"skip":b+c}
