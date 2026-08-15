from .base import (
    FermionToQubitMappingPlugin,
    MappedProblemArtifact,
    MappingAnalysisEntry,
    MappingCapabilityReport,
    MappingComparisonReport,
    MappingCompatibilityReport,
    MappingResourceReport,
)
from .bravyi_kitaev import BKMappingPlugin
from .jordan_wigner import JWMappingPlugin
from .registry import get_mapping_plugin, list_mapping_plugins, public_mapping_registry


def analyze_mappings(*args, **kwargs):
    """Load NumPy/OpenFermion analysis only when the task actually runs."""
    from .analysis import analyze_mappings as implementation

    return implementation(*args, **kwargs)


__all__ = [
    "FermionToQubitMappingPlugin",
    "MappedProblemArtifact",
    "MappingAnalysisEntry",
    "MappingCapabilityReport",
    "MappingComparisonReport",
    "MappingCompatibilityReport",
    "MappingResourceReport",
    "JWMappingPlugin",
    "BKMappingPlugin",
    "get_mapping_plugin",
    "list_mapping_plugins",
    "public_mapping_registry",
    "analyze_mappings",
]
