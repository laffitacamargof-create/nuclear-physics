"""Public catalog and validation for the WP1 shared vocabulary."""
from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Iterable, Mapping, TypeVar

from .enums import (
    EXPORTED_ENUMS,
    AlgebraScope,
    AnsatzSemanticClass,
    CheckStatus,
    DecisionStatus,
    EvidenceFreshnessStatus,
    GateApplicability,
    MappingFamily,
    MappingScope,
    PolicyStatus,
    SectorRepresentationKind,
    Severity,
)
from .primitives import LegacyVocabularyTranslation, VocabularyEntry


VOCABULARY_SCHEMA_VERSION = "qcol-mapping-realization-vocabulary/1.0"
VOCABULARY_VERSION = "1.0.0"

EnumT = TypeVar("EnumT", bound=StrEnum)


_DESCRIPTIONS: dict[type[StrEnum], dict[StrEnum, tuple[str, str]]] = {
    MappingFamily: {
        MappingFamily.JORDAN_WIGNER: (
            "Jordan–Wigner",
            "Full-mode fermion-to-qubit family with direct ordered-mode occupation semantics and parity strings.",
        ),
        MappingFamily.BRAVYI_KITAEV: (
            "Bravyi–Kitaev",
            "Full-mode fermion-to-qubit family with distributed occupation, parity, and update information.",
        ),
        MappingFamily.PARITY: (
            "Parity",
            "Fermionic family that stores cumulative parity and requires explicit ordering and reduction-sector declarations.",
        ),
        MappingFamily.PAIR: (
            "Pair mapping",
            "Restricted pair-occupation family; it must not be presented as a general single-fermion mapping.",
        ),
        MappingFamily.CUSTOM: (
            "Custom encoding",
            "Explicitly declared code/encoding whose domain, injectivity, algebra, and proof obligations are supplied separately.",
        ),
    },
    MappingScope: {
        MappingScope.FULL_FERMIONIC_FOCK_SPACE: (
            "Full fermionic Fock space",
            "The mapping represents all declared individual fermionic modes in the full finite Fock space.",
        ),
        MappingScope.RESTRICTED_PHYSICAL_SUBSPACE: (
            "Restricted physical subspace",
            "The mapping is valid only after a declared physical restriction such as seniority zero.",
        ),
        MappingScope.SYMMETRY_REDUCED_SUBSPACE: (
            "Symmetry-reduced subspace",
            "The encoded space is reduced by declared symmetries whose sector values are part of the contract.",
        ),
        MappingScope.TAPERED_SUBSPACE: (
            "Tapered subspace",
            "Qubits are removed only after verified symmetry eigenvalues and ordering assumptions are fixed.",
        ),
        MappingScope.CUSTOM_CODE_SPACE: (
            "Custom code space",
            "The mapping acts through an explicit encoder/projector/isometry on a declared code space.",
        ),
    },
    AlgebraScope: {
        AlgebraScope.CANONICAL_ANTICOMMUTATION_RELATIONS: (
            "Canonical anticommutation relations",
            "Individual fermionic creation and annihilation operators must preserve CAR on the declared encoded space.",
        ),
        AlgebraScope.QUASISPIN_PAIR_ALGEBRA: (
            "Quasispin / hard-core pair algebra",
            "Pair-level operators are verified in the declared paired subspace rather than against full single-fermion CAR.",
        ),
        AlgebraScope.ENCODED_SUBSPACE_OPERATOR_ALGEBRA: (
            "Encoded-subspace operator algebra",
            "Operator action is guaranteed only after projection into the explicitly declared physical/code subspace.",
        ),
        AlgebraScope.CUSTOM_DECLARED_ALGEBRA: (
            "Custom declared algebra",
            "A custom policy supplies a named algebra and its complete conformance tests.",
        ),
    },
    PolicyStatus: {
        PolicyStatus.REGISTERED: ("Registered", "The asset is known to the registry; no execution claim is implied."),
        PolicyStatus.RECOGNIZED: ("Recognized", "The input or policy is understood, but further resolution is required."),
        PolicyStatus.NOT_IMPLEMENTED: ("Not implemented", "The declared path has no implementation binding in this release."),
        PolicyStatus.PLANNED: ("Planned", "The capability is declared on the roadmap but is not executable."),
        PolicyStatus.FUTURE: ("Future", "The capability is registered for future work without current execution support."),
        PolicyStatus.UNRESOLVED: ("Unresolved", "Scientific or implementation requirements have not yet been resolved."),
        PolicyStatus.RECOGNIZED_NOT_EXECUTABLE: ("Recognized, not executable", "The route is understood but one or more required capabilities are missing."),
        PolicyStatus.EXPERIMENTAL: ("Experimental", "The route can run within explicit limits but scientific promotion is incomplete."),
        PolicyStatus.EXECUTABLE: ("Executable", "The route can execute, without implying acceptance verification."),
        PolicyStatus.EXECUTION_READY: ("Execution ready", "All required implementation bindings exist; promotion evidence may still be incomplete."),
        PolicyStatus.VERIFIED: ("Verified", "A component-level declared claim has passed its relevant conformance checks."),
        PolicyStatus.ACCEPTANCE_VERIFIED: ("Acceptance verified", "The exact declared policy/composition/cell passed its versioned acceptance suite."),
        PolicyStatus.UNSUPPORTED: ("Unsupported", "The request lies outside the declared scientific or resource scope."),
        PolicyStatus.DEPRECATED: ("Deprecated", "The asset remains identifiable for evidence replay but should not be selected for new runs."),
    },
    CheckStatus: {
        CheckStatus.PASS: ("Pass", "The declared check succeeded with sufficient evidence."),
        CheckStatus.REVIEW: ("Review", "The check completed but requires bounded review or additional evidence."),
        CheckStatus.FAIL: ("Fail", "The declared condition was violated."),
        CheckStatus.NOT_RUN: ("Not run", "The check has not executed."),
        CheckStatus.NOT_APPLICABLE: ("Not applicable", "The check is outside the declared task/variant and is not counted as a pass."),
        CheckStatus.BLOCKED: ("Blocked", "An upstream failure or missing prerequisite prevented the check from running."),
    },
    Severity: {
        Severity.INFO: ("Information", "Context or provenance; no action is required."),
        Severity.WARNING: ("Warning", "The condition is non-fatal but should remain visible."),
        Severity.REVIEW: ("Review", "A human/scientific decision is required before promotion."),
        Severity.ERROR: ("Error", "The operation or check failed but the issue may be recoverable."),
        Severity.FATAL: ("Fatal", "The realization must not enter runtime or be promoted."),
    },
    GateApplicability: {
        GateApplicability.REQUIRED: ("Required", "This gate must pass for the declared variant."),
        GateApplicability.OPTIONAL: ("Optional", "The gate may provide extra evidence but is not a universal promotion condition."),
        GateApplicability.NOT_APPLICABLE: ("Not applicable", "The gate does not exist for this task/variant and must not be reported as pass."),
        GateApplicability.BLOCKED: ("Blocked", "The gate is required but cannot start until an upstream prerequisite is resolved."),
    },
    AnsatzSemanticClass: {
        AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR: (
            "Mapped fermionic generator",
            "The ansatz begins from a fermionic generator mapped by the selected convention and requires generator/circuit equivalence evidence.",
        ),
        AnsatzSemanticClass.MAPPING_NATIVE_VERIFIED: (
            "Mapping-native verified",
            "The circuit is defined directly in the encoded qubit space and is accepted only for named mapping/order/sector evidence.",
        ),
        AnsatzSemanticClass.QUBIT_NATIVE: (
            "Qubit native",
            "The circuit makes no automatic fermionic-excitation claim; Hamming-weight preservation alone is insufficient.",
        ),
    },
    SectorRepresentationKind: {
        SectorRepresentationKind.DIRECT_POPCOUNT: (
            "Direct popcount",
            "The conserved quantity is the raw Hamming weight of the declared qubit register.",
        ),
        SectorRepresentationKind.LOCAL_DIAGONAL_OPERATOR: (
            "Local diagonal operator",
            "The conserved quantity is represented by a sum/product of local diagonal qubit operators.",
        ),
        SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR: (
            "Non-local mapped operator",
            "The conserved quantity requires a mapping-specific non-local qubit operator or decoder; raw popcount is invalid.",
        ),
        SectorRepresentationKind.CODE_SPACE_PROJECTOR: (
            "Code-space projector",
            "Membership is tested with a declared projector, stabilizer, or code-space diagnostic.",
        ),
        SectorRepresentationKind.FIXED_BY_PHYSICAL_DOMAIN: (
            "Fixed by physical domain",
            "The quantity is fixed by the declared reduced domain rather than independently represented by qubit bits.",
        ),
        SectorRepresentationKind.UNSUPPORTED: (
            "Unsupported",
            "The mapping supplies no accepted representation or diagnostic for this conserved quantity.",
        ),
    },
    EvidenceFreshnessStatus: {
        EvidenceFreshnessStatus.CURRENT: ("Current", "The evidence fingerprint matches the exact resolved variant and scale."),
        EvidenceFreshnessStatus.STALE: ("Stale", "A policy, convention, dependency, tolerance, or scale changed after evidence was issued."),
        EvidenceFreshnessStatus.MISSING: ("Missing", "No acceptance evidence exists for the exact resolved variant."),
        EvidenceFreshnessStatus.UNKNOWN: ("Unknown", "Evidence exists but its fingerprint cannot yet be evaluated."),
        EvidenceFreshnessStatus.NOT_APPLICABLE: ("Not applicable", "The declared task/claim does not require acceptance evidence of this kind."),
    },
    DecisionStatus: {
        DecisionStatus.ACCEPT: ("Accept", "The bounded decision accepts the exact declared claim."),
        DecisionStatus.REJECT: ("Reject", "The bounded decision rejects the exact declared claim."),
        DecisionStatus.REVIEW: ("Review", "The evidence is insufficient for automatic acceptance or rejection."),
        DecisionStatus.INCONCLUSIVE: ("Inconclusive", "The result cannot distinguish the alternatives under the declared uncertainty."),
        DecisionStatus.DEFER: ("Defer", "The decision is postponed until required evidence or implementation is available."),
        DecisionStatus.NOT_APPLICABLE: ("Not applicable", "No decision of this type applies to the task/variant."),
    },
}


_LEGACY_TRANSLATIONS = (
    LegacyVocabularyTranslation(
        raw_value="verified_for_transform",
        target_enum="PolicyStatus",
        target_value=PolicyStatus.VERIFIED.value,
        qualifier="transform_only",
        rationale="Preserve the scoped transform claim without presenting the complete mapping realization as universally verified.",
    ),
    LegacyVocabularyTranslation(
        raw_value="acceptance_verified_for_analysis",
        target_enum="PolicyStatus",
        target_value=PolicyStatus.ACCEPTANCE_VERIFIED.value,
        qualifier="analysis_only",
        rationale="The accepted claim is the mapping-analysis cell, not state preparation or VQE execution.",
    ),
    LegacyVocabularyTranslation(
        raw_value="not_verified",
        target_enum="PolicyStatus",
        target_value=PolicyStatus.RECOGNIZED_NOT_EXECUTABLE.value,
        qualifier="composition_failed_or_missing",
        rationale="A cell that has not passed acceptance must not be exposed as executable merely because its mapper exists.",
    ),
    LegacyVocabularyTranslation(
        raw_value="failed",
        target_enum="CheckStatus",
        target_value=CheckStatus.FAIL.value,
        qualifier="legacy_conformance_result",
        rationale="Failure is a check outcome, not a universal policy lifecycle status.",
    ),
    LegacyVocabularyTranslation(
        raw_value="not_applicable",
        target_enum="CheckStatus",
        target_value=CheckStatus.NOT_APPLICABLE.value,
        qualifier="gate_or_check",
        rationale="A non-applicable gate is not counted as a pass.",
    ),
)


_SCIENTIFIC_GUARDRAILS = (
    {
        "guardrail_id": "ansatz.hamming_weight_is_not_fermionic_semantics.v1",
        "weak_property": "particle_or_hamming_weight_preserving",
        "forbidden_inference": AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR.value,
        "required_evidence": "mapped_generator_or_mapping_native_equivalence",
        "statement": (
            "Preserving Hamming weight or particle number does not by itself "
            "establish a fermionic excitation ansatz."
        ),
    },
    {
        "guardrail_id": "sector.raw_popcount_is_not_universal_particle_number.v1",
        "weak_property": SectorRepresentationKind.DIRECT_POPCOUNT.value,
        "forbidden_inference": "particle_number_under_every_mapping",
        "required_evidence": SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR.value,
        "statement": (
            "Raw qubit popcount represents particle number only when the exact "
            "mapping/sector profile declares direct-popcount semantics."
        ),
    },
)


_DIRECT_LEGACY_POLICY_VALUES = {
    "registered",
    "recognized",
    "not_implemented",
    "planned",
    "future",
    "unresolved",
    "recognized_not_executable",
    "experimental",
    "executable",
    "execution_ready",
    "verified",
    "acceptance_verified",
    "unsupported",
}
_DIRECT_LEGACY_CHECK_VALUES = {
    "pass",
    "review",
    "fail",
    "not_run",
    "not_applicable",
    "blocked",
}


def coerce_enum(enum_type: type[EnumT], value: EnumT | str) -> EnumT:
    """Return a typed enum member or raise a clear value error."""
    if isinstance(value, enum_type):
        return value
    return enum_type(str(value))


def enum_entries(enum_type: type[EnumT]) -> list[VocabularyEntry]:
    descriptions = _DESCRIPTIONS[enum_type]
    return [
        VocabularyEntry(
            enum_name=enum_type.__name__,
            member_name=member.name,
            value=member.value,
            label=descriptions[member][0],
            description=descriptions[member][1],
        )
        for member in enum_type
    ]


def public_mapping_realization_vocabulary() -> dict[str, Any]:
    payload = {
        "schema_version": VOCABULARY_SCHEMA_VERSION,
        "vocabulary_version": VOCABULARY_VERSION,
        "scope": "Phase A.3.2a WP1 — shared declarations only",
        "scientific_behavior_change": False,
        "enums": {
            enum_type.__name__: {
                "values": [entry.to_dict() for entry in enum_entries(enum_type)]
            }
            for enum_type in EXPORTED_ENUMS
        },
        "scientific_guardrails": [dict(item) for item in _SCIENTIFIC_GUARDRAILS],
        "legacy_translations": [item.to_dict() for item in _LEGACY_TRANSLATIONS],
        "notes": [
            "WP1 exports vocabulary; policy contracts begin in WP2.",
            "No callable or scientific runtime implementation is stored here.",
            "Not-applicable gates are not counted as passes.",
            "Scoped legacy phrases remain explicit translations rather than universal statuses.",
        ],
    }
    return payload


def vocabulary_fingerprint(payload: Mapping[str, Any] | None = None) -> str:
    value = dict(payload or public_mapping_realization_vocabulary())
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _all_values(enum_types: Iterable[type[StrEnum]]) -> dict[str, set[str]]:
    return {item.__name__: {member.value for member in item} for item in enum_types}


def validate_mapping_realization_vocabulary(
    payload: Mapping[str, Any] | None = None,
    *,
    raise_on_error: bool = False,
) -> dict[str, bool]:
    public = dict(payload or public_mapping_realization_vocabulary())
    values = _all_values(EXPORTED_ENUMS)
    enum_payload = public.get("enums", {})
    translations = {item.raw_value: item for item in _LEGACY_TRANSLATIONS}

    descriptor_values = {
        enum_name: {
            str(item["value"])
            for item in enum_payload.get(enum_name, {}).get("values", [])
        }
        for enum_name in values
    }
    direct_policy_values = values[PolicyStatus.__name__]
    direct_check_values = values[CheckStatus.__name__]

    checks = {
        "schema_version": public.get("schema_version") == VOCABULARY_SCHEMA_VERSION,
        "vocabulary_version": public.get("vocabulary_version") == VOCABULARY_VERSION,
        "no_scientific_behavior_change": public.get("scientific_behavior_change") is False,
        "all_required_enums_exported": set(enum_payload) == {item.__name__ for item in EXPORTED_ENUMS},
        "enum_values_unique": all(
            len({member.value for member in enum_type}) == len(list(enum_type))
            for enum_type in EXPORTED_ENUMS
        ),
        "descriptors_complete": all(descriptor_values[name] == expected for name, expected in values.items()),
        "all_enum_members_are_strings": all(
            isinstance(member.value, str)
            for enum_type in EXPORTED_ENUMS
            for member in enum_type
        ),
        "json_roundtrip": False,
        "hamming_weight_not_fermionic_semantics": (
            AnsatzSemanticClass.QUBIT_NATIVE
            != AnsatzSemanticClass.MAPPED_FERMIONIC_GENERATOR
            and "Hamming" in _DESCRIPTIONS[AnsatzSemanticClass][AnsatzSemanticClass.QUBIT_NATIVE][1]
        ),
        "raw_popcount_not_universal_particle_number": (
            SectorRepresentationKind.DIRECT_POPCOUNT
            != SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR
            and "raw popcount is invalid" in _DESCRIPTIONS[SectorRepresentationKind][SectorRepresentationKind.NONLOCAL_MAPPED_OPERATOR][1]
        ),
        "legacy_policy_values_covered": _DIRECT_LEGACY_POLICY_VALUES <= direct_policy_values,
        "legacy_check_values_covered": _DIRECT_LEGACY_CHECK_VALUES <= direct_check_values,
        "scoped_legacy_values_have_explicit_translation": {
            "verified_for_transform",
            "acceptance_verified_for_analysis",
            "not_verified",
            "failed",
            "not_applicable",
        } <= set(translations),
        "failure_registry_severities_covered": {"fatal", "review"} <= values[Severity.__name__],
        "gate_not_applicable_is_not_pass": CheckStatus.NOT_APPLICABLE.value != CheckStatus.PASS.value,
    }

    try:
        checks["json_roundtrip"] = json.loads(json.dumps(public, sort_keys=True)) == public
    except (TypeError, ValueError):
        checks["json_roundtrip"] = False

    if raise_on_error and not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise AssertionError(
            "Mapping-realization vocabulary validation failed: " + ", ".join(failed)
        )
    return checks


__all__ = [
    "VOCABULARY_SCHEMA_VERSION",
    "VOCABULARY_VERSION",
    "coerce_enum",
    "enum_entries",
    "public_mapping_realization_vocabulary",
    "vocabulary_fingerprint",
    "validate_mapping_realization_vocabulary",
]
