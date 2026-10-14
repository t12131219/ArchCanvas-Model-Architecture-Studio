"""Conditional convolutional VAE from the reviewed MNIST notebook, not textbook defaults."""
from adapters.convvae import _build, _validate

SOURCE = "deeplearning-models-batch3/pytorch_ipynb/autoencoder/ae-cnn-cvae.py"


def build():
    return _build("ccvae",SOURCE,"ConditionalVariationalAutoencoder",50,conditional=True)


def validate_ir(ir):
    return _validate(ir,"ccvae",50,True)
