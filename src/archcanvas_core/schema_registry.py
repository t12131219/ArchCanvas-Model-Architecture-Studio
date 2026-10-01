from __future__ import annotations

from .architecture_v2 import ARCHITECTURE_V2_SCHEMA_MODELS
from .models import SCHEMA_MODELS as V1_SCHEMA_MODELS
from .module_contract import MODULE_CONTRACT_SCHEMA_MODELS
from .source_v2 import SOURCE_V2_SCHEMA_MODELS

SCHEMA_MODELS = {
    **V1_SCHEMA_MODELS,
    **SOURCE_V2_SCHEMA_MODELS,
    **MODULE_CONTRACT_SCHEMA_MODELS,
    **ARCHITECTURE_V2_SCHEMA_MODELS,
}
