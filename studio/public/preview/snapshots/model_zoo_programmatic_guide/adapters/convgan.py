"""Convolutional MNIST GAN with raw logits, not the WGAN critic configuration."""
from adapters.dcwgan import _build, _validate

SOURCE = "deeplearning-models-batch4/pytorch_ipynb/gan/gan-conv.py"


def build():
    return _build("convgan",SOURCE,False)


def validate_ir(ir):
    return _validate(ir,"convgan",False)
