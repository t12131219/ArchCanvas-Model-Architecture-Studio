"""Reviewed Manual / fused BatchNorm arithmetic module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('manual_fused_bn')

def validate_ir(ir):return validate_case('manual_fused_bn',ir)
