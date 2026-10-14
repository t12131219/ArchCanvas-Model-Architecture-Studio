"""Reviewed Squeeze / space-to-channel module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('glow_squeeze')

def validate_ir(ir):return validate_case('glow_squeeze',ir)
