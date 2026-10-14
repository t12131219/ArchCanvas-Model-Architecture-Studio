"""Reviewed CORAL / shared ordinal score head module profile."""
from module_adapters.root_support import build_case,validate_case

def build():return build_case('coral_head')

def validate_ir(ir):return validate_case('coral_head',ir)
