"""Nonexecuting source-fixture generator. Seed selects branch count and unary kinds."""
from pathlib import Path
import random
seed=20261017
r=random.Random(seed)
root=Path(__file__).parent
count=r.randint(5,8)
ops=[r.choice(['ReLU','GELU','Tanh','Sigmoid','Identity']) for _ in range(count)]
source='''# Generated static source only; do not execute. Seed: 20261017.
from torch import nn

class 共享残差单元_LongMixedLanguageResidualCell(nn.Module):
    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(16,16)
        self.activation = nn.GELU()
    def forward(self,x):
        h=self.linear(x)
        return self.activation(h)+x

class NestedBranch(nn.Module):
    def __init__(self):
        super().__init__()
        self.cell=共享残差单元_LongMixedLanguageResidualCell()
    def forward(self,x):
        return self.cell(x)

class SeededFanout(nn.Module):
    def __init__(self):
        super().__init__()
        self.nested=NestedBranch()
'''
for i,op in enumerate(ops):source+=f'        self.branch_{i}=nn.{op}()\n'
source+='    def forward(self,x):\n        z=self.nested(x)\n'
for i in range(count):source+=f'        b{i}=self.branch_{i}(z)\n'
source+='        return '+ '+'.join(f'b{i}' for i in range(count))+'\n'
(root/'seeded_fanout.py').write_text(source)
(root/'transformed_mlp.py').write_text('''# Structural holdout: MLP fixture duplicated into nested branches + conditional join.
# Original fixture: fixtures/mlp/model.py. No model code was executed.
from torch import nn

class MLP(nn.Module):
    def __init__(self,input_dim=16,hidden_dim=32,output_dim=16):
        super().__init__()
        self.network=nn.Sequential(nn.Linear(input_dim,hidden_dim),nn.GELU(),nn.Dropout(0.1),nn.Linear(hidden_dim,output_dim))
    def forward(self,features):
        return self.network(features)

class Wrapper(nn.Module):
    def __init__(self):
        super().__init__()
        self.left=MLP()
        self.right=MLP()
        self.project=nn.Linear(16,4)
        self.fallback=nn.Identity()
    def forward(self,x,flag=True):
        a=self.left(x)
        b=self.right(x)
        if flag:
            c=a+b
            y=self.project(c)
        else:
            c=self.fallback(b)
            y=self.project(c)
        return y
''')
print({'seed':seed,'branchCount':count,'operations':ops})
