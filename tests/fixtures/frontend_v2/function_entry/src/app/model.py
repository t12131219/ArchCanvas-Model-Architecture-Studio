from .helpers import activate


def model_fn_body(inputs):
    hidden = activate(inputs)
    return hidden
