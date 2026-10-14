"""Reviewed Degree mask / strict autoregressive topology module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('autoregressive_mask')

def validate_ir(ir):return validate_case('autoregressive_mask',ir)
