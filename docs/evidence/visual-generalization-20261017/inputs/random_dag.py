from torch import nn
class RandomDAG(nn.Module):
    def __init__(self):
        super().__init__()
        self.stage_0=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_1=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_2=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_3=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_4=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_5=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_6=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_7=nn.Sequential(nn.Linear(8,8),nn.GELU())
        self.stage_8=nn.Sequential(nn.Linear(8,8),nn.GELU())
    def forward(self,x):
        v0=self.stage_0(x)
        v1=self.stage_1(v0)
        v2=self.stage_2(v1+v0)
        v3=self.stage_3(v1+v0)
        v4=self.stage_4(v0)
        v5=self.stage_5(v1+v2)
        v6=self.stage_6(v4)
        v7=self.stage_7(v6+v3)
        v8=self.stage_8(v4+v6)
        return v8,v5,v2
