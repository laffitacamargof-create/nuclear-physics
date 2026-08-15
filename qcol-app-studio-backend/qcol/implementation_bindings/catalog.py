"""Public WP3 catalogs, fingerprints, and validation gates."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from qcol.acceptance import baseline_fingerprint
from qcol.mapping_policies import PolicyStatus, vocabulary_fingerprint
from qcol.policy_contract_catalog import (
    build_wp2_contract_examples,
    policy_contract_catalog_fingerprint,
)

from .builtin import (
    build_wp3_example_registries,
    known_contract_missing_binding_requirement,
    recognized_not_executable_requirement,
)
from .contract_index import contract_identity, resolve_contracts
from .enums import BindingFailureCode


IMPLEMENTATION_BINDING_CATALOG_SCHEMA_VERSION = (
    "qcol-implementation-binding-catalog/1.0"
)
IMPLEMENTATION_BINDING_CATALOG_VERSION = "1.0.0"
WP3_INTRODUCED_PROJECT_VERSION = "1.11.0"
EXPECTED_WP0_FINGERPRINT = (
    "992f08c33a51de8c496cf7f894cbdbb4f8958eb2ddabe5b6021fc43e1d287e18"
)
EXPECTED_WP1_FINGERPRINT = (
    "2fbcfc375bf56621fd0c379ed695233d1e572b4ad8e4f57842678ef50c192c8d"
)
EXPECTED_WP2_FINGERPRINT = (
    "ccf69efaf5637aa40f810dd06a5df3d84d9e54c908ac41b4eeb78ee04eb54888"
)


def build_wp3_example_resolution_bundle() -> dict[str, Any]:
    contract_registry, binding_registry = build_wp3_example_registries()
    examples = build_wp2_contract_examples()
    contract_ids = tuple(contract_identity(item)[0] for item in examples.values())
    resolved_plan = resolve_contracts(
        contract_registry,
        binding_registry,
        contract_ids,
        plan_label="WP3 all-resolvable schema-fixture contracts",
    )
    missing = binding_registry.resolve(known_contract_missing_binding_requirement())
    unavailable = binding_registry.resolve(recognized_not_executable_requirement())
    return {
        "contract_registry": contract_registry,
        "binding_registry": binding_registry,
        "resolved_plan": resolved_plan,
        "missing_binding_resolution": missing,
        "recognized_not_executable_resolution": unavailable,
    }


def public_implementation_binding_catalog() -> dict[str, Any]:
    bundle = build_wp3_example_resolution_bundle()
    contract_registry = bundle["contract_registry"]
    binding_registry = bundle["binding_registry"]
    resolved_plan = bundle["resolved_plan"]
    missing = bundle["missing_binding_resolution"]
    unavailable = bundle["recognized_not_executable_resolution"]

    payload = {
        "schema_version": IMPLEMENTATION_BINDING_CATALOG_SCHEMA_VERSION,
        "catalog_version": IMPLEMENTATION_BINDING_CATALOG_VERSION,
        "introduced_in_project_version": WP3_INTRODUCED_PROJECT_VERSION,
        "phase": "Phase A.3.2a",
        "work_package": "WP3 — Registries and Implementation Bindings",
        "objective": (
            "Connect declarative contract IDs to exact versioned binding IDs "
            "and lazy callables without placing callables in contracts or evidence."
        ),
        "scientific_behavior_change": False,
        "live_policy_migration_performed": False,
        "silent_fallback_allowed": False,
        "public_contracts_contain_callables": False,
        "callable_payload_withheld": True,
        "contract_registry": contract_registry.public_catalog(),
        "binding_registry": binding_registry.public_catalog(),
        "resolved_example_plan": resolved_plan.to_public_dict(),
        "known_contract_missing_binding": missing.to_public_dict(),
        "recognized_not_executable_binding": unavailable.to_public_dict(),
        "preserved_foundation_fingerprints": {
            "wp0_baseline": baseline_fingerprint(),
            "wp1_vocabulary": vocabulary_fingerprint(),
            "wp2_declarative_contract_catalog": policy_contract_catalog_fingerprint(),
        },
        "guardrails": [
            {
                "id": "wp3.exact_binding_id_only.v1",
                "statement": "The registry resolves the exact binding ID and never searches for a substitute.",
            },
            {
                "id": "wp3.missing_is_recognized_not_executable.v1",
                "statement": "A known contract with an absent binding returns recognized_not_executable, not ImportError.",
            },
            {
                "id": "wp3.callables_withheld_from_public_views.v1",
                "statement": "Resolved plans expose provider/version/revision metadata, never callable objects.",
            },
            {
                "id": "wp3.no_live_policy_migration.v1",
                "statement": "Pair, JW, and BK live policy migration remains reserved for WP8–WP10.",
            },
        ],
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return json.loads(
        json.dumps(payload, sort_keys=True, allow_nan=False, ensure_ascii=False)
    )


def implementation_binding_catalog_fingerprint(
    payload: dict[str, Any] | None = None,
) -> str:
    catalog = dict(payload or public_implementation_binding_catalog())
    existing = catalog.pop("fingerprint", None)
    fingerprint = hashlib.sha256(
        json.dumps(
            catalog,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if existing is not None and existing != fingerprint:
        raise ValueError("Implementation-binding catalog fingerprint mismatch.")
    return fingerprint


def validate_implementation_binding_registry(
    payload: dict[str, Any] | None = None,
) -> dict[str, bool]:
    catalog = payload or public_implementation_binding_catalog()
    bundle = build_wp3_example_resolution_bundle()
    plan = bundle["resolved_plan"]
    missing = bundle["missing_binding_resolution"].report
    unavailable = bundle["recognized_not_executable_resolution"].report

    resolved_rows = plan.to_public_dict()["implementations"]
    metadata_complete = all(
        all(
            row["binding_metadata"].get(key)
            for key in (
                "provider",
                "binding_version",
                "implementation_version",
                "convention_id",
                "source_revision",
            )
        )
        for row in resolved_rows
    )
    no_callable_values = "callable_object" not in json.dumps(catalog, sort_keys=True)
    no_fallback = all(
        row["details"].get("silent_fallback_performed") is False
        for row in resolved_rows
    ) and missing.details.get("silent_fallback_performed") is False

    return {
        "strict_json_round_trip": (
            json.loads(json.dumps(catalog, allow_nan=False, sort_keys=True))
            == catalog
        ),
        "binding_catalog_fingerprint_valid": (
            implementation_binding_catalog_fingerprint(catalog)
            == catalog["fingerprint"]
        ),
        "all_wp2_example_requirements_resolve": plan.all_required_resolved,
        "resolved_metadata_complete": metadata_complete,
        "public_catalog_contains_no_callable_objects": no_callable_values,
        "callable_payload_withheld": catalog["callable_payload_withheld"] is True,
        "missing_binding_is_recognized_not_executable": (
            missing.code is BindingFailureCode.NOT_REGISTERED
            and missing.policy_status is PolicyStatus.RECOGNIZED_NOT_EXECUTABLE
            and not bundle["missing_binding_resolution"].executable
        ),
        "declared_unavailable_is_recognized_not_executable": (
            unavailable.code is BindingFailureCode.DECLARED_NOT_EXECUTABLE
            and unavailable.policy_status is PolicyStatus.RECOGNIZED_NOT_EXECUTABLE
            and not bundle["recognized_not_executable_resolution"].executable
        ),
        "no_silent_fallback": no_fallback,
        "wp0_fingerprint_preserved": (
            baseline_fingerprint() == EXPECTED_WP0_FINGERPRINT
        ),
        "wp1_fingerprint_preserved": (
            vocabulary_fingerprint() == EXPECTED_WP1_FINGERPRINT
        ),
        "wp2_fingerprint_preserved": (
            policy_contract_catalog_fingerprint() == EXPECTED_WP2_FINGERPRINT
        ),
        "live_policy_migration_not_performed": (
            catalog["live_policy_migration_performed"] is False
        ),
        "scientific_behavior_change_false": (
            catalog["scientific_behavior_change"] is False
        ),
    }


__all__ = [
    "IMPLEMENTATION_BINDING_CATALOG_SCHEMA_VERSION",
    "IMPLEMENTATION_BINDING_CATALOG_VERSION",
    "WP3_INTRODUCED_PROJECT_VERSION",
    "EXPECTED_WP0_FINGERPRINT",
    "EXPECTED_WP1_FINGERPRINT",
    "EXPECTED_WP2_FINGERPRINT",
    "build_wp3_example_resolution_bundle",
    "public_implementation_binding_catalog",
    "implementation_binding_catalog_fingerprint",
    "validate_implementation_binding_registry",
]
