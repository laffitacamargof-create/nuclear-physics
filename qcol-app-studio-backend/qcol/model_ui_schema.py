"""Schema-driven model-input descriptions shared by Browser and Gradio UIs.

The public UI schema is derived from :class:`ModelContract.parameter_schema`.
It contains no Hamiltonian or runtime logic.  Fixed and hidden parameters are
retained in the contract and injected at the ModelInstance boundary rather than
rendered as user controls.
"""
from __future__ import annotations

import json
from typing import Any, Mapping

from .model_contracts import ModelContract, ModelContractError, ParameterSpec
from .model_registry import get_model_contract
from .models.qho_common import QHO_MODEL_IDS
from .request_boundaries import copy_plain_data

MODEL_UI_SCHEMA_VERSION = "qcol-model-ui-schema/1.2"
QHO_UI_CATALOG_VERSION = "qcol-qho-ui-catalog/1.2"


def _display_value(value: Any) -> str:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _ui_input_kind(spec: ParameterSpec) -> str:
    if spec.kind == "integer":
        return "integer"
    if spec.kind == "number":
        return "number"
    if spec.kind in {"vector_or_scalar", "matrix_or_scalar"}:
        return "structured_number"
    return "text"


def _field_payload(spec: ParameterSpec) -> dict[str, Any]:
    payload = spec.to_dict()
    payload.update(
        {
            "ui_input_kind": _ui_input_kind(spec),
            "render": bool(spec.visible and spec.role == "editable"),
            "default_display": _display_value(spec.default),
        }
    )
    return payload


def public_model_ui_schema(model_id: str) -> dict[str, Any]:
    contract = get_model_contract(model_id)
    from .scientific_core import public_scientific_core_view
    fields = [_field_payload(item) for item in sorted(contract.parameter_schema, key=lambda x: x.order)]
    for item in fields:
        item["parameter_namespace"] = "model_parameters"
        item["authoritative_owner_id"] = "owner.model_contract"
        item["ui_projection_only"] = True
    return {
        "schema_version": MODEL_UI_SCHEMA_VERSION,
        "model_id": contract.model_id,
        "model_version": contract.model_version,
        "label": contract.label,
        "description": contract.description,
        # ``family`` is retained as a backward-compatible navigation alias.
        # It is never a scientific or resource authority.
        "family": contract.family,
        "family_authority": "navigation_and_grouping_only",
        "classification": (
            contract.classification.to_dict()
            if contract.classification is not None
            else None
        ),
        "ui_group": (
            {
                "id": contract.classification.ui_group_id,
                "label": contract.classification.ui_group_label,
                "authority": "navigation_and_grouping_only",
            }
            if contract.classification is not None
            else {
                "id": contract.family,
                "label": contract.family,
                "authority": "navigation_and_grouping_only",
            }
        ),
        "problem_type": contract.problem_type,
        "support_status": contract.support_status,
        "execution_status": contract.execution_status,
        "parameter_fields": fields,
        "rendered_parameter_keys": [item["key"] for item in fields if item["render"]],
        "fixed_parameters": {
            item.key: copy_plain_data(item.fixed_value)
            for item in contract.parameter_schema
            if item.role == "fixed"
        },
        "hidden_defaults": {
            item.key: copy_plain_data(item.default)
            for item in contract.parameter_schema
            if item.role == "editable" and not item.visible and item.default is not None
        },
        "policies": contract.to_dict()["policies"],
        "reference_validity": contract.reference_validity.to_dict(),
        "resource_validity": contract.resource_validity.to_dict(),
        "assumptions": list(contract.assumptions),
        "limitations": list(contract.limitations),
        "schema_driven": True,
        "semantic_authority": {
            "ui_owner_id": "owner.ui",
            "resource_owner_id": "owner.resource_assessor",
            "ansatz_parameterization_owner_id": "owner.ansatz_policy",
            "ui_may_infer_scientific_or_resource_semantics": False,
            "resource_values_are_read_only_views": True,
        },
        "scientific_core": public_scientific_core_view(model_id)["scientific_core"],
        "parameter_namespace_ownership": {
            "model_parameters": "owner.model_contract",
            "variational_parameters": "owner.ansatz_policy",
            "task_controller_parameters": "owner.task_contract",
            "execution_parameters": "owner.execution_target",
        },
        "callable_payload_withheld": True,
    }


def public_qho_ui_catalog() -> dict[str, Any]:
    models = [public_model_ui_schema(model_id) for model_id in QHO_MODEL_IDS]
    return {
        "schema_version": QHO_UI_CATALOG_VERSION,
        "ui_group_id": "nuclear_vibrations",
        "ui_group_label": "Oscillators",
        # Backward-compatible aliases; navigation only.
        "family_id": "oscillator",
        "family_label": "Oscillators",
        "family_authority": "navigation_and_grouping_only",
        "default_model_id": QHO_MODEL_IDS[0],
        "model_ids": list(QHO_MODEL_IDS),
        "models": models,
        "model_schema_endpoint": "/catalog/model-contracts/{model_id}",
        "ui_schema_endpoint": "/catalog/model-ui-schemas/{model_id}",
        "interface_rule": (
            "Render only fields with role=editable and visible=true; fixed values "
            "are injected by the model contract at the instance boundary. The UI "
            "must not derive parameter counts, mappings, sectors, ansatz semantics, "
            "task compatibility, or resource formulas from a family/group label."
        ),
        "semantic_authority_invariant": (
            "UI asks and renders; contracts declare; policies own local semantics; "
            "the resolver composes; ResourceAssessor derives; Evidence proves identity."
        ),
        "shared_realization_family": {
            "hamiltonian_policy_id": "hard_core_oscillator_hamiltonian.v1",
            "mapping_policy_id": "direct_hard_core_mode_encoding.v1",
            "sector_policy_id": "one_excitation_sector.v1",
            "state_preparation_policy_id": "lowest_mode_state.v1",
            "ansatz_policy_id": "one_excitation_chain_givens.v1",
            "reference_policy_id": "small_exact_one_excitation_sector.v1",
            "runtime_policy_id": "external_variational_energy.v1",
        },
        "run_pipeline_changed": False,
        "second_runtime_created": False,
    }


def visible_parameter_keys(model_id: str) -> tuple[str, ...]:
    schema = public_model_ui_schema(model_id)
    return tuple(schema["rendered_parameter_keys"])


def _coerce_scalar_or_vector(raw: Any, *, field: str) -> float | list[float]:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (list, tuple)):
        values = [float(item) for item in raw]
        if not values:
            raise ModelContractError(f"{field} must not be empty.")
        return values[0] if len(values) == 1 else values
    text = str(raw).strip()
    if not text:
        raise ModelContractError(f"{field} must not be empty.")
    if text.startswith("["):
        decoded = json.loads(text)
        if isinstance(decoded, list) and decoded and all(not isinstance(x, list) for x in decoded):
            values = [float(item) for item in decoded]
            return values[0] if len(values) == 1 else values
        raise ModelContractError(f"{field} must be a scalar or one-dimensional vector.")
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ModelContractError(f"{field} must not be empty.")
    return values[0] if len(values) == 1 else values


def _coerce_matrix_or_scalar(raw: Any, *, field: str) -> float | list[list[float]]:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (list, tuple)):
        if raw and all(isinstance(row, (list, tuple)) for row in raw):
            return [[float(item) for item in row] for row in raw]
        values = [float(item) for item in raw]
        if len(values) == 1:
            return values[0]
        raise ModelContractError(f"{field} must be a scalar or square matrix.")
    text = str(raw).strip()
    if not text:
        raise ModelContractError(f"{field} must not be empty.")
    if text.startswith("["):
        decoded = json.loads(text)
        if isinstance(decoded, list) and decoded and all(isinstance(row, list) for row in decoded):
            return [[float(item) for item in row] for row in decoded]
        if isinstance(decoded, (int, float)):
            return float(decoded)
        raise ModelContractError(f"{field} must be a scalar or square matrix.")
    return float(text)


def coerce_model_ui_parameters(model_id: str, raw_values: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce user-visible values according to the selected ModelContract.

    Fixed fields are not accepted from the UI and are injected by the normal
    ModelInstance adapter.  Hidden editable fields use their declared defaults.
    """
    contract: ModelContract = get_model_contract(model_id)
    specs = {item.key: item for item in contract.parameter_schema}
    allowed = {item.key for item in contract.parameter_schema if item.role == "editable" and item.visible}
    unknown = set(raw_values) - allowed
    if unknown:
        raise ModelContractError(
            f"UI supplied parameters not rendered by {model_id!r}: {sorted(unknown)}"
        )
    result: dict[str, Any] = {}
    for key in sorted(allowed, key=lambda item: specs[item].order):
        spec = specs[key]
        raw = raw_values.get(key, spec.default)
        if spec.kind == "integer":
            value = int(raw)
        elif spec.kind == "number":
            value = float(raw)
        elif spec.kind == "vector_or_scalar":
            value = _coerce_scalar_or_vector(raw, field=key)
        elif spec.kind == "matrix_or_scalar":
            value = _coerce_matrix_or_scalar(raw, field=key)
        else:
            value = str(raw)
        if spec.minimum is not None and isinstance(value, (int, float)) and value < spec.minimum:
            raise ModelContractError(f"{key} must be >= {spec.minimum}.")
        if spec.maximum is not None and isinstance(value, (int, float)) and value > spec.maximum:
            raise ModelContractError(f"{key} must be <= {spec.maximum}.")
        result[key] = value
    for spec in contract.parameter_schema:
        if spec.role == "editable" and not spec.visible and spec.default is not None:
            result[spec.key] = spec.default
    return result


def validate_qho_ui_catalog() -> dict[str, bool]:
    expected = {
        "nuclear.qho.free": ("n_modes", "omega"),
        "nuclear.qho.pairing": ("n_modes", "omega", "coupling"),
        "nuclear.qho.spinorbit": ("n_modes", "omega", "kappa"),
        "nuclear.qho.full": ("n_modes", "omega", "coupling", "kappa"),
    }
    actual = {model_id: visible_parameter_keys(model_id) for model_id in QHO_MODEL_IDS}
    catalog = public_qho_ui_catalog()
    policy_sets = {
        tuple(sorted(item["policies"].items()))
        for item in catalog["models"]
    }
    return {
        "all_four_models_present": tuple(catalog["model_ids"]) == QHO_MODEL_IDS,
        "field_sets_match_contracts": actual == expected,
        "fixed_interactions_not_rendered": all(
            key not in actual[model_id]
            for model_id, key in (
                ("nuclear.qho.free", "coupling"),
                ("nuclear.qho.free", "kappa"),
                ("nuclear.qho.pairing", "kappa"),
                ("nuclear.qho.spinorbit", "coupling"),
            )
        ),
        "same_shared_policy_family": len(policy_sets) == 1,
        "no_second_runtime": catalog["second_runtime_created"] is False,
        "run_pipeline_unchanged": catalog["run_pipeline_changed"] is False,
        "family_is_navigation_only": catalog["family_authority"] == "navigation_and_grouping_only",
        "ui_is_display_only_for_resources": all(
            item["semantic_authority"]["ui_may_infer_scientific_or_resource_semantics"] is False
            for item in catalog["models"]
        ),
    }


__all__ = [
    "MODEL_UI_SCHEMA_VERSION",
    "QHO_UI_CATALOG_VERSION",
    "public_model_ui_schema",
    "public_qho_ui_catalog",
    "visible_parameter_keys",
    "coerce_model_ui_parameters",
    "validate_qho_ui_catalog",
]
