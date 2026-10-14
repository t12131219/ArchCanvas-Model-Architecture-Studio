"""Reviewed CORN probability decoder module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('corn_decoder')

def validate_ir(ir):return validate_case('corn_decoder',ir)
