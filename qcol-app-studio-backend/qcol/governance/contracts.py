"""Declarative governance and Phase B handoff contracts for WP13.

WP13 treats policies, compatibility rules, acceptance evidence, and published
support states as governed scientific assets.  These frozen contracts contain
no callables and are safe to archive as strict JSON.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from qcol.mapping_policies import CheckStatus, DecisionStatus
from qcol.realization_policies.base import (
    DeclarativeContract,
    PolicyContractError,
    freeze_json,
    require_text,
    require_token,
)

from .enums import (
    DeprecationStatus,
    EvidenceTreatment,
    GovernedAssetKind,
    HandoffStatus,
    MigrationKind,
    OwnerType,
    PatchOperation,
    PatchValueType,
)


SCIENTIFIC_OWNER_SCHEMA_VERSION = "qcol-scientific-owner-contract/1.0"
GOVERNED_ASSET_SCHEMA_VERSION = "qcol-governed-scientific-asset/1.0"
EVIDENCE_OWNERSHIP_SCHEMA_VERSION = "qcol-acceptance-evidence-ownership/1.0"
DEPRECATION_RULE_SCHEMA_VERSION = "qcol-deprecation-rule/1.0"
MIGRATION_RULE_SCHEMA_VERSION = "qcol-migration-rule/1.0"
PUBLISHED_STATUS_SCHEMA_VERSION = "qcol-published-scientific-status/1.0"
ALLOWED_PATCH_SCHEMA_VERSION = "qcol-allowed-request-patch/1.0"
PATCH_CANDIDATE_SCHEMA_VERSION = "qcol-request-patch-candidate/1.0"
PATCH_VALIDATION_SCHEMA_VERSION = "qcol-request-patch-validation-report/1.0"
PHASE_B_HANDOFF_SCHEMA_VERSION = "qcol-phase-b-handoff-contract/1.0"


RELEASE_GATE_ATTESTATION_SCHEMA_VERSION = "qcol-release-gate-attestation/1.0"
A32C_RELEASE_DECISION_SCHEMA_VERSION = "qcol-a3-2c-release-decision/1.0"
GOVERNANCE_RELEASE_MANIFEST_SCHEMA_VERSION = "qcol-governance-release-manifest/1.0"


@dataclass(frozen=True)
class ScientificOwnerContract(DeclarativeContract):
    owner_id: str
    label: str
    owner_type: OwnerType
    scope: tuple[str, ...]
    responsibilities: tuple[str, ...]
    approval_authorities: tuple[str, ...]
    limitation_review_required: bool = True
    schema_version: str = SCIENTIFIC_OWNER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("owner_id", self.owner_id)
        require_text("label", self.label)
        if not isinstance(self.owner_type, OwnerType):
            raise PolicyContractError("owner_type must be OwnerType.")
        scope = tuple(require_token("scope", str(item)) for item in self.scope)
        if not scope:
            raise PolicyContractError("scope must not be empty.")
        object.__setattr__(self, "scope", scope)
        responsibilities = tuple(
            require_text("responsibilities", str(item)) for item in self.responsibilities
        )
        if not responsibilities:
            raise PolicyContractError("responsibilities must not be empty.")
        object.__setattr__(self, "responsibilities", responsibilities)
        authorities = tuple(
            require_token("approval_authorities", str(item))
            for item in self.approval_authorities
        )
        if not authorities:
            raise PolicyContractError("approval_authorities must not be empty.")
        object.__setattr__(self, "approval_authorities", authorities)


@dataclass(frozen=True)
class GovernedAssetRecord(DeclarativeContract):
    asset_id: str
    asset_kind: GovernedAssetKind
    contract_schema_id: str
    contract_schema_version: str
    asset_version: str
    implementation_binding_ids: tuple[str, ...]
    implementation_version: str | None
    scientific_owner_id: str
    acceptance_evidence_owner_id: str | None
    published_status: str
    limitation_statement: str
    validity_envelope: Mapping[str, Any] = field(default_factory=dict)
    deprecation_rule_id: str | None = None
    migration_rule_ids: tuple[str, ...] = field(default_factory=tuple)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = GOVERNED_ASSET_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("asset_id", self.asset_id)
        if not isinstance(self.asset_kind, GovernedAssetKind):
            raise PolicyContractError("asset_kind must be GovernedAssetKind.")
        require_token("contract_schema_id", self.contract_schema_id)
        require_text("contract_schema_version", self.contract_schema_version)
        require_token("asset_version", self.asset_version)
        bindings = tuple(
            require_token("implementation_binding_ids", str(item))
            for item in self.implementation_binding_ids
        )
        if len(set(bindings)) != len(bindings):
            raise PolicyContractError("implementation_binding_ids contains duplicates.")
        object.__setattr__(self, "implementation_binding_ids", bindings)
        if self.implementation_version is not None:
            require_token("implementation_version", self.implementation_version)
        require_token("scientific_owner_id", self.scientific_owner_id)
        if self.acceptance_evidence_owner_id is not None:
            require_token("acceptance_evidence_owner_id", self.acceptance_evidence_owner_id)
        require_token("published_status", self.published_status)
        require_text("limitation_statement", self.limitation_statement)
        if self.deprecation_rule_id is not None:
            require_token("deprecation_rule_id", self.deprecation_rule_id)
        migrations = tuple(
            require_token("migration_rule_ids", str(item))
            for item in self.migration_rule_ids
        )
        object.__setattr__(self, "migration_rule_ids", migrations)
        object.__setattr__(
            self,
            "validity_envelope",
            freeze_json(self.validity_envelope, path="GovernedAssetRecord.validity_envelope"),
        )
        object.__setattr__(
            self,
            "provenance",
            freeze_json(self.provenance, path="GovernedAssetRecord.provenance"),
        )


@dataclass(frozen=True)
class AcceptanceEvidenceOwnershipContract(DeclarativeContract):
    evidence_asset_id: str
    evidence_schema_id: str
    evidence_schema_version: str
    scientific_owner_id: str
    custodian_owner_id: str
    promotion_authority_owner_id: str
    published_claim_id: str
    fingerprint_required: bool
    retention_policy: str
    regeneration_command: str
    revocation_conditions: tuple[str, ...]
    supersession_policy: str
    schema_version: str = EVIDENCE_OWNERSHIP_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "evidence_asset_id",
            "evidence_schema_id",
            "scientific_owner_id",
            "custodian_owner_id",
            "promotion_authority_owner_id",
            "published_claim_id",
        ):
            require_token(label, getattr(self, label))
        require_text("evidence_schema_version", self.evidence_schema_version)
        require_text("retention_policy", self.retention_policy)
        require_text("regeneration_command", self.regeneration_command)
        conditions = tuple(
            require_text("revocation_conditions", str(item))
            for item in self.revocation_conditions
        )
        if not conditions:
            raise PolicyContractError("revocation_conditions must not be empty.")
        object.__setattr__(self, "revocation_conditions", conditions)
        require_text("supersession_policy", self.supersession_policy)


@dataclass(frozen=True)
class DeprecationRuleContract(DeclarativeContract):
    rule_id: str
    asset_id: str
    status: DeprecationStatus
    announced_in_release: str
    earliest_removal_release: str | None
    replacement_asset_id: str | None
    warning_code: str
    migration_required: bool
    preserve_as_regression_fixture: bool
    acceptance_evidence_treatment: EvidenceTreatment
    notes: str
    schema_version: str = DEPRECATION_RULE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("rule_id", self.rule_id)
        require_token("asset_id", self.asset_id)
        if not isinstance(self.status, DeprecationStatus):
            raise PolicyContractError("status must be DeprecationStatus.")
        require_token("announced_in_release", self.announced_in_release)
        if self.earliest_removal_release is not None:
            require_token("earliest_removal_release", self.earliest_removal_release)
        if self.replacement_asset_id is not None:
            require_token("replacement_asset_id", self.replacement_asset_id)
        require_token("warning_code", self.warning_code)
        if not isinstance(self.acceptance_evidence_treatment, EvidenceTreatment):
            raise PolicyContractError(
                "acceptance_evidence_treatment must be EvidenceTreatment."
            )
        require_text("notes", self.notes)


@dataclass(frozen=True)
class MigrationRuleContract(DeclarativeContract):
    migration_id: str
    source_asset_id: str
    source_version: str
    target_asset_id: str
    target_version: str
    migration_kind: MigrationKind
    semantic_scope: str
    automatic: bool
    evidence_treatment: EvidenceTreatment
    requires_revalidation: bool
    failure_code_on_invalid: str
    notes: str
    schema_version: str = MIGRATION_RULE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "migration_id",
            "source_asset_id",
            "source_version",
            "target_asset_id",
            "target_version",
            "failure_code_on_invalid",
        ):
            require_token(label, getattr(self, label))
        if not isinstance(self.migration_kind, MigrationKind):
            raise PolicyContractError("migration_kind must be MigrationKind.")
        if not isinstance(self.evidence_treatment, EvidenceTreatment):
            raise PolicyContractError("evidence_treatment must be EvidenceTreatment.")
        require_text("semantic_scope", self.semantic_scope)
        require_text("notes", self.notes)


@dataclass(frozen=True)
class PublishedScientificStatusRecord(DeclarativeContract):
    record_id: str
    variant_id: str
    model_id: str
    task_id: str
    mapping_policy_id: str
    mapper_status: str
    composition_status: str
    cell_status: str
    runtime_status: str
    runnable: bool
    selectable: bool
    support_boundary: str
    evidence_fingerprint: str | None
    declared_scale: Mapping[str, Any]
    source_record_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    unqualified_mapping_verified_badge: bool = False
    schema_version: str = PUBLISHED_STATUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "record_id",
            "variant_id",
            "model_id",
            "task_id",
            "mapping_policy_id",
            "mapper_status",
            "composition_status",
            "cell_status",
            "runtime_status",
        ):
            require_token(label, getattr(self, label))
        require_text("support_boundary", self.support_boundary)
        if self.evidence_fingerprint is not None:
            require_token("evidence_fingerprint", self.evidence_fingerprint)
        source_ids = tuple(
            require_token("source_record_ids", str(item)) for item in self.source_record_ids
        )
        if not source_ids:
            raise PolicyContractError("source_record_ids must not be empty.")
        object.__setattr__(self, "source_record_ids", source_ids)
        limitations = tuple(
            require_text("limitations", str(item)) for item in self.limitations
        )
        if not limitations:
            raise PolicyContractError("limitations must not be empty.")
        object.__setattr__(self, "limitations", limitations)
        object.__setattr__(
            self,
            "declared_scale",
            freeze_json(self.declared_scale, path="PublishedScientificStatusRecord.declared_scale"),
        )
        if self.unqualified_mapping_verified_badge:
            raise PolicyContractError(
                "WP13 forbids one unconditional 'mapping verified' badge."
            )


@dataclass(frozen=True)
class AllowedRequestPatchContract(DeclarativeContract):
    patch_rule_id: str
    field_path: str
    operation: PatchOperation
    applies_to_variant_ids: tuple[str, ...]
    applies_to_task_ids: tuple[str, ...]
    value_type: PatchValueType
    allowed_values: tuple[Any, ...] = field(default_factory=tuple)
    minimum: float | int | None = None
    maximum: float | int | None = None
    source_constraints: tuple[str, ...] = field(default_factory=tuple)
    forbidden_sources: tuple[str, ...] = field(default_factory=tuple)
    preconditions: tuple[str, ...] = field(default_factory=tuple)
    requires_user_approval: bool = True
    requires_resolver_rerun: bool = True
    requires_pipeline_rerun: bool = True
    requires_new_evidence: bool = True
    may_mutate_problem_artifact: bool = False
    may_mutate_evidence: bool = False
    may_mutate_verification: bool = False
    reason_codes: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    schema_version: str = ALLOWED_PATCH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("patch_rule_id", self.patch_rule_id)
        if not isinstance(self.field_path, str) or not self.field_path.startswith("/"):
            raise PolicyContractError("field_path must be a JSON-pointer-like absolute path.")
        if not isinstance(self.operation, PatchOperation):
            raise PolicyContractError("operation must be PatchOperation.")
        if not isinstance(self.value_type, PatchValueType):
            raise PolicyContractError("value_type must be PatchValueType.")
        variants = tuple(
            require_token("applies_to_variant_ids", str(item))
            for item in self.applies_to_variant_ids
        )
        tasks = tuple(
            require_token("applies_to_task_ids", str(item))
            for item in self.applies_to_task_ids
        )
        if not variants or not tasks:
            raise PolicyContractError(
                "applies_to_variant_ids and applies_to_task_ids must not be empty."
            )
        object.__setattr__(self, "applies_to_variant_ids", variants)
        object.__setattr__(self, "applies_to_task_ids", tasks)
        object.__setattr__(
            self,
            "allowed_values",
            freeze_json(self.allowed_values, path="AllowedRequestPatchContract.allowed_values"),
        )
        for name in ("source_constraints", "forbidden_sources", "preconditions"):
            values = tuple(require_text(name, str(item)) for item in getattr(self, name))
            object.__setattr__(self, name, values)
        reasons = tuple(require_token("reason_codes", str(item)) for item in self.reason_codes)
        if not reasons:
            raise PolicyContractError("reason_codes must not be empty.")
        object.__setattr__(self, "reason_codes", reasons)
        require_text("description", self.description)
        if (
            self.may_mutate_problem_artifact
            or self.may_mutate_evidence
            or self.may_mutate_verification
        ):
            raise PolicyContractError(
                "Advisor patches may not mutate ProblemArtifact, Evidence, or Verification."
            )


@dataclass(frozen=True)
class RequestPatchCandidate(DeclarativeContract):
    patch_id: str
    target_variant_id: str
    task_id: str
    field_path: str
    operation: PatchOperation
    proposed_value: Any
    source: str
    source_run_id: str | None = None
    same_variant_fingerprint: bool | None = None
    schema_version: str = PATCH_CANDIDATE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("patch_id", self.patch_id)
        require_token("target_variant_id", self.target_variant_id)
        require_token("task_id", self.task_id)
        if not isinstance(self.field_path, str) or not self.field_path.startswith("/"):
            raise PolicyContractError("field_path must be a JSON-pointer-like path.")
        if not isinstance(self.operation, PatchOperation):
            raise PolicyContractError("operation must be PatchOperation.")
        object.__setattr__(
            self,
            "proposed_value",
            freeze_json(self.proposed_value, path="RequestPatchCandidate.proposed_value"),
        )
        require_text("source", self.source)
        if self.source_run_id is not None:
            require_token("source_run_id", self.source_run_id)


@dataclass(frozen=True)
class RequestPatchValidationReport(DeclarativeContract):
    report_id: str
    patch_id: str
    status: CheckStatus
    decision: DecisionStatus
    code: str
    message: str
    matched_rule_id: str | None
    evidence: Mapping[str, Any]
    suggested_action: str | None
    requires_user_approval: bool
    requires_resolver_rerun: bool
    requires_pipeline_rerun: bool
    requires_new_evidence: bool
    mutation_performed: bool = False
    hypothesis_only: bool = True
    schema_version: str = PATCH_VALIDATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        require_token("report_id", self.report_id)
        require_token("patch_id", self.patch_id)
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        if not isinstance(self.decision, DecisionStatus):
            raise PolicyContractError("decision must be DecisionStatus.")
        require_token("code", self.code)
        require_text("message", self.message)
        if self.matched_rule_id is not None:
            require_token("matched_rule_id", self.matched_rule_id)
        if self.suggested_action is not None:
            require_text("suggested_action", self.suggested_action)
        object.__setattr__(
            self,
            "evidence",
            freeze_json(self.evidence, path="RequestPatchValidationReport.evidence"),
        )
        if self.mutation_performed:
            raise PolicyContractError("WP13 patch validation must never mutate the request.")


@dataclass(frozen=True)
class PhaseBHandoffContract(DeclarativeContract):
    handoff_id: str
    handoff_version: str
    status: HandoffStatus
    compatibility_report_schema_version: str
    resource_report_schema_version: str
    request_patch_schema_version: str
    allowed_patch_registry_id: str
    allowed_patch_registry_fingerprint: str
    advisor_context_readable_fields: tuple[str, ...]
    advisor_context_forbidden_fields: tuple[str, ...]
    forbidden_mutations: tuple[str, ...]
    recommendation_status: str
    user_approval_required: bool
    same_pipeline_required: bool
    verification_retains_final_authority: bool
    phase_b_may_start: bool
    phase_b_advisor_runtime_implemented: bool
    limitations: tuple[str, ...]
    schema_version: str = PHASE_B_HANDOFF_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "handoff_id",
            "handoff_version",
            "allowed_patch_registry_id",
            "allowed_patch_registry_fingerprint",
            "recommendation_status",
        ):
            require_token(label, getattr(self, label))
        require_text("compatibility_report_schema_version", self.compatibility_report_schema_version)
        require_text("resource_report_schema_version", self.resource_report_schema_version)
        require_text("request_patch_schema_version", self.request_patch_schema_version)
        if not isinstance(self.status, HandoffStatus):
            raise PolicyContractError("status must be HandoffStatus.")
        for name in (
            "advisor_context_readable_fields",
            "advisor_context_forbidden_fields",
            "forbidden_mutations",
            "limitations",
        ):
            values = tuple(require_text(name, str(item)) for item in getattr(self, name))
            if not values:
                raise PolicyContractError(f"{name} must not be empty.")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class ReleaseGateAttestation(DeclarativeContract):
    gate_id: str
    gate_kind: str
    status: CheckStatus
    source_record_id: str
    evidence_fingerprint: str
    message: str
    schema_version: str = RELEASE_GATE_ATTESTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in ("gate_id", "gate_kind", "source_record_id", "evidence_fingerprint"):
            require_token(label, getattr(self, label))
        if not isinstance(self.status, CheckStatus):
            raise PolicyContractError("status must be CheckStatus.")
        require_text("message", self.message)


@dataclass(frozen=True)
class A32CReleaseDecision(DeclarativeContract):
    release_id: str
    release_version: str
    project_version: str
    resolved_variant_id: str
    gate_attestations: tuple[ReleaseGateAttestation, ...]
    fingerprint_match: bool
    evidence_reproducible: bool
    published_cell_status: str
    phase_a3_2c_exit_ready: bool
    phase_b_handoff_ready: bool
    phase_b_advisor_runtime_implemented: bool
    second_runtime_created: bool
    foundation_fingerprints: Mapping[str, Any]
    limitations: tuple[str, ...]
    schema_version: str = A32C_RELEASE_DECISION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in ("release_id", "release_version", "project_version", "resolved_variant_id", "published_cell_status"):
            require_token(label, getattr(self, label))
        gates = tuple(self.gate_attestations)
        if len(gates) != 3:
            raise PolicyContractError("A.3.2c release requires exactly three gate attestations.")
        if not all(isinstance(item, ReleaseGateAttestation) for item in gates):
            raise PolicyContractError("gate_attestations must contain ReleaseGateAttestation objects.")
        object.__setattr__(self, "gate_attestations", gates)
        object.__setattr__(
            self,
            "foundation_fingerprints",
            freeze_json(self.foundation_fingerprints, path="A32CReleaseDecision.foundation_fingerprints"),
        )
        limits = tuple(require_text("limitations", str(item)) for item in self.limitations)
        if not limits:
            raise PolicyContractError("limitations must not be empty.")
        object.__setattr__(self, "limitations", limits)
        expected_ready = (
            all(item.status is CheckStatus.PASS for item in gates)
            and self.fingerprint_match
            and self.evidence_reproducible
            and not self.second_runtime_created
        )
        if self.phase_a3_2c_exit_ready != expected_ready:
            raise PolicyContractError("phase_a3_2c_exit_ready does not match its governed release conditions.")
        if self.published_cell_status == "acceptance_verified" and not expected_ready:
            raise PolicyContractError("acceptance_verified may be published only after all release gates pass.")
        if self.phase_b_handoff_ready and not expected_ready:
            raise PolicyContractError("Phase B handoff cannot be ready before A.3.2c release conditions pass.")


@dataclass(frozen=True)
class GovernanceReleaseManifest(DeclarativeContract):
    manifest_id: str
    manifest_version: str
    project_version: str
    governance_catalog_fingerprint: str
    allowed_patch_registry_fingerprint: str
    release_decision_fingerprint: str
    schema_versions: Mapping[str, Any]
    implementation_versions: Mapping[str, Any]
    evidence_archive_id: str
    evidence_reproducible: bool
    callable_payload_withheld: bool
    python_pickling_used: bool
    second_runtime_created: bool
    schema_version: str = GOVERNANCE_RELEASE_MANIFEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for label in (
            "manifest_id",
            "manifest_version",
            "project_version",
            "governance_catalog_fingerprint",
            "allowed_patch_registry_fingerprint",
            "release_decision_fingerprint",
            "evidence_archive_id",
        ):
            require_token(label, getattr(self, label))
        object.__setattr__(
            self,
            "schema_versions",
            freeze_json(self.schema_versions, path="GovernanceReleaseManifest.schema_versions"),
        )
        object.__setattr__(
            self,
            "implementation_versions",
            freeze_json(self.implementation_versions, path="GovernanceReleaseManifest.implementation_versions"),
        )
        if self.python_pickling_used:
            raise PolicyContractError("WP13 release evidence must be pickle-free.")
        if self.second_runtime_created:
            raise PolicyContractError("WP13 governance cannot create a second runtime.")


__all__ = [
    "SCIENTIFIC_OWNER_SCHEMA_VERSION",
    "GOVERNED_ASSET_SCHEMA_VERSION",
    "EVIDENCE_OWNERSHIP_SCHEMA_VERSION",
    "DEPRECATION_RULE_SCHEMA_VERSION",
    "MIGRATION_RULE_SCHEMA_VERSION",
    "PUBLISHED_STATUS_SCHEMA_VERSION",
    "ALLOWED_PATCH_SCHEMA_VERSION",
    "PATCH_CANDIDATE_SCHEMA_VERSION",
    "PATCH_VALIDATION_SCHEMA_VERSION",
    "PHASE_B_HANDOFF_SCHEMA_VERSION",
    "RELEASE_GATE_ATTESTATION_SCHEMA_VERSION",
    "A32C_RELEASE_DECISION_SCHEMA_VERSION",
    "GOVERNANCE_RELEASE_MANIFEST_SCHEMA_VERSION",
    "ScientificOwnerContract",
    "GovernedAssetRecord",
    "AcceptanceEvidenceOwnershipContract",
    "DeprecationRuleContract",
    "MigrationRuleContract",
    "PublishedScientificStatusRecord",
    "AllowedRequestPatchContract",
    "RequestPatchCandidate",
    "RequestPatchValidationReport",
    "PhaseBHandoffContract",
    "ReleaseGateAttestation",
    "A32CReleaseDecision",
    "GovernanceReleaseManifest",
]
