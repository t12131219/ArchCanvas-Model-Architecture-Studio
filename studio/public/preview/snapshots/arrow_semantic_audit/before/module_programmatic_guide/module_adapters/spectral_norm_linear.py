"""Reviewed Spectral normalization / Linear wrapper module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('spectral_norm_linear')

def validate_ir(ir):return validate_case('spectral_norm_linear',ir)
