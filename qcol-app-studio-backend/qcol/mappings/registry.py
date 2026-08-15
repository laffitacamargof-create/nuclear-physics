"""Registry of complete fermion-to-qubit mapping plugins."""
from __future__ import annotations

from typing import Dict, Tuple

from .base import FermionToQubitMappingPlugin
from .bravyi_kitaev import BKMappingPlugin
from .jordan_wigner import JWMappingPlugin

MAPPING_PLUGIN_REGISTRY_VERSION = "qcol-mapping-plugin-registry/1.2-policy-migrations"
_PLUGINS: Dict[str, FermionToQubitMappingPlugin] = {}

# Explicit policy migrations preserve old public IDs without pretending that
# mapper-plugin IDs and governed MappingPolicy IDs are the same contract.
MAPPING_POLICY_MIGRATIONS = {
    "jordan_wigner.v1": "jordan_wigner.spin_orbital.v1",
    "bravyi_kitaev.v1": "bravyi_kitaev.spin_orbital.default.v1",
}



def register_mapping_plugin(plugin: FermionToQubitMappingPlugin, *, replace: bool = False) -> None:
    if plugin.mapping_id in _PLUGINS and not replace:
        raise KeyError(f"Mapping plugin already registered: {plugin.mapping_id!r}")
    _PLUGINS[plugin.mapping_id] = plugin


for _plugin in (JWMappingPlugin(), BKMappingPlugin()):
    register_mapping_plugin(_plugin)


def get_mapping_plugin(mapping_id: str) -> FermionToQubitMappingPlugin:
    try:
        return _PLUGINS[str(mapping_id)]
    except KeyError as exc:
        raise KeyError(f"Unknown mapping plugin {mapping_id!r}. Available: {sorted(_PLUGINS)}") from exc


def list_mapping_plugins() -> Tuple[FermionToQubitMappingPlugin, ...]:
    return tuple(_PLUGINS[key] for key in sorted(_PLUGINS))


def public_mapping_registry() -> dict:
    return {
        "registry_version": MAPPING_PLUGIN_REGISTRY_VERSION,
        "plugins": [plugin.public_descriptor() for plugin in list_mapping_plugins()],
        "policy_migrations": dict(MAPPING_POLICY_MIGRATIONS),
        "silent_aliasing_allowed": False,
    }
