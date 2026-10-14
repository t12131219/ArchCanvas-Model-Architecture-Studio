from module_adapters._deform_extended import build_variant,validate_variant
def build():return build_variant('deformable_conv',True)
def validate_ir(ir):return validate_variant(ir,'deformable_conv',True)
