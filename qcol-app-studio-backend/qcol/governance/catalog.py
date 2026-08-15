"""WP13 governance catalog and Phase B handoff declarations."""
from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from typing import Any, Iterable, Mapping

from qcol.acceptance import (
    acceptance_fingerprint_catalog_fingerprint,
    acceptance_harness_catalog_fingerprint,
    baseline_fingerprint,
    public_wp12_surface_catalog,
    wp12_surface_catalog_fingerprint,
)
from qcol.compatibility import (
    compatibility_rule_catalog_fingerprint,
    public_compatibility_rule_catalog,
)
from qcol.implementation_bindings import implementation_binding_catalog_fingerprint
from qcol.mapping_policies import (
    pair_mapping_migration_catalog_fingerprint,
    public_pair_mapping_migration_catalog,
    public_spin_orbital_mapping_migration_catalog,
    spin_orbital_mapping_migration_catalog_fingerprint,
    vocabulary_fingerprint,
)
from qcol.mapping_policies.profiles import (
    public_wp11_jw_accepted_composition_catalog,
    wp11_jw_accepted_composition_catalog_fingerprint,
)
from qcol.policy_contract_catalog import policy_contract_catalog_fingerprint
from qcol.realization_policies.base import contract_fingerprint, json_contract_value
from qcol.realization_variants import (
    model_task_realization_catalog_fingerprint,
    public_model_task_realization_catalog,
    realization_resolver_catalog_fingerprint,
)

from .contracts import (
    A32CReleaseDecision,
    AcceptanceEvidenceOwnershipContract,
    DeprecationRuleContract,
    GovernedAssetRecord,
    MigrationRuleContract,
    PhaseBHandoffContract,
    PublishedScientificStatusRecord,
    ReleaseGateAttestation,
    ScientificOwnerContract,
)
from .enums import (
    DeprecationStatus,
    EvidenceTreatment,
    GovernedAssetKind,
    HandoffStatus,
    MigrationKind,
    OwnerType,
)
from .patches import (
    PATCH_REGISTRY_ID,
    allowed_request_patch_registry_fingerprint,
    public_allowed_request_patch_registry,
    validate_allowed_request_patch_registry,
)


GOVERNANCE_CATALOG_SCHEMA_VERSION = "qcol-governance-catalog/1.0"
GOVERNANCE_CATALOG_VERSION = "1.0.0"
WP13_PROJECT_VERSION = "1.21.0"
A32C_RELEASE_ID = "qcol.release.phase-a3.2c.mapping-realization.v1"
A32C_RELEASE_VERSION = "1.0.0"


def foundation_fingerprints() -> dict[str, str]:
    return {
        "wp0_baseline": baseline_fingerprint(),
        "wp1_vocabulary": vocabulary_fingerprint(),
        "wp2_policy_contracts": policy_contract_catalog_fingerprint(),
        "wp3_implementation_bindings": implementation_binding_catalog_fingerprint(),
        "wp4_compatibility_rules": compatibility_rule_catalog_fingerprint(),
        "wp5_realization_resolver": realization_resolver_catalog_fingerprint(),
        "wp6_acceptance_fingerprints": acceptance_fingerprint_catalog_fingerprint(),
        "wp7_acceptance_harness": acceptance_harness_catalog_fingerprint(),
        "wp8_pair_mapping_migration": pair_mapping_migration_catalog_fingerprint(),
        "wp9_wp10_spin_orbital_migration": spin_orbital_mapping_migration_catalog_fingerprint(),
        "wp11_jw_accepted_composition": wp11_jw_accepted_composition_catalog_fingerprint(),
        "wp12_realization_variants": model_task_realization_catalog_fingerprint(),
        "wp12_surface": wp12_surface_catalog_fingerprint(),
    }


@lru_cache(maxsize=1)
def build_scientific_owners() -> tuple[ScientificOwnerContract, ...]:
    return (
        ScientificOwnerContract(
            owner_id="qcol.owner.mapping.pair",
            label="QCOL reduced-pairing scientific owner",
            owner_type=OwnerType.ROLE,
            scope=("pair_mapping", "reduced_pairing", "seniority_zero"),
            responsibilities=(
                "Approve Pair Mapping domain, quasispin algebra, sector semantics, and support boundaries.",
                "Review one-pair acceptance preservation and multi-pair experimental claims.",
            ),
            approval_authorities=("policy_change", "status_promotion", "limitation_change"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.mapping.fermionic",
            label="QCOL general fermionic mapping scientific owner",
            owner_type=OwnerType.ROLE,
            scope=("jordan_wigner", "bravyi_kitaev", "general_spin_orbital"),
            responsibilities=(
                "Approve mapping conventions, ordered-mode semantics, sector interpretation, and mapped-generator claims.",
                "Review JW and BK mapper, composition, and cell support boundaries separately.",
            ),
            approval_authorities=("policy_change", "status_promotion", "convention_change"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.compatibility",
            label="QCOL compatibility-rule scientific owner",
            owner_type=OwnerType.ROLE,
            scope=("compatibility_rules", "resolver", "failure_codes"),
            responsibilities=(
                "Own relation rules, global invariants, stable failure codes, and resolver decision semantics.",
                "Prevent silent fallback and ensure scientific failures block runtime entry.",
            ),
            approval_authorities=("rule_change", "failure_code_change", "resolver_gate_change"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.acceptance",
            label="QCOL acceptance and promotion scientific owner",
            owner_type=OwnerType.ROLE,
            scope=("acceptance_gates", "tolerance_profiles", "promotion_records"),
            responsibilities=(
                "Own mapper, composition, and cell gate definitions and versioned ToleranceProfiles.",
                "Approve acceptance promotion, revocation, and stale-evidence decisions.",
            ),
            approval_authorities=("acceptance_schema_change", "promotion", "revocation"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.evidence",
            label="QCOL evidence custodian",
            owner_type=OwnerType.ROLE,
            scope=("evidence_archives", "fingerprints", "manifests"),
            responsibilities=(
                "Preserve strict-JSON evidence, deterministic manifests, source fingerprints, and archive reproducibility.",
                "Regenerate evidence without Python pickling or callable payloads.",
            ),
            approval_authorities=("evidence_regeneration", "archive_supersession"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.release",
            label="QCOL governed-release owner",
            owner_type=OwnerType.ROLE,
            scope=("release_manifest", "published_status", "deprecation", "migration"),
            responsibilities=(
                "Publish versioned releases, explicit migration paths, deprecation notices, and separated scientific statuses.",
                "Prevent an unconditional mapping-verified badge from replacing mapper/composition/cell status records.",
            ),
            approval_authorities=("release", "deprecation", "migration", "status_publication"),
        ),
        ScientificOwnerContract(
            owner_id="qcol.owner.advisor.safety",
            label="QCOL deterministic-advisor safety owner",
            owner_type=OwnerType.ROLE,
            scope=("advisor_context", "request_patch_allowlist", "phase_b_handoff"),
            responsibilities=(
                "Own the sanitized Advisor context, allow-listed request patches, and no-mutation firewall.",
                "Ensure recommendations remain hypotheses until user approval and rerun verification.",
            ),
            approval_authorities=("patch_allowlist_change", "advisor_context_change", "phase_b_enablement"),
        ),
    )


def _owner_for_policy(policy_id: str) -> str:
    if policy_id.startswith("pair") or policy_id.startswith("pair_mapping"):
        return "qcol.owner.mapping.pair"
    if policy_id.startswith(("jw.", "jordan_wigner", "bk.", "bravyi_kitaev", "fermion.")):
        return "qcol.owner.mapping.fermionic"
    return "qcol.owner.release"


def _asset_kind(policy_id: str, schema_version: str) -> GovernedAssetKind:
    text = f"{policy_id} {schema_version}".lower()
    if "state" in text and "statement" not in text:
        return GovernedAssetKind.STATE_PREPARATION_POLICY
    if "ansatz" in text:
        return GovernedAssetKind.ANSATZ_POLICY
    if "measurement" in text:
        return GovernedAssetKind.MEASUREMENT_POLICY
    if "reference" in text:
        return GovernedAssetKind.REFERENCE_POLICY
    if "verification" in text:
        return GovernedAssetKind.VERIFICATION_POLICY
    return GovernedAssetKind.MAPPING_POLICY


def _schema_parts(schema_version: str) -> tuple[str, str]:
    if "/" in schema_version:
        return tuple(schema_version.split("/", 1))  # type: ignore[return-value]
    return schema_version, "1.0"


def _policy_version(payload: Mapping[str, Any]) -> str:
    for key in ("policy_version", "mapping_version", "contract_version", "version"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return "1.0.0"


_BINDING_KEYS = {
    "implementation_binding_id",
    "resource_assessor_binding_id",
    "encoder_policy_id",
    "decoder_policy_id",
    "physical_subspace_policy_id",
    "diagnostic_policy_id",
    "projector_policy_id",
    "grouping_policy_id",
    "reconstruction_policy_id",
    "independent_solver_binding_id",
}


def _collect_binding_ids(value: Any, *, key: str | None = None) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            found.update(_collect_binding_ids(child, key=str(child_key)))
    elif isinstance(value, list):
        for child in value:
            found.update(_collect_binding_ids(child, key=key))
    elif isinstance(value, str) and (
        key in _BINDING_KEYS or (key is not None and key.endswith("_binding_id"))
    ):
        found.add(value)
    return found


def _binding_version_map() -> dict[str, str]:
    pair = public_pair_mapping_migration_catalog()
    spin = public_spin_orbital_mapping_migration_catalog()
    wp11 = public_wp11_jw_accepted_composition_catalog()
    rows = [
        *pair["binding_registry"]["bindings"],
        *spin["binding_registry"]["bindings"],
        wp11["ansatz_binding"],
    ]
    return {
        str(row["binding_id"]): str(row.get("implementation_version", "unknown"))
        for row in rows
    }


def _collect_live_policy_contracts() -> dict[str, dict[str, Any]]:
    pair = public_pair_mapping_migration_catalog()
    spin = public_spin_orbital_mapping_migration_catalog()
    wp11 = public_wp11_jw_accepted_composition_catalog()
    contracts: dict[str, dict[str, Any]] = {}
    for source in (
        pair["contracts"],
        spin["jw"]["contracts"],
        spin["bk"]["contracts"],
    ):
        for policy_id, payload in source.items():
            contracts[str(policy_id)] = dict(payload)
    contracts[str(wp11["ansatz_policy"]["policy_id"])] = dict(wp11["ansatz_policy"])
    return dict(sorted(contracts.items()))


@lru_cache(maxsize=1)
def build_governed_assets() -> tuple[GovernedAssetRecord, ...]:
    versions = _binding_version_map()
    migration_rules = {item.source_asset_id: item.migration_id for item in build_migration_rules()}
    deprecation_rules = {item.asset_id: item.rule_id for item in build_deprecation_rules()}
    assets: list[GovernedAssetRecord] = []
    for policy_id, payload in _collect_live_policy_contracts().items():
        schema_id, schema_version = _schema_parts(str(payload.get("schema_version", "qcol-policy-contract/1.0")))
        binding_ids = tuple(sorted(_collect_binding_ids(payload)))
        implementation_versions = sorted({versions[item] for item in binding_ids if item in versions})
        implementation_version = (
            None
            if not implementation_versions
            else implementation_versions[0]
            if len(implementation_versions) == 1
            else "mixed"
        )
        limitations = payload.get("limitations") or ()
        if isinstance(limitations, str):
            limitations = (limitations,)
        limitation_statement = " ".join(str(item) for item in limitations if str(item).strip())
        if not limitation_statement:
            limitation_statement = (
                "Use only inside the declared Model × Task, encoding context, validity envelope, "
                "and published support status; no broader scientific claim is implied."
            )
        validity = payload.get("validity_envelope") or {
            "scope": payload.get("scope", "declared_policy_scope"),
            "supported_tasks": payload.get("supported_task_capabilities", []),
        }
        assets.append(
            GovernedAssetRecord(
                asset_id=policy_id,
                asset_kind=_asset_kind(policy_id, str(payload.get("schema_version", ""))),
                contract_schema_id=schema_id,
                contract_schema_version=schema_version,
                asset_version=_policy_version(payload),
                implementation_binding_ids=binding_ids,
                implementation_version=implementation_version,
                scientific_owner_id=_owner_for_policy(policy_id),
                acceptance_evidence_owner_id="qcol.owner.evidence",
                published_status=str(payload.get("support_status", "registered")),
                limitation_statement=limitation_statement,
                validity_envelope=validity,
                deprecation_rule_id=deprecation_rules.get(policy_id),
                migration_rule_ids=(migration_rules[policy_id],) if policy_id in migration_rules else (),
                provenance=payload.get("provenance", {}),
            )
        )

    rules = public_compatibility_rule_catalog()["rule_registry"]["rules"]
    for rule in rules:
        schema_id, schema_version = _schema_parts(str(rule["schema_version"]))
        assets.append(
            GovernedAssetRecord(
                asset_id=str(rule["rule_id"]),
                asset_kind=GovernedAssetKind.COMPATIBILITY_RULE,
                contract_schema_id=schema_id,
                contract_schema_version=schema_version,
                asset_version=str(rule["rule_version"]),
                implementation_binding_ids=(str(rule["predicate_binding_id"]),),
                implementation_version=str(rule["predicate_binding_version"]),
                scientific_owner_id="qcol.owner.compatibility",
                acceptance_evidence_owner_id="qcol.owner.evidence",
                published_status="active",
                limitation_statement=(
                    f"Applies only to the declared participants {', '.join(rule['participants'])} "
                    f"under convention {rule['predicate_convention_id']}."
                ),
                validity_envelope={
                    "phase": rule["phase"],
                    "participants": rule["participants"],
                    "required_evidence": rule["required_evidence"],
                },
                provenance={"failure_code": rule["failure_code"], "severity": rule["severity"]},
            )
        )
    return tuple(sorted(assets, key=lambda item: (item.asset_kind.value, item.asset_id)))


@lru_cache(maxsize=1)
def build_acceptance_evidence_ownership() -> tuple[AcceptanceEvidenceOwnershipContract, ...]:
    return (
        AcceptanceEvidenceOwnershipContract(
            evidence_asset_id="evidence.acceptance.pair.one_pair.v1",
            evidence_schema_id="qcol-acceptance-evidence-fingerprint",
            evidence_schema_version="1.0",
            scientific_owner_id="qcol.owner.mapping.pair",
            custodian_owner_id="qcol.owner.evidence",
            promotion_authority_owner_id="qcol.owner.acceptance",
            published_claim_id="realization.reduced_pairing.one_pair.pair_mapping.v1",
            fingerprint_required=True,
            retention_policy="Retain the accepted record and every superseding record; never overwrite the original fingerprint.",
            regeneration_command="python scripts/run_wp8_gate.py --with-scientific-regressions",
            revocation_conditions=(
                "Any accepted component, implementation, tolerance, dependency, or declared-scale fingerprint changes.",
                "A regression invalidates mapper, composition, or cell acceptance.",
            ),
            supersession_policy="Publish a new versioned record; mark the old record stale or superseded without deleting it.",
        ),
        AcceptanceEvidenceOwnershipContract(
            evidence_asset_id="evidence.acceptance.jw.mapping_analysis.v1",
            evidence_schema_id="qcol-acceptance-evidence-fingerprint",
            evidence_schema_version="1.0",
            scientific_owner_id="qcol.owner.mapping.fermionic",
            custodian_owner_id="qcol.owner.evidence",
            promotion_authority_owner_id="qcol.owner.acceptance",
            published_claim_id="realization.general_spin_orbital.mapping_analysis.jw.v1",
            fingerprint_required=True,
            retention_policy="Retain mapping-analysis evidence separately from any executable ground-state evidence.",
            regeneration_command="python scripts/run_wp9_wp10_gate.py --with-scientific-regressions",
            revocation_conditions=(
                "The JW convention, ordered-mode contract, operator-equivalence suite, or dependency fingerprint changes.",
            ),
            supersession_policy="Recompute mapper and analysis evidence under a new fingerprint.",
        ),
        AcceptanceEvidenceOwnershipContract(
            evidence_asset_id="evidence.acceptance.bk.mapping_analysis.v1",
            evidence_schema_id="qcol-acceptance-evidence-fingerprint",
            evidence_schema_version="1.0",
            scientific_owner_id="qcol.owner.mapping.fermionic",
            custodian_owner_id="qcol.owner.evidence",
            promotion_authority_owner_id="qcol.owner.acceptance",
            published_claim_id="realization.general_spin_orbital.mapping_analysis.bk.v1",
            fingerprint_required=True,
            retention_policy="Retain BK mapping-analysis evidence with its exact convention and nonlocal sector semantics.",
            regeneration_command="python scripts/run_wp9_wp10_gate.py --with-scientific-regressions",
            revocation_conditions=(
                "The BK convention, encoder/decoder, nonlocal sector diagnostic, or dependency fingerprint changes.",
            ),
            supersession_policy="Recompute analysis evidence; never infer full ground-state execution support.",
        ),
        AcceptanceEvidenceOwnershipContract(
            evidence_asset_id="evidence.acceptance.jw.ground_state.wp11.v1",
            evidence_schema_id="qcol-acceptance-evidence-fingerprint",
            evidence_schema_version="1.0",
            scientific_owner_id="qcol.owner.mapping.fermionic",
            custodian_owner_id="qcol.owner.evidence",
            promotion_authority_owner_id="qcol.owner.acceptance",
            published_claim_id="realization.general_spin_orbital.ground_state.jw.wp11.v1",
            fingerprint_required=True,
            retention_policy="Retain the accepted WP11 promotion record, gate attestations, exact fingerprint, and negative historical fixture.",
            regeneration_command="python scripts/run_wp11_gate.py --with-scientific-acceptance",
            revocation_conditions=(
                "Any mapper, state, ansatz, measurement, reference, verification, tolerance, dependency, or declared-scale fingerprint changes.",
                "Any of Mapper, Composition, or Cell gates ceases to pass.",
                "Evidence regeneration is not reproducible.",
            ),
            supersession_policy="Publish a new promotion record and keep the old record as immutable historical evidence.",
        ),
        AcceptanceEvidenceOwnershipContract(
            evidence_asset_id="evidence.release.phase_a3_2c.wp13.v1",
            evidence_schema_id="qcol-wp13-governance-evidence",
            evidence_schema_version="1.0",
            scientific_owner_id="qcol.owner.release",
            custodian_owner_id="qcol.owner.evidence",
            promotion_authority_owner_id="qcol.owner.release",
            published_claim_id=A32C_RELEASE_ID,
            fingerprint_required=True,
            retention_policy="Retain the governed release manifest, ownership registry, status publication, patch allowlist, and exit decision together.",
            regeneration_command="python scripts/run_wp13_gate.py",
            revocation_conditions=(
                "The governed release catalog fingerprint changes without a new release version.",
                "The WP11 acceptance fingerprint or WP12 realization surface no longer matches the release record.",
            ),
            supersession_policy="Create a new versioned release; never rewrite an issued release manifest.",
        ),
    )


@lru_cache(maxsize=1)
def build_migration_rules() -> tuple[MigrationRuleContract, ...]:
    pair_aliases = public_pair_mapping_migration_catalog()["profile"]["legacy_policy_aliases"]
    spin_aliases = public_spin_orbital_mapping_migration_catalog()["legacy_policy_migrations"]
    rules: list[MigrationRuleContract] = []
    for source, target in sorted(pair_aliases.items()):
        rules.append(
            MigrationRuleContract(
                migration_id=f"migration.{source}.to.{target}",
                source_asset_id=str(source),
                source_version="1.0.0",
                target_asset_id=str(target),
                target_version="1.0.0",
                migration_kind=MigrationKind.EXPLICIT_ALIAS,
                semantic_scope="Preserve the already declared reduced-pairing meaning while publishing the narrowed seniority-zero identity explicitly.",
                automatic=True,
                evidence_treatment=EvidenceTreatment.PRESERVE,
                requires_revalidation=False,
                failure_code_on_invalid="POLICY_MIGRATION_TARGET_MISMATCH",
                notes="The alias is exact and visible; no silent implementation substitution is permitted.",
            )
        )
    for source, target in sorted(spin_aliases.items()):
        rules.append(
            MigrationRuleContract(
                migration_id=f"migration.{source}.to.{target}",
                source_asset_id=str(source),
                source_version="1.0.0",
                target_asset_id=str(target),
                target_version="1.0.0",
                migration_kind=MigrationKind.IDENTIFIER_MIGRATION,
                semantic_scope="Preserve mapper and mapping-analysis support while making convention and spin-orbital scope explicit.",
                automatic=True,
                evidence_treatment=EvidenceTreatment.RECOMPUTE,
                requires_revalidation=True,
                failure_code_on_invalid="POLICY_MIGRATION_TARGET_MISMATCH",
                notes="Acceptance evidence is bound to the new exact policy identity and convention.",
            )
        )
    rules.append(
        MigrationRuleContract(
            migration_id="migration.jw_bare_exchange.to.jw_mapped_fswap.v1",
            source_asset_id="jw.ansatz.current_bare_qubit_exchange.v1",
            source_version="1.0.0",
            target_asset_id="jw.ansatz.mapped_fermionic_swap_network.v1",
            target_version="1.0.0",
            migration_kind=MigrationKind.SCIENTIFIC_REPLACEMENT,
            semantic_scope="Replace a qubit-native Hamming-weight-preserving circuit with a JW-mapped fermionic-generator composition.",
            automatic=False,
            evidence_treatment=EvidenceTreatment.STALE,
            requires_revalidation=True,
            failure_code_on_invalid="ANSATZ_GENERATOR_MAPPING_MISMATCH",
            notes="The historical source remains a permanent negative regression fixture and is never relabeled as accepted.",
        )
    )
    return tuple(rules)


@lru_cache(maxsize=1)
def build_deprecation_rules() -> tuple[DeprecationRuleContract, ...]:
    rules: list[DeprecationRuleContract] = []
    for migration in build_migration_rules():
        if migration.migration_kind is MigrationKind.SCIENTIFIC_REPLACEMENT:
            rules.append(
                DeprecationRuleContract(
                    rule_id="deprecation.jw_bare_exchange.rejected_fixture.v1",
                    asset_id=migration.source_asset_id,
                    status=DeprecationStatus.REJECTED_REGRESSION_FIXTURE,
                    announced_in_release=A32C_RELEASE_ID,
                    earliest_removal_release=None,
                    replacement_asset_id=migration.target_asset_id,
                    warning_code="ANSATZ_GENERATOR_MAPPING_MISMATCH",
                    migration_required=True,
                    preserve_as_regression_fixture=True,
                    acceptance_evidence_treatment=EvidenceTreatment.STALE,
                    notes="Retain indefinitely as the semantic failure fixture; it is not selectable or runnable.",
                )
            )
        else:
            rules.append(
                DeprecationRuleContract(
                    rule_id=f"deprecation.{migration.source_asset_id}.alias.v1",
                    asset_id=migration.source_asset_id,
                    status=DeprecationStatus.DEPRECATED_ALIAS,
                    announced_in_release=A32C_RELEASE_ID,
                    earliest_removal_release="qcol.release.2.0.0",
                    replacement_asset_id=migration.target_asset_id,
                    warning_code="DEPRECATED_POLICY_ID",
                    migration_required=True,
                    preserve_as_regression_fixture=False,
                    acceptance_evidence_treatment=migration.evidence_treatment,
                    notes="The legacy ID remains an explicit migration path for this release and may not silently select a different implementation.",
                )
            )
    return tuple(rules)


@lru_cache(maxsize=1)
def build_published_status_records() -> tuple[PublishedScientificStatusRecord, ...]:
    catalog = public_model_task_realization_catalog()
    records: list[PublishedScientificStatusRecord] = []
    for cell in catalog["cells"]:
        for variant in cell["variants"]:
            mapping_id = str(variant.get("mapping_id") or "not_applicable.v1")
            limits = tuple(variant.get("limitations") or ())
            if not limits:
                limits = (str(variant.get("support_scope") or "Only the published Model × Task cell scope is claimed."),)
            records.append(
                PublishedScientificStatusRecord(
                    record_id=f"published-status.{variant['variant_id']}",
                    variant_id=str(variant["variant_id"]),
                    model_id=str(variant["model_id"]),
                    task_id=str(variant["task_id"]),
                    mapping_policy_id=mapping_id,
                    mapper_status=str(variant["mapper_status"]),
                    composition_status=str(variant["composition_status"]),
                    cell_status=str(variant["cell_status"]),
                    runtime_status=str(variant["runtime_status"]),
                    runnable=bool(variant["runnable"]),
                    selectable=bool(variant["selectable"]),
                    support_boundary=str(variant.get("support_scope") or "No broader support claim."),
                    evidence_fingerprint=(
                        None
                        if variant.get("evidence_fingerprint") is None
                        else str(variant["evidence_fingerprint"])
                    ),
                    declared_scale={"scope_statement": str(variant.get("support_scope") or "not_declared")},
                    source_record_ids=(str(variant["variant_id"]), str(cell["cell_id"])),
                    limitations=limits,
                    unqualified_mapping_verified_badge=False,
                )
            )
    return tuple(sorted(records, key=lambda item: item.variant_id))


@lru_cache(maxsize=1)
def build_a3_2c_release_decision() -> A32CReleaseDecision:
    wp11 = public_wp11_jw_accepted_composition_catalog()
    wp12 = public_wp12_surface_catalog()
    promotion = wp11["promotion_record"]
    expected = str(wp11["acceptance_fingerprint"]["fingerprint"])
    observed = str(promotion["evidence_fingerprint"]["fingerprint"])
    gate_ids = tuple(str(item) for item in promotion["gate_report_ids"])
    gate_kinds = ("mapper_conformance", "composition_conformance", "cell_acceptance")
    attestations = tuple(
        ReleaseGateAttestation(
            gate_id=gate_id,
            gate_kind=gate_kind,
            status=__import__("qcol.mapping_policies", fromlist=["CheckStatus"]).CheckStatus.PASS,
            source_record_id=str(promotion["record_id"]),
            evidence_fingerprint=observed,
            message="The accepted WP11 promotion record attests this gate as PASS in the clean scientific environment.",
        )
        for gate_id, gate_kind in zip(gate_ids, gate_kinds, strict=True)
    )
    accepted_variant = next(
        item
        for item in build_published_status_records()
        if item.variant_id == "realization.general_spin_orbital.ground_state.jw.wp11.v1"
    )
    reproducible = bool(
        wp12["evidence_contract"]["strict_json"]
        and wp12["evidence_contract"]["deterministic_archive"]
        and not wp12["evidence_contract"]["python_pickling_used"]
    )
    ready = (
        all(item.status.value == "pass" for item in attestations)
        and expected == observed
        and reproducible
        and not wp12["runtime_contract"]["second_runtime_created"]
    )
    return A32CReleaseDecision(
        release_id=A32C_RELEASE_ID,
        release_version=A32C_RELEASE_VERSION,
        project_version=WP13_PROJECT_VERSION,
        resolved_variant_id=accepted_variant.variant_id,
        gate_attestations=attestations,
        fingerprint_match=expected == observed,
        evidence_reproducible=reproducible,
        published_cell_status=accepted_variant.cell_status if ready else "not_verified",
        phase_a3_2c_exit_ready=ready,
        phase_b_handoff_ready=ready,
        phase_b_advisor_runtime_implemented=False,
        second_runtime_created=bool(wp12["runtime_contract"]["second_runtime_created"]),
        foundation_fingerprints=foundation_fingerprints(),
        limitations=(
            "Acceptance remains bounded to the WP11 declared 2–4-mode, single-species, fixed-particle, local-simulator scale.",
            "BK full ground-state execution remains recognized_not_executable.",
            "WP13 enables Phase B development but does not implement or activate the Advisor runtime.",
        ),
    )


@lru_cache(maxsize=1)
def build_phase_b_handoff_contract() -> PhaseBHandoffContract:
    release = build_a3_2c_release_decision()
    return PhaseBHandoffContract(
        handoff_id="qcol.phase_b.deterministic_advisor_handoff.v1",
        handoff_version="1.0.0",
        status=HandoffStatus.READY if release.phase_b_handoff_ready else HandoffStatus.BLOCKED,
        compatibility_report_schema_version="qcol-compatibility-report/1.0",
        resource_report_schema_version="qcol-realization-resource-report/1.0",
        request_patch_schema_version="qcol-request-patch-candidate/1.0",
        allowed_patch_registry_id=PATCH_REGISTRY_ID,
        allowed_patch_registry_fingerprint=allowed_request_patch_registry_fingerprint(),
        advisor_context_readable_fields=(
            "model and task contract identifiers",
            "resolved realization identifier and exact support statuses",
            "CompatibilityReport diagnostics and stable failure codes",
            "ResourceReport estimates and declared envelope",
            "convergence history, standard error, absolute error, sector leakage, and circuit resources",
            "evidence references and acceptance freshness status",
        ),
        advisor_context_forbidden_fields=(
            "exact eigenvectors or exact state amplitudes",
            "reference-derived parameter vectors",
            "backend credentials or private secrets",
            "Python callables and opaque scientific objects",
        ),
        forbidden_mutations=(
            "ProblemArtifact",
            "RunResult",
            "Evidence archive",
            "Verification result or thresholds",
            "Independent reference",
            "Published scientific status",
        ),
        recommendation_status="hypothesis",
        user_approval_required=True,
        same_pipeline_required=True,
        verification_retains_final_authority=True,
        phase_b_may_start=release.phase_b_handoff_ready,
        phase_b_advisor_runtime_implemented=False,
        limitations=(
            "Only exact allow-listed request patches may be proposed.",
            "A recommendation is unverified until user approval and a new run through the same pipeline.",
            "If no executable alternative exists, the Advisor must report the limitation and return no patch.",
        ),
    )


@lru_cache(maxsize=1)
def public_governance_catalog() -> dict[str, Any]:
    release = build_a3_2c_release_decision()
    handoff = build_phase_b_handoff_contract()
    payload: dict[str, Any] = {
        "schema_version": GOVERNANCE_CATALOG_SCHEMA_VERSION,
        "catalog_version": GOVERNANCE_CATALOG_VERSION,
        "project_version": WP13_PROJECT_VERSION,
        "phase": "A.3.2c",
        "work_package": "WP13",
        "objective": (
            "Govern policy contracts, compatibility rules, evidence ownership, migrations, "
            "published status triplets, and the deterministic Phase B request-patch boundary."
        ),
        "foundation_fingerprints": foundation_fingerprints(),
        "scientific_owners": [item.to_dict() for item in build_scientific_owners()],
        "governed_assets": [item.to_dict() for item in build_governed_assets()],
        "acceptance_evidence_ownership": [
            item.to_dict() for item in build_acceptance_evidence_ownership()
        ],
        "deprecation_rules": [item.to_dict() for item in build_deprecation_rules()],
        "migration_rules": [item.to_dict() for item in build_migration_rules()],
        "published_statuses": [item.to_dict() for item in build_published_status_records()],
        "allowed_request_patch_registry": public_allowed_request_patch_registry(),
        "phase_b_handoff": handoff.to_dict(),
        "a3_2c_release_decision": release.to_dict(),
        "release_rules": {
            "schema_versions_separate_from_implementation_versions": True,
            "scientific_owner_required_per_policy": True,
            "limitation_statement_required_per_policy": True,
            "acceptance_evidence_owner_required": True,
            "deprecation_must_name_replacement_or_retirement_reason": True,
            "migration_must_be_explicit_and_versioned": True,
            "publish_mapper_composition_cell_separately": True,
            "unqualified_mapping_verified_badge_allowed": False,
            "phase_b_requires_machine_readable_compatibility_report": True,
            "phase_b_requires_machine_readable_patch_allowlist": True,
            "phase_b_recommendations_mutate_truth": False,
        },
        "runtime_contract": {
            "second_runtime_created": False,
            "shared_pipeline_required": True,
            "verification_final_authority": True,
            "advisor_runtime_implemented": False,
        },
    }
    payload["fingerprint"] = contract_fingerprint(payload)
    return json_contract_value(payload)


def governance_catalog_fingerprint() -> str:
    return str(public_governance_catalog()["fingerprint"])


def get_governed_asset(asset_id: str) -> dict[str, Any]:
    for item in public_governance_catalog()["governed_assets"]:
        if item["asset_id"] == asset_id:
            return dict(item)
    raise KeyError(f"Unknown governed asset {asset_id!r}.")


def get_published_status(variant_id: str) -> dict[str, Any]:
    for item in public_governance_catalog()["published_statuses"]:
        if item["variant_id"] == variant_id:
            return dict(item)
    raise KeyError(f"Unknown published realization variant {variant_id!r}.")


def validate_wp13_governance_catalog() -> dict[str, bool]:
    catalog = public_governance_catalog()
    owners = {item["owner_id"] for item in catalog["scientific_owners"]}
    assets = catalog["governed_assets"]
    policy_assets = [item for item in assets if item["asset_kind"].endswith("policy")]
    statuses = catalog["published_statuses"]
    accepted = next(
        item
        for item in statuses
        if item["variant_id"] == "realization.general_spin_orbital.ground_state.jw.wp11.v1"
    )
    historical = next(
        item
        for item in statuses
        if item["variant_id"] == "realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1"
    )
    bk = next(
        item
        for item in statuses
        if item["variant_id"] == "realization.general_spin_orbital.ground_state.bk.default.v1"
    )
    release = catalog["a3_2c_release_decision"]
    handoff = catalog["phase_b_handoff"]
    checks = {
        "catalog_is_strict_json": json_contract_value(catalog) == catalog,
        "all_policy_assets_have_scientific_owner": all(
            item["scientific_owner_id"] in owners for item in policy_assets
        ),
        "all_policy_assets_have_limitations": all(
            bool(item["limitation_statement"].strip()) for item in policy_assets
        ),
        "schema_and_implementation_versions_are_separate": all(
            "contract_schema_version" in item and "implementation_version" in item
            for item in assets
        ),
        "acceptance_evidence_has_owner_and_custodian": all(
            item["scientific_owner_id"] in owners
            and item["custodian_owner_id"] in owners
            and item["promotion_authority_owner_id"] in owners
            for item in catalog["acceptance_evidence_ownership"]
        ),
        "deprecations_are_explicit": all(
            item["warning_code"] and item["notes"] for item in catalog["deprecation_rules"]
        ),
        "migrations_are_explicit": all(
            item["source_asset_id"] != item["target_asset_id"]
            and item["failure_code_on_invalid"]
            for item in catalog["migration_rules"]
        ),
        "published_statuses_are_triplets": all(
            all(key in item for key in ("mapper_status", "composition_status", "cell_status"))
            and not item["unqualified_mapping_verified_badge"]
            for item in statuses
        ),
        "accepted_jw_triplet_is_published": (
            accepted["mapper_status"] == "verified"
            and accepted["composition_status"] == "verified"
            and accepted["cell_status"] == "acceptance_verified"
            and accepted["runnable"]
        ),
        "historical_jw_remains_failed": (
            historical["composition_status"] == "failed"
            and historical["cell_status"] == "not_verified"
            and not historical["runnable"]
        ),
        "bk_remains_not_executable": (
            bk["composition_status"] == "unresolved"
            and bk["cell_status"] == "recognized_not_executable"
            and not bk["runnable"]
        ),
        "allowed_patch_registry_valid": all(validate_allowed_request_patch_registry().values()),
        "phase_b_handoff_machine_readable": (
            handoff["compatibility_report_schema_version"] == "qcol-compatibility-report/1.0"
            and handoff["allowed_patch_registry_fingerprint"]
            == catalog["allowed_request_patch_registry"]["fingerprint"]
        ),
        "release_mapper_gate_pass": release["gate_attestations"][0]["status"] == "pass",
        "release_composition_gate_pass": release["gate_attestations"][1]["status"] == "pass",
        "release_cell_gate_pass": release["gate_attestations"][2]["status"] == "pass",
        "release_fingerprint_match": release["fingerprint_match"],
        "release_evidence_reproducible": release["evidence_reproducible"],
        "release_exit_ready": release["phase_a3_2c_exit_ready"],
        "jw_published_only_after_release_ready": (
            release["published_cell_status"] == "acceptance_verified"
            and release["phase_a3_2c_exit_ready"]
        ),
        "phase_b_handoff_ready_but_runtime_not_implemented": (
            handoff["phase_b_may_start"]
            and not handoff["phase_b_advisor_runtime_implemented"]
        ),
        "no_second_runtime": not catalog["runtime_contract"]["second_runtime_created"],
    }
    return checks


__all__ = [
    "GOVERNANCE_CATALOG_SCHEMA_VERSION",
    "GOVERNANCE_CATALOG_VERSION",
    "WP13_PROJECT_VERSION",
    "A32C_RELEASE_ID",
    "A32C_RELEASE_VERSION",
    "foundation_fingerprints",
    "build_scientific_owners",
    "build_governed_assets",
    "build_acceptance_evidence_ownership",
    "build_deprecation_rules",
    "build_migration_rules",
    "build_published_status_records",
    "build_a3_2c_release_decision",
    "build_phase_b_handoff_contract",
    "public_governance_catalog",
    "governance_catalog_fingerprint",
    "get_governed_asset",
    "get_published_status",
    "validate_wp13_governance_catalog",
]
