"""Reviewed MaskedLinear / conditional projection module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('masked_linear')

def validate_ir(ir):return validate_case('masked_linear',ir)
