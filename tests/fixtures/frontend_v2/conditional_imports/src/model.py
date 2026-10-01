from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from torch.nn import ReLU as activation
else:
    from torch.nn import GELU as activation


class Model:
    def forward(self, value):
        return activation(value)
