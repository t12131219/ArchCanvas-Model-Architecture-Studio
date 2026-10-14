"""Reviewed MADESplit / autoregressive affine module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('made_split')

def validate_ir(ir):return validate_case('made_split',ir)
