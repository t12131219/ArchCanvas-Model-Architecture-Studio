"""Reviewed LU invertible 1x1 convolution module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('glow_invconv_lu')

def validate_ir(ir):return validate_case('glow_invconv_lu',ir)
