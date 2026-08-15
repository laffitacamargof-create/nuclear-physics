"""Stable compatibility failure codes for QCOL mapping-realization decisions.

WP0 freezes the vocabulary used to describe known scientific incompatibilities.
The codes are transport-safe identifiers shared by reports, evidence, API/UI
surfaces, tests, and the deterministic advisor planned for Phase B.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


class CompatibilityFailureCode(str, Enum):
    MAPPING_DOMAIN_MISMATCH = "MAPPING_DOMAIN_MISMATCH"
    MISSING_MAPPING_METADATA = "MISSING_MAPPING_METADATA"
    MODE_ORDER_CONTEXT_MISMATCH = "MODE_ORDER_CONTEXT_MISMATCH"
    INITIAL_STATE_ENCODING_MISMATCH = "INITIAL_STATE_ENCODING_MISMATCH"
    TAPER_SECTOR_UNKNOWN = "TAPER_SECTOR_UNKNOWN"
    ANSATZ_GENERATOR_MAPPING_MISMATCH = "ANSATZ_GENERATOR_MAPPING_MISMATCH"
    SECTOR_REPRESENTATION_UNAVAILABLE = "SECTOR_REPRESENTATION_UNAVAILABLE"
    SECTOR_LEAKAGE_EXCEEDS_LIMIT = "SECTOR_LEAKAGE_EXCEEDS_LIMIT"
    TASK_OPERATOR_NOT_MAPPABLE = "TASK_OPERATOR_NOT_MAPPABLE"
    REFERENCE_SECTOR_MISMATCH = "REFERENCE_SECTOR_MISMATCH"
    CUSTOM_CODE_NONINJECTIVE = "CUSTOM_CODE_NONINJECTIVE"
    ACCEPTANCE_EVIDENCE_STALE = "ACCEPTANCE_EVIDENCE_STALE"
    RESOURCE_ENVELOPE_EXCEEDED = "RESOURCE_ENVELOPE_EXCEEDED"
    QASM_SEMANTIC_DRIFT = "QASM_SEMANTIC_DRIFT"


@dataclass(frozen=True)
class CompatibilityFailureSpec:
    code: CompatibilityFailureCode
    title: str
    message: str
    scope: str
    severity: str
    recoverable: bool
    suggested_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code.value,
            "title": self.title,
            "message": self.message,
            "scope": self.scope,
            "severity": self.severity,
            "recoverable": bool(self.recoverable),
            "suggested_action": self.suggested_action,
        }


_SPECS = {
    CompatibilityFailureCode.MAPPING_DOMAIN_MISMATCH: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.MAPPING_DOMAIN_MISMATCH,
        title="Mapping domain mismatch",
        message="The physical model lies outside the mapping policy's declared domain.",
        scope="model_mapping",
        severity="fatal",
        recoverable=True,
        suggested_action="Choose a mapping whose declared physical domain contains the model, or add a scientifically reviewed adapter.",
    ),
    CompatibilityFailureCode.MISSING_MAPPING_METADATA: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.MISSING_MAPPING_METADATA,
        title="Required mapping metadata is missing",
        message="The mapping cannot be interpreted reproducibly because required scientific metadata is absent.",
        scope="model_mapping",
        severity="fatal",
        recoverable=True,
        suggested_action="Declare the missing mode order, sector, convention, or physical-domain metadata before resolution.",
    ),
    CompatibilityFailureCode.MODE_ORDER_CONTEXT_MISMATCH: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.MODE_ORDER_CONTEXT_MISMATCH,
        title="Mode-order context mismatch",
        message="The Hamiltonian, mapping, state, ansatz, measurement, or reference use incompatible mode-order conventions.",
        scope="global_composition",
        severity="fatal",
        recoverable=True,
        suggested_action="Resolve one shared ordering context and rebuild every dependent artifact from it.",
    ),
    CompatibilityFailureCode.INITIAL_STATE_ENCODING_MISMATCH: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.INITIAL_STATE_ENCODING_MISMATCH,
        title="Initial-state encoding mismatch",
        message="The initial state was prepared for a different encoding, mapping convention, order, code space, or target sector.",
        scope="mapping_state",
        severity="fatal",
        recoverable=True,
        suggested_action="Use the encoder registered for the exact mapping convention and declared ordering context.",
    ),
    CompatibilityFailureCode.TAPER_SECTOR_UNKNOWN: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.TAPER_SECTOR_UNKNOWN,
        title="Tapering sector is unknown",
        message="Symmetry reduction was requested without a declared and verified symmetry eigen-sector.",
        scope="mapping_sector",
        severity="fatal",
        recoverable=True,
        suggested_action="Declare and verify the tapering eigenvalues before applying the reduction.",
    ),
    CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH,
        title="Ansatz generator does not implement the selected mapping",
        message=(
            "The circuit preserves particle number, but it does not implement "
            "the JW-mapped nonadjacent fermionic generator."
        ),
        scope="mapping_ansatz",
        severity="fatal",
        recoverable=True,
        suggested_action=(
            "Use generators mapped with the selected policy, a fermionic-swap construction, "
            "or provide mapping-native generator-equivalence evidence."
        ),
    ),
    CompatibilityFailureCode.SECTOR_REPRESENTATION_UNAVAILABLE: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.SECTOR_REPRESENTATION_UNAVAILABLE,
        title="Sector representation unavailable",
        message="The selected mapping does not provide an accepted representation or diagnostic for the requested conserved quantity.",
        scope="mapping_sector",
        severity="fatal",
        recoverable=True,
        suggested_action="Choose a mapping with a registered sector profile or add a verified mapped observable/projector.",
    ),
    CompatibilityFailureCode.SECTOR_LEAKAGE_EXCEEDS_LIMIT: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.SECTOR_LEAKAGE_EXCEEDS_LIMIT,
        title="Sector leakage exceeds the declared limit",
        message="The realized circuit leaves the declared physical sector beyond the accepted tolerance.",
        scope="composition",
        severity="fatal",
        recoverable=True,
        suggested_action="Use a sector-preserving realization or tighten the state/ansatz construction before execution.",
    ),
    CompatibilityFailureCode.TASK_OPERATOR_NOT_MAPPABLE: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.TASK_OPERATOR_NOT_MAPPABLE,
        title="Task operator cannot be mapped",
        message="At least one Hamiltonian, observable, penalty, generator, or evolution operator required by the task cannot be transformed consistently.",
        scope="mapping_task",
        severity="fatal",
        recoverable=True,
        suggested_action="Select a compatible mapping or implement and accept the missing task-operator transformation.",
    ),
    CompatibilityFailureCode.REFERENCE_SECTOR_MISMATCH: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.REFERENCE_SECTOR_MISMATCH,
        title="Reference does not match the resolved physical problem",
        message="The reference uses a different Hamiltonian, ordering, units, constant shift, sector, quantity, or validity range.",
        scope="model_task_reference",
        severity="fatal",
        recoverable=True,
        suggested_action="Rebuild an independent reference from the same source-domain problem and declared sector.",
    ),
    CompatibilityFailureCode.CUSTOM_CODE_NONINJECTIVE: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.CUSTOM_CODE_NONINJECTIVE,
        title="Custom code is non-injective",
        message="Two valid physical states encode to the same qubit state in the declared domain.",
        scope="custom_mapping",
        severity="fatal",
        recoverable=False,
        suggested_action="Redesign the encoder or narrow its declared physical domain before promotion.",
    ),
    CompatibilityFailureCode.ACCEPTANCE_EVIDENCE_STALE: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.ACCEPTANCE_EVIDENCE_STALE,
        title="Acceptance evidence is stale",
        message="A policy, implementation, dependency, ordering context, task, or declared scale changed after the acceptance evidence was produced.",
        scope="acceptance",
        severity="fatal",
        recoverable=True,
        suggested_action="Rerun the exact acceptance suite and issue a new evidence fingerprint.",
    ),
    CompatibilityFailureCode.RESOURCE_ENVELOPE_EXCEEDED: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.RESOURCE_ENVELOPE_EXCEEDED,
        title="Resource envelope exceeded",
        message="The combination is scientifically meaningful but outside the currently declared executable scale.",
        scope="resources",
        severity="review",
        recoverable=True,
        suggested_action="Reduce the declared problem scale, change the realization, or expand and reaccept the resource envelope.",
    ),
    CompatibilityFailureCode.QASM_SEMANTIC_DRIFT: CompatibilityFailureSpec(
        code=CompatibilityFailureCode.QASM_SEMANTIC_DRIFT,
        title="QASM semantic drift",
        message="Translation or unrolling changed the accepted circuit's state or task expectation beyond tolerance.",
        scope="translation",
        severity="fatal",
        recoverable=True,
        suggested_action="Inspect unsupported gates or decomposition rules and rebuild the QASM2-safe circuit.",
    ),
}


def get_failure_spec(code: CompatibilityFailureCode | str) -> CompatibilityFailureSpec:
    normalized = code if isinstance(code, CompatibilityFailureCode) else CompatibilityFailureCode(str(code))
    return _SPECS[normalized]


def public_failure_code_registry() -> Dict[str, Any]:
    return {
        "schema_version": "qcol-compatibility-failure-codes/1.0",
        "codes": [spec.to_dict() for spec in _SPECS.values()],
    }


def validate_failure_code_registry() -> Dict[str, bool]:
    codes = [spec.code.value for spec in _SPECS.values()]
    return {
        "all_enum_values_registered": set(codes) == {item.value for item in CompatibilityFailureCode},
        "codes_unique": len(codes) == len(set(codes)),
        "messages_nonempty": all(spec.message.strip() for spec in _SPECS.values()),
        "suggested_actions_nonempty": all(spec.suggested_action.strip() for spec in _SPECS.values()),
        "jw_negative_fixture_code_present": CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH in _SPECS,
    }
