"""User navigation and authoritative scientific-core projections.

The user sees three simple entrances.  Those labels are navigation only.  The
scientific core is a read-only projection from the ModelContract and the
resolved policy/realization registries; it stores no duplicate semantic truth.
"""
from __future__ import annotations

from typing import Any

from .model_registry import get_model_contract, list_model_contracts
from .model_task_matrix import public_model_task_matrix
from .realization_variants import public_model_task_realization_catalog
from .request_boundaries import copy_plain_data

USER_NAVIGATION_SCHEMA = "qcol-user-navigation/1.0"
SCIENTIFIC_CORE_VIEW_SCHEMA = "qcol-scientific-core-view/1.0"

_GROUPS = (
    ("oscillators", "Oscillators"),
    ("fermions", "Fermions"),
    ("custom", "Custom"),
)


def public_user_navigation_catalog() -> dict[str, Any]:
    models = list_model_contracts()
    groups = []
    for group_id, label in _GROUPS:
        model_ids = [
            contract.model_id for contract in models
            if contract.classification is not None
            and contract.classification.ui_group_id == group_id
        ]
        groups.append({
            "id": group_id,
            "label": label,
            "authority": "navigation_only",
            "scientific_inference_allowed": False,
            "resource_inference_allowed": False,
            "model_ids": model_ids,
        })
    return {
        "schema_version": USER_NAVIGATION_SCHEMA,
        "groups": groups,
        "rule": "Simple user navigation must not constrain or classify the internal physics ontology.",
    }


def _supported_realizations(model_id: str) -> list[dict[str, Any]]:
    matrix = public_model_task_matrix()
    variants = public_model_task_realization_catalog()
    cells = {row["cell_id"]: row for row in matrix["cells"]}
    variant_cells = {row["cell_id"]: row for row in variants["cells"]}
    rows = []
    for cell_id, cell in sorted(cells.items()):
        if cell.get("model_id") != model_id:
            continue
        variant_view = variant_cells.get(cell_id, {})
        rows.append({
            "cell_id": cell_id,
            "task_id": cell.get("task_id"),
            "status": cell.get("status"),
            "runnable": bool(cell.get("runnable")),
            "default_variant_id": variant_view.get("default_variant_id"),
            "variants": [
                {
                    "variant_id": item.get("variant_id"),
                    "mapping_id": item.get("mapping_id"),
                    "ansatz_policy_id": item.get("ansatz_policy_id"),
                    "cell_status": item.get("cell_status"),
                    "runnable": bool(item.get("runnable")),
                }
                for item in variant_view.get("variants", [])
            ],
        })
    return rows


def public_scientific_core_view(model_id: str) -> dict[str, Any]:
    contract = get_model_contract(model_id)
    classification = contract.classification
    return {
        "schema_version": SCIENTIFIC_CORE_VIEW_SCHEMA,
        "model_id": contract.model_id,
        "model_version": contract.model_version,
        "user_view": {
            "group_id": None if classification is None else classification.ui_group_id,
            "group_label": None if classification is None else classification.ui_group_label,
            "authority": "navigation_only",
            "may_drive_scientific_decisions": False,
        },
        "scientific_core": {
            "model_contract": {
                "physical_phenomenon": {
                    "value": list(contract.physical_phenomena),
                    "authoritative_owner_id": "owner.model_contract",
                },
                "degrees_of_freedom": {
                    "value": list(contract.degrees_of_freedom),
                    "authoritative_owner_id": "owner.model_contract",
                },
                "representation": {
                    "value": copy_plain_data(contract.representation_contract),
                    "authoritative_owner_id": "owner.model_contract",
                },
                "hamiltonian_components": {
                    "value": list(contract.hamiltonian_components),
                    "authoritative_owner_id": "owner.model_contract",
                },
                "sector_symmetries": {
                    "value": {
                        "model_sector_capability": {
                            "conserved_quantities": list(contract.conserved_quantities),
                            "sector_schema": copy_plain_data(contract.sector_schema),
                        },
                        "sector_representation_policy_id": contract.sector_policy_id,
                    },
                    "authoritative_owner_id": "owner.model_contract",
                    "component_owners": {
                        "model_sector_capability": "owner.model_contract",
                        "sector_representation_semantics": "owner.sector_policy",
                    },
                    "projection_mode": "read_only_from_authoritative_owners",
                },
                "encoding_mapping": {
                    "value": {
                        "declared_primary_mapping_policy_id": contract.mapping_policy_id,
                        "compatible_mapping_policy_ids": list(contract.compatible_mapping_ids),
                        "selected_mapping_is_realization_specific": True,
                    },
                    "authoritative_owner_id": "owner.mapping_policy",
                    "component_owners": {
                        "mapping_capability_declaration": "owner.model_contract",
                        "mapping_semantics": "owner.mapping_policy",
                        "realization_selection": "owner.capability_resolver",
                    },
                    "projection_mode": "read_only_from_authoritative_owners",
                },
                "supported_realizations": {
                    "value": _supported_realizations(model_id),
                    "authoritative_owner_id": "owner.capability_resolver",
                    "projection_mode": "read_only",
                },
            }
        },
        "classification": {
            "value": None if classification is None else classification.to_dict(),
            "authority": "descriptive_taxonomy_and_discovery_only",
            "excluded_from_scientific_identity": True,
        },
    }


def public_scientific_core_catalog() -> dict[str, Any]:
    return {
        "schema_version": "qcol-scientific-core-catalog/1.0",
        "user_navigation": public_user_navigation_catalog(),
        "models": [public_scientific_core_view(c.model_id) for c in list_model_contracts()],
        "rule": "Preserve a simple mentor-facing view without making the UI taxonomy an internal physics constraint.",
    }


__all__ = ["public_user_navigation_catalog", "public_scientific_core_view", "public_scientific_core_catalog"]
