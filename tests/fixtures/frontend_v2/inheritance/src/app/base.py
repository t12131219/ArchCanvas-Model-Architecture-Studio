from .factory import make_activation


class BaseModel:
    def __init__(self):
        self.activation = make_activation()

    def forward(self, x):
        return self.activation(x)
