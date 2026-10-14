"""Reviewed BatchNormFlow / affine + logdet module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('flow_batchnorm')

def validate_ir(ir):return validate_case('flow_batchnorm',ir)
