"""Reviewed Glow ActNorm / data-initialized affine module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('glow_actnorm')

def validate_ir(ir):return validate_case('glow_actnorm',ir)
