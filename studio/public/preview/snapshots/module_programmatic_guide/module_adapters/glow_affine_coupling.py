"""Reviewed Glow affine coupling module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('glow_affine_coupling')

def validate_ir(ir):return validate_case('glow_affine_coupling',ir)
