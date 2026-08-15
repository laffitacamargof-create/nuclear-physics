"""Dependency-light predicate implementations for the nine WP4 rules.

Each predicate consumes a :class:`RuleEvaluationContext` and returns a
:class:`PredicateResult`.  It reports facts only; the rule contract supplies the
stable failure code, severity, and default suggested action.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from qcol.mapping_policies import CheckStatus, SectorRepresentationKind

from .rule_contracts import PredicateResult, RuleEvaluationContext


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    return {str(item) for item in value}


def _mapping(context: RuleEvaluationContext, name: str) -> Mapping[str, Any]:
    value = context.component(name)
    return value if isinstance(value, Mapping) else {}


def evaluate_model_mapping_domain(*, context: RuleEvaluationContext) -> PredicateResult:
    model = _mapping(context, "model")
    mapping = _mapping(context, "mapping")
    accepted_operator_types = _tokens(mapping.get("accepted_operator_types"))
    allowed_domains = _tokens(mapping.get("allowed_physical_domains"))
    required_metadata = _tokens(mapping.get("required_model_metadata"))
    model_metadata = model.get("metadata", {})
    if not isinstance(model_metadata, Mapping):
        model_metadata = {}
    missing_metadata = sorted(required_metadata - set(map(str, model_metadata.keys())))
    required_symmetries = _tokens(mapping.get("required_symmetries"))
    declared_symmetries = _tokens(model.get("verified_symmetries")) | _tokens(
        model.get("declared_symmetries")
    )

    checks = {
        "operator_type_supported": model.get("operator_type") in accepted_operator_types,
        "physical_domain_supported": model.get("physical_domain") in allowed_domains,
        "required_metadata_present": not missing_metadata,
        "hermiticity_satisfied": (
            not bool(mapping.get("requires_hermitian_hamiltonian", False))
            or bool(model.get("hermitian", False))
        ),
        "required_symmetries_present": required_symmetries <= declared_symmetries,
    }
    passed = all(checks.values())
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "The model lies inside the mapping's declared operator and physical domain."
            if passed
            else "The model does not satisfy the mapping's declared domain obligations."
        ),
        evidence={
            "model_id": model.get("model_id"),
            "mapping_policy_id": mapping.get("policy_id"),
            "checks": checks,
            "missing_metadata": missing_metadata,
            "required_symmetries": sorted(required_symmetries),
            "declared_or_verified_symmetries": sorted(declared_symmetries),
        },
    )


def evaluate_ordering_same_context(*, context: RuleEvaluationContext) -> PredicateResult:
    ordering = _mapping(context, "ordering")
    expected = ordering.get("encoding_context_fingerprint")
    component_fingerprints = ordering.get("component_context_fingerprints", {})
    if not isinstance(component_fingerprints, Mapping):
        component_fingerprints = {}
    normalized = {
        str(name): str(value)
        for name, value in component_fingerprints.items()
        if value is not None and str(value).strip()
    }
    missing_components = sorted(
        str(item) for item in ordering.get("required_components", ())
        if str(item) not in normalized
    )
    mismatches = {
        name: value
        for name, value in normalized.items()
        if expected is None or value != expected
    }
    passed = bool(expected) and not missing_components and not mismatches
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "All declared components share one EncodingContext fingerprint."
            if passed
            else "The resolved tuple contains missing or conflicting ordering contexts."
        ),
        evidence={
            "expected_encoding_context_fingerprint": expected,
            "component_context_fingerprints": normalized,
            "missing_components": missing_components,
            "mismatches": mismatches,
        },
    )


def evaluate_mapping_sector_representation(*, context: RuleEvaluationContext) -> PredicateResult:
    task = _mapping(context, "task")
    mapping = _mapping(context, "mapping")
    sector = _mapping(context, "sector")
    required_quantities = _tokens(task.get("required_conserved_quantities")) | _tokens(
        sector.get("required_quantities")
    )
    profiles_raw = mapping.get("sector_profiles", ())
    profiles: dict[str, Mapping[str, Any]] = {}
    if isinstance(profiles_raw, (list, tuple)):
        for item in profiles_raw:
            if isinstance(item, Mapping) and item.get("quantity_id"):
                profiles[str(item["quantity_id"])] = item

    missing: list[str] = []
    invalid: dict[str, Any] = {}
    for quantity in sorted(required_quantities):
        profile = profiles.get(quantity)
        if profile is None:
            missing.append(quantity)
            continue
        kind = str(profile.get("representation_kind", ""))
        diagnostic = str(profile.get("diagnostic_policy_id", "") or "")
        domain_evidence = bool(profile.get("fixed_by_domain_evidence", False))
        supported = kind != SectorRepresentationKind.UNSUPPORTED.value
        diagnostically_defined = (
            bool(diagnostic)
            or kind == SectorRepresentationKind.FIXED_BY_PHYSICAL_DOMAIN.value
            and domain_evidence
        )
        if not supported or not diagnostically_defined:
            invalid[quantity] = {
                "representation_kind": kind,
                "diagnostic_policy_id": diagnostic or None,
                "fixed_by_domain_evidence": domain_evidence,
            }

    passed = not missing and not invalid
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "Every required conserved quantity has an explicit accepted sector representation."
            if passed
            else "At least one required conserved quantity lacks an accepted representation or diagnostic."
        ),
        evidence={
            "required_quantities": sorted(required_quantities),
            "available_profiles": {
                key: _plain(value) for key, value in sorted(profiles.items())
            },
            "missing_quantities": missing,
            "invalid_profiles": invalid,
            "raw_popcount_claim": mapping.get("raw_popcount_is_particle_number"),
        },
    )


def evaluate_mapping_state_encoder_match(*, context: RuleEvaluationContext) -> PredicateResult:
    task = _mapping(context, "task")
    if not bool(task.get("requires_state_preparation", False)):
        return PredicateResult(
            status=CheckStatus.NOT_APPLICABLE,
            message="This task does not require a state-preparation composition.",
            evidence={"task_id": task.get("task_id")},
        )

    mapping = _mapping(context, "mapping")
    state = _mapping(context, "state_preparation")
    required = _tokens(mapping.get("requires_state_capabilities"))
    provided = _tokens(state.get("provided_capabilities"))
    checks = {
        "mapping_policy_id_matches": state.get("mapping_policy_id") == mapping.get("policy_id"),
        "mapping_convention_matches": state.get("mapping_convention_id") == mapping.get("convention_id"),
        "encoding_context_matches": state.get("encoding_context_fingerprint") == mapping.get("encoding_context_fingerprint"),
        "required_capabilities_present": required <= provided,
        "state_in_code_space": bool(state.get("encoded_state_in_code_space", False)),
        "target_sector_matches": bool(state.get("target_sector_match", False)),
    }
    passed = all(checks.values())
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "The initial state uses the exact mapping convention, code space, order, and target sector."
            if passed
            else "The initial state does not match the resolved mapping encoding or target sector."
        ),
        evidence={
            "checks": checks,
            "required_capabilities": sorted(required),
            "provided_capabilities": sorted(provided),
            "state_policy_id": state.get("policy_id"),
            "mapping_policy_id": mapping.get("policy_id"),
        },
    )


def evaluate_mapping_ansatz_generator_semantics(*, context: RuleEvaluationContext) -> PredicateResult:
    task = _mapping(context, "task")
    if not bool(task.get("requires_ansatz", False)):
        return PredicateResult(
            status=CheckStatus.NOT_APPLICABLE,
            message="This task does not require an ansatz composition.",
            evidence={"task_id": task.get("task_id")},
        )

    mapping = _mapping(context, "mapping")
    ansatz = _mapping(context, "ansatz")
    required = _tokens(mapping.get("requires_ansatz_capabilities"))
    provided = _tokens(ansatz.get("provided_capabilities"))
    equivalence = ansatz.get("generator_equivalence_evidence", {})
    if not isinstance(equivalence, Mapping):
        equivalence = {}
    evidence_required = "mapped_generator_semantics" in required
    equivalence_ok = (
        not evidence_required
        or bool(equivalence.get("passed", False))
        and str(equivalence.get("freshness_status", "")) == "current"
    )
    checks = {
        "mapping_policy_id_matches": ansatz.get("mapping_policy_id") == mapping.get("policy_id"),
        "mapping_convention_matches": ansatz.get("mapping_convention_id") == mapping.get("convention_id"),
        "encoding_context_matches": ansatz.get("encoding_context_fingerprint") == mapping.get("encoding_context_fingerprint"),
        "required_capabilities_present": required <= provided,
        "generator_equivalence_current_and_passed": equivalence_ok,
        "declared_invariants_preserved": bool(ansatz.get("declared_invariants_preserved", False)),
    }
    passed = all(checks.values())
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "The ansatz implements the selected mapping's generator semantics and declared invariants."
            if passed
            else "The ansatz preserves some invariants but does not satisfy the selected mapping's generator semantics."
        ),
        evidence={
            "checks": checks,
            "semantic_class": ansatz.get("semantic_class"),
            "required_capabilities": sorted(required),
            "provided_capabilities": sorted(provided),
            "generator_equivalence_evidence": _plain(equivalence),
            "particle_number_preserving": ansatz.get("particle_number_preserving"),
            "hamming_weight_preserving": ansatz.get("hamming_weight_preserving"),
            "nonadjacent_sign_test_passed": ansatz.get("nonadjacent_sign_test_passed"),
        },
    )


def evaluate_mapping_task_all_operators_mapped(*, context: RuleEvaluationContext) -> PredicateResult:
    task = _mapping(context, "task")
    mapping = _mapping(context, "mapping")
    required = _tokens(task.get("required_operator_kinds"))
    supported = _tokens(mapping.get("transformable_operator_kinds"))
    missing = sorted(required - supported)
    passed = not missing
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "The mapping can transform the Hamiltonian and every operator required by the task."
            if passed
            else "At least one task operator cannot be transformed under the selected mapping."
        ),
        evidence={
            "task_id": task.get("task_id"),
            "required_operator_kinds": sorted(required),
            "transformable_operator_kinds": sorted(supported),
            "missing_operator_kinds": missing,
        },
    )


def evaluate_model_task_reference_same_problem(*, context: RuleEvaluationContext) -> PredicateResult:
    model = _mapping(context, "model")
    task = _mapping(context, "task")
    ordering = _mapping(context, "ordering")
    sector = _mapping(context, "sector")
    reference = _mapping(context, "reference")
    if not reference:
        return PredicateResult(
            status=CheckStatus.FAIL,
            message="The resolved tuple has no declared independent reference.",
            evidence={"task_id": task.get("task_id")},
        )

    model_scale = model.get("declared_scale", {})
    validity = reference.get("validity_envelope", {})
    if not isinstance(model_scale, Mapping):
        model_scale = {}
    if not isinstance(validity, Mapping):
        validity = {}
    max_modes = validity.get("max_n_modes")
    n_modes = model_scale.get("n_modes")
    scale_ok = True
    if isinstance(max_modes, int) and isinstance(n_modes, int):
        scale_ok = n_modes <= max_modes

    checks = {
        "source_problem_matches": reference.get("source_problem_fingerprint") == model.get("source_problem_fingerprint"),
        "task_matches": reference.get("task_id") == task.get("task_id"),
        "quantity_matches": reference.get("quantity_id") == task.get("target_quantity"),
        "units_match": reference.get("units") == model.get("units") == task.get("units"),
        "ordering_matches": reference.get("encoding_context_fingerprint") == ordering.get("encoding_context_fingerprint"),
        "sector_matches": reference.get("sector_fingerprint") == sector.get("sector_fingerprint"),
        "scale_within_validity": scale_ok,
        "independent_reference": bool(reference.get("independent", False)),
        "not_constructed_from_tested_mapping": not bool(reference.get("constructed_from_tested_mapping", True)),
        "constant_shift_recorded": reference.get("constant_shift") is not None,
    }
    passed = all(checks.values())
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "The reference solves the same source problem, task quantity, ordering, sector, units, and scale independently of the tested mapping."
            if passed
            else "The reference does not match the resolved source problem or is not independent of the tested mapping."
        ),
        evidence={
            "checks": checks,
            "model_source_problem_fingerprint": model.get("source_problem_fingerprint"),
            "reference_source_problem_fingerprint": reference.get("source_problem_fingerprint"),
            "model_scale": _plain(model_scale),
            "reference_validity_envelope": _plain(validity),
        },
    )


def evaluate_composition_resource_envelope(*, context: RuleEvaluationContext) -> PredicateResult:
    resources = _mapping(context, "resources")
    within = bool(resources.get("within_declared_envelope", False))
    if within:
        return PredicateResult(
            status=CheckStatus.PASS,
            message="The resolved tuple is inside its declared resource envelope.",
            evidence={
                "estimate": _plain(resources.get("estimate", {})),
                "envelope": _plain(resources.get("envelope", {})),
            },
        )
    return PredicateResult(
        status=CheckStatus.REVIEW,
        message="The tuple is scientifically meaningful but exceeds the currently declared executable resource envelope.",
        evidence={
            "estimate": _plain(resources.get("estimate", {})),
            "envelope": _plain(resources.get("envelope", {})),
            "exceeded_dimensions": _plain(resources.get("exceeded_dimensions", [])),
        },
        suggested_action=(
            "Reduce the declared scale, choose a lower-cost realization, or extend and reaccept the resource envelope."
        ),
    )


def evaluate_composition_acceptance_fingerprint(*, context: RuleEvaluationContext) -> PredicateResult:
    acceptance = _mapping(context, "acceptance_evidence")
    expected = acceptance.get("resolved_variant_fingerprint")
    actual = acceptance.get("evidence_fingerprint")
    freshness = str(acceptance.get("freshness_status", ""))
    checks = {
        "fingerprint_present": bool(expected) and bool(actual),
        "fingerprint_matches": bool(expected) and expected == actual,
        "evidence_current": freshness == "current",
        "policy_versions_match": bool(acceptance.get("policy_versions_match", False)),
        "declared_scale_matches": bool(acceptance.get("declared_scale_matches", False)),
    }
    passed = all(checks.values())
    return PredicateResult(
        status=CheckStatus.PASS if passed else CheckStatus.FAIL,
        message=(
            "Acceptance evidence matches the exact resolved policy tuple and declared scale."
            if passed
            else "Acceptance evidence is missing, stale, or belongs to a different resolved tuple or scale."
        ),
        evidence={
            "checks": checks,
            "resolved_variant_fingerprint": expected,
            "evidence_fingerprint": actual,
            "freshness_status": freshness or None,
        },
    )


__all__ = [
    "evaluate_model_mapping_domain",
    "evaluate_ordering_same_context",
    "evaluate_mapping_sector_representation",
    "evaluate_mapping_state_encoder_match",
    "evaluate_mapping_ansatz_generator_semantics",
    "evaluate_mapping_task_all_operators_mapped",
    "evaluate_model_task_reference_same_problem",
    "evaluate_composition_resource_envelope",
    "evaluate_composition_acceptance_fingerprint",
]
