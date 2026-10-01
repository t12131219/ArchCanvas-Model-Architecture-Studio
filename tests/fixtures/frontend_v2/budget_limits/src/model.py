def inner(value):
    return value


def outer(value):
    return inner(value)


class Model:
    def forward(self, value):
        return outer(value)
