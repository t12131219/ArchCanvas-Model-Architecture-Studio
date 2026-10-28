# Structural holdout: MLP fixture duplicated into nested branches + conditional join.
# Original fixture: fixtures/mlp/model.py. No model code was executed.
from torch import nn

class MLP(nn.Module):
    def __init__(self,input_dim=16,hidden_dim=32,output_dim=16):
        super().__init__()
        self.network=nn.Sequential(nn.Linear(input_dim,hidden_dim),nn.GELU(),nn.Dropout(0.1),nn.Linear(hidden_dim,output_dim))
    def forward(self,features):
        return self.network(features)

class FourBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.left=MLP()
        self.right=MLP()
        self.project=nn.Linear(16,4)
        self.fallback=nn.Identity()
        self.third=MLP()
        self.fourth=MLP()
    def forward(self,x,flag=True):
        a=self.left(x)
        b=self.right(x)
        if flag:
            c=(a+b)+(self.third(x)+self.fourth(x))
            y=self.project(c)
        else:
            c=self.fallback(a+b)
            y=self.project(c)
        return y
