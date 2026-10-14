"""Reviewed Non-local 2D attention / pooled keys-values module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('nonlocal_attention')

def validate_ir(ir):return validate_case('nonlocal_attention',ir)
