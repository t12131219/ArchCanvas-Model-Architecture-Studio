"""Frozen source module; bounded Inception AST adapter."""
from module_adapters._inception_extended import build_variant,validate_variant
def build():return build_variant('inception_factorized')
def validate_ir(ir):return validate_variant(ir,'inception_factorized')
