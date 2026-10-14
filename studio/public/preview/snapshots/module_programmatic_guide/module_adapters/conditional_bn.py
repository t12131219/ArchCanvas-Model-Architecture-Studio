"""Reviewed Conditional BatchNorm / two condition heads module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('conditional_bn')

def validate_ir(ir):return validate_case('conditional_bn',ir)
