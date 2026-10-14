"""Reviewed Split prior / conditional Gaussian density module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('glow_split_prior')

def validate_ir(ir):return validate_case('glow_split_prior',ir)
