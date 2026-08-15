"""Independent multi-pair reduced-pairing model plugin."""
from .acceptance import MultiPairAcceptanceReport, assess_multi_pair_artifact
from .contract import (
    MODEL_ID,
    MODEL_VERSION,
    MULTI_PAIR_ACCEPTANCE_PRESETS,
    MULTI_PAIR_MODEL_CONTRACT,
    SUPPORTED_TASK,
)

__all__ = [
    "MODEL_ID",
    "MODEL_VERSION",
    "MULTI_PAIR_ACCEPTANCE_PRESETS",
    "MULTI_PAIR_MODEL_CONTRACT",
    "SUPPORTED_TASK",
    "MultiPairAcceptanceReport",
    "assess_multi_pair_artifact",
]
