from torch import nn
class Level0(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=nn.Sequential(nn.Linear(8,8),nn.ReLU())
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
class Level1(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=Level0()
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
class Level2(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=Level1()
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
class Level3(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=Level2()
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
class Level4(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=Level3()
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
class Level5(nn.Module):
    def __init__(self):
        super().__init__()
        self.inner=Level4()
        self.skip=nn.Identity()
    def forward(self,x):
        return self.inner(x)+self.skip(x)
