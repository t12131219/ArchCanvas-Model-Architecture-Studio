from module_adapters._shuffle_extended import build_variant,validate_variant
def build():return build_variant('shuffle_ir_stride1',1)
def validate_ir(ir):return validate_variant(ir,'shuffle_ir_stride1',1)
