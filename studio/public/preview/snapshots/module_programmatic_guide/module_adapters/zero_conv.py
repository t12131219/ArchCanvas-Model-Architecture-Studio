"""Reviewed ZeroConv2d conditioner module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('zero_conv')

def validate_ir(ir):return validate_case('zero_conv',ir)
