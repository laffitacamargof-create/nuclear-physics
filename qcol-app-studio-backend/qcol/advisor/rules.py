"""Versioned deterministic Advisor rules.

Rules do not mutate requests or scientific records.  A rule may either emit a
grounded fact/limitation or propose one exact RequestPatchCandidate that is
validated again against the WP13 allowlist by the Advisor engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Optional, Sequence

from qcol.governance.contracts import RequestPatchCandidate
from qcol.governance.enums import PatchOperation
from qcol.governance.patches import (
    BK_ANALYSIS_VARIANT,
    JW_ANALYSIS_VARIANT,
    JW_GROUND_VARIANT,
)
from qcol.realization_policies.base import contract_fingerprint

from .contracts import AdvisorContext, AdvisorRuleContract, EvidenceReference
from .enums import (
    AdvisorRulePhase,
    RecommendationEpistemicStatus,
    RecommendationKind,
)


@dataclass(frozen=True)
class RuleOutcome:
    title: str
    summary: str
    explanation: str
    evidence_refs: tuple[EvidenceReference, ...]
    expected_effect: str
    limitations: tuple[str, ...]
    patch: Optional[RequestPatchCandidate] = None
    kind: RecommendationKind = RecommendationKind.VERIFIED_FACT
    epistemic_status: RecommendationEpistemicStatus = RecommendationEpistemicStatus.GROUNDED


Predicate = Callable[[AdvisorContext], Optional[RuleOutcome]]


def _ref(source: str, path: str, label: str, value: object) -> EvidenceReference:
    return EvidenceReference(source=source, path=path, label=label, observed_value=value)


def _patch_id(rule_id: str, context: AdvisorContext, field_path: str, proposed_value: object) -> str:
    return f"advisor-patch-{contract_fingerprint({'rule_id': rule_id, 'context': context.context_id, 'field': field_path, 'value': proposed_value})[:16]}"


def _patch(
    rule_id: str,
    context: AdvisorContext,
    *,
    field_path: str,
    proposed_value: object,
    source: str = "deterministic_advisor",
    source_run_id: str | None = None,
    same_variant_fingerprint: bool | None = None,
) -> RequestPatchCandidate:
    return RequestPatchCandidate(
        patch_id=_patch_id(rule_id, context, field_path, proposed_value),
        target_variant_id=context.variant_id,
        task_id=context.task_id,
        field_path=field_path,
        operation=PatchOperation.REPLACE,
        proposed_value=proposed_value,
        source=source,
        source_run_id=source_run_id,
        same_variant_fingerprint=same_variant_fingerprint,
    )


def _support_boundary(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.model_id == "fermion.general_spin_orbital":
        return RuleOutcome(
            title="Mapping support boundary",
            summary=(
                "JW transformation is verified. The accepted WP11 JW composition is runnable at its "
                "declared scale; the historical bare exchange remains rejected. BK is verified for "
                "mapping analysis, but full BK ground-state execution remains unresolved."
            ),
            explanation=(
                "QCOL publishes mapper, composition, and cell statuses separately. The old JW circuit "
                "preserved particle number but failed mapped-generator equivalence; the accepted JW "
                "variant uses mapping-aware fermionic generators. BK may be compared as an operator "
                "mapping, but it is not silently promoted to a ground-state execution path."
            ),
            evidence_refs=(
                _ref("context", "/status_triplet/mapper", "Current mapper status", context.status_triplet.get("mapper")),
                _ref("context", "/status_triplet/composition", "Current composition status", context.status_triplet.get("composition")),
                _ref("context", "/status_triplet/cell", "Current cell status", context.status_triplet.get("cell")),
                _ref("governance", "/support_boundaries/bk_ground_state", "BK ground-state boundary", "recognized_not_executable"),
            ),
            expected_effect="Preserve an honest distinction between transform support, composition support, and complete cell acceptance.",
            limitations=(
                "This card reports governed support facts; it does not choose a mapping for a ground-state rerun.",
                "BK resource analysis is not a claim that BK is physically more accurate or executable for this cell.",
            ),
        )
    if context.model_id.startswith("nuclear.reduced_pairing"):
        return RuleOutcome(
            title="Pair-mapping domain boundary",
            summary="Pair mapping is valid only in the declared seniority-zero reduced pair-occupation domain.",
            explanation=(
                "The pair-occupation encoding preserves quasispin / hard-core-pair algebra. Raw pair-qubit "
                "popcount means pair number, while physical particle number is twice that value. It does not "
                "claim full single-fermion Fock-space semantics or broken-pair support."
            ),
            evidence_refs=(
                _ref("context", "/model_id", "Resolved model", context.model_id),
                _ref("governance", "/pair_mapping/mapping_scope", "Pair-mapping scope", "restricted_seniority_zero_subspace"),
                _ref("governance", "/pair_mapping/preserved_algebra", "Preserved algebra", "quasispin / hard-core-pair algebra"),
            ),
            expected_effect="Prevent a reduced pair encoding from being interpreted as a general single-fermion mapping.",
            limitations=("No mapping-family change is proposed by this card.",),
        )
    return None


def _historical_jw_failure(context: AdvisorContext) -> Optional[RuleOutcome]:
    if "ANSATZ_GENERATOR_MAPPING_MISMATCH" not in context.stable_failure_codes:
        return None
    return RuleOutcome(
        title="Current ansatz rejected by composition conformance",
        summary=(
            "The circuit preserves particle number, but it fails mapped-generator equivalence for "
            "nonadjacent Jordan–Wigner excitations."
        ),
        explanation=(
            "Particle-number or Hamming-weight preservation is weaker than implementing the mapped "
            "fermionic generator. The historical bare qubit exchange misses the JW parity-dependent "
            "relative sign, so QCOL blocks the cell before measurement or QASM execution."
        ),
        evidence_refs=(
            _ref("compatibility", "/stable_failure_codes", "Stable failure code", "ANSATZ_GENERATOR_MAPPING_MISMATCH"),
            _ref("context", "/status_triplet/composition", "Composition status", context.status_triplet.get("composition")),
            _ref("context", "/telemetry/runtime_path", "Runtime path", context.telemetry.get("runtime_path")),
        ),
        expected_effect="Keep the invalid historical composition blocked and direct users to the accepted mapped-fermionic JW variant.",
        limitations=(
            "The Advisor cannot mutate the ansatz identity or relabel the historical fixture.",
            "No request patch is emitted because ansatz-family replacement is not allow-listed in Phase B.",
        ),
        kind=RecommendationKind.LIMITATION,
        epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
    )


def _bk_unresolved(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.variant_id != "realization.general_spin_orbital.ground_state.bk.default.v1":
        return None
    return RuleOutcome(
        title="BK ground-state realization is not executable",
        summary="BK is available for mapping analysis, but its full ground-state composition remains unresolved.",
        explanation=(
            "The mapper is verified for transformation, yet BK-aware state preparation, nonlocal particle-number "
            "diagnostics, a compatible ansatz, and cell acceptance are not present. Raw qubit popcount is not "
            "physical particle number under this encoding."
        ),
        evidence_refs=(
            _ref("context", "/status_triplet/mapper", "BK mapper status", context.status_triplet.get("mapper")),
            _ref("context", "/status_triplet/composition", "BK composition status", context.status_triplet.get("composition")),
            _ref("context", "/status_triplet/cell", "BK cell status", context.status_triplet.get("cell")),
            _ref("governance", "/bk/raw_popcount_is_particle_number", "Raw-popcount semantics", False),
        ),
        expected_effect="Report the support limitation without inventing a BK execution path or silently substituting JW components.",
        limitations=("No executable alternative can be created by a request patch in this cell.",),
        kind=RecommendationKind.LIMITATION,
        epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
    )


def _stale_evidence(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.acceptance_evidence.get("freshness") != "stale" and "ACCEPTANCE_EVIDENCE_STALE" not in context.stable_failure_codes:
        return None
    return RuleOutcome(
        title="Acceptance evidence is stale",
        summary="The current acceptance record does not match the resolved realization fingerprint.",
        explanation=(
            "Changing a policy, convention, ordering, sector, ansatz, reference, tolerance profile, dependency, "
            "or declared scale invalidates the old evidence. QCOL does not allow a stale record to promote or "
            "authorize the current realization."
        ),
        evidence_refs=(
            _ref("acceptance", "/acceptance_evidence/freshness", "Evidence freshness", context.acceptance_evidence.get("freshness")),
            _ref("acceptance", "/acceptance_evidence/fingerprint", "Observed evidence fingerprint", context.acceptance_evidence.get("fingerprint")),
            _ref("context", "/variant_fingerprint", "Resolved variant fingerprint", context.variant_fingerprint),
        ),
        expected_effect="Require fresh resolution, rerun, and evidence generation before any status promotion.",
        limitations=(
            "The Advisor cannot edit or refresh Evidence directly.",
            "No patch is emitted because evidence regeneration is a pipeline outcome, not a request-field mutation.",
        ),
        kind=RecommendationKind.LIMITATION,
        epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
    )


def _sector_leakage(context: AdvisorContext) -> Optional[RuleOutcome]:
    leakage = context.telemetry.get("sector_leakage")
    if leakage is None:
        return None
    try:
        leakage_value = float(leakage)
    except (TypeError, ValueError):
        return None
    threshold = context.telemetry.get("sector_leakage_threshold")
    try:
        threshold_value = float(threshold) if threshold is not None else 1e-8
    except (TypeError, ValueError):
        threshold_value = 1e-8
    if leakage_value <= threshold_value:
        return None
    return RuleOutcome(
        title="Physical-sector leakage requires review",
        summary=f"Observed sector leakage {leakage_value:.6g} exceeds the declared limit {threshold_value:.6g}.",
        explanation=(
            "Sector leakage is a scientific diagnostic, not an optimizer score. The current allowlist does not "
            "permit the Advisor to replace the mapping, state preparation, ansatz family, verification policy, "
            "or acceptance threshold."
        ),
        evidence_refs=(
            _ref("telemetry", "/telemetry/sector_leakage", "Sector leakage", leakage_value),
            _ref("telemetry", "/telemetry/sector_leakage_threshold", "Declared leakage threshold", threshold_value),
            _ref("context", "/variant_id", "Resolved realization", context.variant_id),
        ),
        expected_effect="Keep the run in review and require a supported realization or implementation diagnosis.",
        limitations=(
            "No unsafe ansatz, mapping, or verification-threshold patch is emitted.",
            "A new accepted circuit family must first be registered and pass its own composition and cell gates.",
        ),
        kind=RecommendationKind.LIMITATION,
        epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
    )


def _sampling_uncertainty(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.task_id != "ground_state_energy" or not context.telemetry.get("variant_runnable"):
        return None
    stderr = context.telemetry.get("standard_error")
    threshold = context.telemetry.get("acceptance_threshold")
    shots = context.telemetry.get("shots_per_group")
    try:
        stderr_value = float(stderr)
        threshold_value = float(threshold) if threshold is not None else 0.02
        shots_value = int(shots)
    except (TypeError, ValueError):
        return None
    trigger = max(0.005, 0.25 * abs(threshold_value))
    if stderr_value <= trigger or shots_value >= 32768:
        return None
    proposed = min(32768, max(256, shots_value * 2))
    rule_id = "advisor.rule.sampling_uncertainty.v1"
    return RuleOutcome(
        title="Reduce sampling uncertainty",
        summary=f"The standard error {stderr_value:.6g} is large relative to the declared acceptance scale.",
        explanation=(
            "Increasing shots changes sampling precision only. It does not alter the model, mapping, ansatz, "
            "reference, verification thresholds, or scientific acceptance rule."
        ),
        evidence_refs=(
            _ref("telemetry", "/telemetry/standard_error", "Standard error", stderr_value),
            _ref("telemetry", "/telemetry/acceptance_threshold", "Acceptance threshold", threshold_value),
            _ref("telemetry", "/telemetry/shots_per_group", "Current shots per group", shots_value),
        ),
        expected_effect="Lower the Monte Carlo standard error in a new run; the actual improvement remains to be verified.",
        limitations=(
            "More shots increase runtime and do not fix mapping, ansatz, or convergence errors.",
            "This remains an unverified hypothesis until a new same-pipeline run is completed.",
        ),
        patch=_patch(rule_id, context, field_path="/shots", proposed_value=proposed),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _optimizer_budget(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.task_id != "ground_state_energy" or not context.telemetry.get("variant_runnable"):
        return None
    converged = context.telemetry.get("optimizer_converged")
    evaluations = context.telemetry.get("optimizer_evaluations")
    maximum = context.telemetry.get("max_evaluations")
    message = str(context.telemetry.get("optimizer_message", ""))
    try:
        evaluations_value = int(evaluations)
        maximum_value = int(maximum)
    except (TypeError, ValueError):
        return None
    exhausted = converged is False and (
        evaluations_value >= maximum_value
        or "maximum" in message.lower()
        or "exceeded" in message.lower()
    )
    if not exhausted or maximum_value >= 500:
        return None
    proposed = min(500, max(maximum_value + 10, maximum_value * 2))
    rule_id = "advisor.rule.optimizer_budget.v1"
    return RuleOutcome(
        title="Extend the optimizer budget",
        summary=f"The controller stopped after {evaluations_value} evaluations without satisfying its convergence flag.",
        explanation=(
            "The same external optimizer loop can be rerun with a larger bounded evaluation budget. This does "
            "not change the circuit family or the scientific acceptance rule."
        ),
        evidence_refs=(
            _ref("telemetry", "/telemetry/optimizer_converged", "Convergence flag", converged),
            _ref("telemetry", "/telemetry/optimizer_evaluations", "Completed evaluations", evaluations_value),
            _ref("request", "/telemetry/max_evaluations", "Declared maximum evaluations", maximum_value),
            _ref("telemetry", "/telemetry/optimizer_message", "Controller message", message),
        ),
        expected_effect="Give the existing controller more opportunities to improve the objective in a new run.",
        limitations=(
            "A larger budget does not guarantee convergence.",
            "The candidate must be resolved and rerun through the same pipeline with new Evidence.",
        ),
        patch=_patch(rule_id, context, field_path="/max_evaluations", proposed_value=proposed),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _warm_start(context: AdvisorContext) -> Optional[RuleOutcome]:
    previous = context.previous_run
    if previous is None or context.task_id != "ground_state_energy":
        return None
    if context.telemetry.get("optimizer_converged") is True:
        return None
    rule_id = "advisor.rule.warm_start.v1"
    return RuleOutcome(
        title="Warm-start from a compatible previous run",
        summary=f"Run {previous.run_id} provides final parameters for the same resolved realization fingerprint.",
        explanation=(
            "Only final parameters from a previous QCOL run of the same realization are eligible. Exact-reference "
            "amplitudes, exact eigenvectors, and reference-derived parameter vectors are excluded from the Advisor context."
        ),
        evidence_refs=(
            _ref("previous_run", "/previous_run/run_id", "Source run", previous.run_id),
            _ref("previous_run", "/previous_run/variant_fingerprint", "Source variant fingerprint", previous.variant_fingerprint),
            _ref("context", "/variant_fingerprint", "Current variant fingerprint", context.variant_fingerprint),
        ),
        expected_effect="Test whether a same-realization warm start improves controller behavior in a new run.",
        limitations=(
            "Warm-start parameters are not a scientific answer and do not inherit the previous run's acceptance.",
            "The exact reference remains inaccessible to this rule.",
        ),
        patch=_patch(
            rule_id,
            context,
            field_path="/initial_parameters",
            proposed_value=list(previous.final_parameters),
            source="previous_run.final_parameters",
            source_run_id=previous.run_id,
            same_variant_fingerprint=True,
        ),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _jw_ansatz_depth(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.variant_id != JW_GROUND_VARIANT or context.telemetry.get("optimizer_converged") is not False:
        return None
    layers = context.telemetry.get("ansatz_layers")
    try:
        layers_value = int(layers)
    except (TypeError, ValueError):
        return None
    if layers_value != 1:
        return None
    rule_id = "advisor.rule.jw_ansatz_depth.v1"
    return RuleOutcome(
        title="Compare the accepted two-layer JW ansatz",
        summary="The current accepted JW run used one ansatz layer and did not converge.",
        explanation=(
            "WP11 accepts one or two layers of the same mapped-fermionic FSWAP-routed ansatz. Changing the "
            "layer count is an execution hypothesis inside the accepted family, not a replacement by an unverified ansatz."
        ),
        evidence_refs=(
            _ref("request", "/telemetry/ansatz_layers", "Current ansatz layers", layers_value),
            _ref("telemetry", "/telemetry/optimizer_converged", "Convergence flag", False),
            _ref("context", "/variant_id", "Accepted JW realization", context.variant_id),
        ),
        expected_effect="Test whether additional accepted expressivity changes convergence or the verified result.",
        limitations=(
            "The deeper circuit may increase resource cost and need not improve the result.",
            "The new run receives a new evidence record; existing WP11 evidence is not reused as run evidence.",
        ),
        patch=_patch(rule_id, context, field_path="/parameters/ansatz_layers", proposed_value=2),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _seed_stability(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.task_id != "ground_state_energy" or not context.telemetry.get("variant_runnable"):
        return None
    if str(context.telemetry.get("result_status", "")).upper() not in {"REVIEW", "FAIL"}:
        return None
    # Scientific failures already have more specific no-patch cards.
    if context.stable_failure_codes:
        return None
    leakage = context.telemetry.get("sector_leakage")
    threshold = context.telemetry.get("sector_leakage_threshold")
    try:
        if leakage is not None and float(leakage) > float(threshold if threshold is not None else 1e-8):
            return None
    except (TypeError, ValueError):
        pass
    seed = context.telemetry.get("seed")
    try:
        seed_value = int(seed)
    except (TypeError, ValueError):
        return None
    proposed = 0 if seed_value >= 2147483647 else seed_value + 1
    rule_id = "advisor.rule.seed_stability.v1"
    return RuleOutcome(
        title="Check seed stability",
        summary="The run remains in REVIEW without a mapped scientific failure code.",
        explanation="A new deterministic seed can test whether the observed behavior is stable under the declared stochastic controls.",
        evidence_refs=(
            _ref("telemetry", "/telemetry/result_status", "Run status", context.telemetry.get("result_status")),
            _ref("telemetry", "/telemetry/seed", "Current seed", seed_value),
            _ref("context", "/stable_failure_codes", "Scientific failure codes", []),
        ),
        expected_effect="Produce an independent same-configuration run for a bounded seed-stability check.",
        limitations=(
            "A new seed does not repair an incompatible mapping or ansatz.",
            "The result must be compared through explicit evidence; no silent replacement occurs.",
        ),
        patch=_patch(rule_id, context, field_path="/seed", proposed_value=proposed),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _mapping_comparison(context: AdvisorContext) -> Optional[RuleOutcome]:
    if context.task_id != "mapping_analysis":
        return None
    current = [str(item) for item in context.telemetry.get("mapping_ids", []) if item]
    both = ["jordan_wigner.v1", "bravyi_kitaev.v1"]
    if set(current) == set(both):
        return RuleOutcome(
            title="JW and BK are already compared on the same input",
            summary="Both verified mapping-analysis plugins are present in this deterministic operator comparison.",
            explanation=(
                "The comparison may report qubit count, Pauli terms, Pauli weight, grouping estimates, and warnings. "
                "It must not claim that one exact mapping is universally more physically accurate."
            ),
            evidence_refs=(
                _ref("telemetry", "/telemetry/mapping_ids", "Mappings compared", current),
                _ref("resource", "/resource_report/mapping_resources", "Comparable resource reports", context.resource_report.get("mapping_resources", [])),
            ),
            expected_effect="Keep the mapping comparison bounded to operator equivalence and declared resource metrics.",
            limitations=("This is not a ground-state execution recommendation.",),
        )
    rule_id = "advisor.rule.mapping_comparison.v1"
    return RuleOutcome(
        title="Compare JW and BK resources on the same operator",
        summary="Only a subset of the mappings verified for mapping analysis is present in the current request.",
        explanation=(
            "The Advisor may propose both registered analysis mappings because the task is analysis-only. The "
            "patch does not enable BK VQE or choose a ground-state mapping."
        ),
        evidence_refs=(
            _ref("telemetry", "/telemetry/mapping_ids", "Current mapping-analysis candidates", current),
            _ref("governance", "/allowed_mapping_analysis_ids", "Verified analysis mappings", both),
        ),
        expected_effect="Generate comparable JW/BK operator-resource reports from the same FermionOperator and mode ordering.",
        limitations=(
            "The comparison is analysis-only and invokes no optimizer, shots, QASM circuit, or hardware backend.",
            "Resource ranking does not establish universal physical superiority.",
        ),
        patch=_patch(rule_id, context, field_path="/task_parameters/mapping_ids", proposed_value=both),
        kind=RecommendationKind.PATCH_HYPOTHESIS,
        epistemic_status=RecommendationEpistemicStatus.HYPOTHESIS,
    )


def _resource_review(context: AdvisorContext) -> Optional[RuleOutcome]:
    if "RESOURCE_ENVELOPE_EXCEEDED" not in context.stable_failure_codes:
        return None
    return RuleOutcome(
        title="Declared resource envelope exceeded",
        summary="The resolved composition is scientifically described, but its requested scale exceeds a declared resource limit.",
        explanation=(
            "A resource REVIEW is not a mapping-equivalence failure. The Advisor may report the limit and may "
            "only propose a reduction or alternative when an exact registered patch policy exists."
        ),
        evidence_refs=(
            _ref("compatibility", "/stable_failure_codes", "Resource failure code", "RESOURCE_ENVELOPE_EXCEEDED"),
            _ref("resource", "/resource_report", "Resolved resource report", context.resource_report),
        ),
        expected_effect="Keep the support boundary explicit and prevent an unsupported scale from entering runtime.",
        limitations=("No generic model-space reduction or mapping substitution is allow-listed in this release.",),
        kind=RecommendationKind.LIMITATION,
        epistemic_status=RecommendationEpistemicStatus.VERIFIED_LIMITATION,
    )


def build_advisor_rule_contracts() -> tuple[AdvisorRuleContract, ...]:
    return (
        AdvisorRuleContract(
            rule_id="advisor.rule.support_boundary.v1",
            rule_version="1.0.0",
            priority=10,
            phase=AdvisorRulePhase.SUPPORT_BOUNDARY,
            reason_code="MAPPING_SUPPORT_BOUNDARY",
            predicate_binding_id="advisor.binding.support_boundary.v1",
            output_kind=RecommendationKind.VERIFIED_FACT,
            title="Mapping support boundary",
            description="Publish governed Pair/JW/BK support facts without proposing unsupported execution.",
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.historical_jw_failure.v1",
            rule_version="1.0.0",
            priority=20,
            phase=AdvisorRulePhase.SCIENTIFIC_DIAGNOSTIC,
            reason_code="JW_COMPOSITION_REJECTED",
            predicate_binding_id="advisor.binding.historical_jw_failure.v1",
            output_kind=RecommendationKind.LIMITATION,
        
            title="Historical JW composition failure",
            description="Explain ANSATZ_GENERATOR_MAPPING_MISMATCH and emit no unsafe ansatz patch.",
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.bk_unresolved.v1",
            rule_version="1.0.0",
            priority=21,
            phase=AdvisorRulePhase.SCIENTIFIC_DIAGNOSTIC,
            reason_code="BK_EXECUTION_UNAVAILABLE",
            predicate_binding_id="advisor.binding.bk_unresolved.v1",
            output_kind=RecommendationKind.LIMITATION,
            title="BK execution unavailable",
            description="Explain the recognized-not-executable BK ground-state boundary.",
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.stale_evidence.v1",
            rule_version="1.0.0",
            priority=22,
            phase=AdvisorRulePhase.SCIENTIFIC_DIAGNOSTIC,
            reason_code="EVIDENCE_STALE_RERUN_REQUIRED",
            predicate_binding_id="advisor.binding.stale_evidence.v1",
            output_kind=RecommendationKind.LIMITATION,
            title="Stale evidence",
            description="Block reuse of mismatched acceptance evidence and request a fresh pipeline result.",
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.sector_leakage.v1",
            rule_version="1.0.0",
            priority=23,
            phase=AdvisorRulePhase.SCIENTIFIC_DIAGNOSTIC,
            reason_code="SECTOR_LEAKAGE_REQUIRES_REVIEW",
            predicate_binding_id="advisor.binding.sector_leakage.v1",
            output_kind=RecommendationKind.LIMITATION,
            title="Sector leakage",
            description="Report sector leakage without changing ansatz, mapping, or verification truth.",
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.sampling_uncertainty.v1",
            rule_version="1.0.0",
            priority=40,
            phase=AdvisorRulePhase.EXECUTION_DIAGNOSTIC,
            reason_code="REDUCE_SAMPLING_UNCERTAINTY",
            predicate_binding_id="advisor.binding.sampling_uncertainty.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Sampling uncertainty",
            description="Propose an allow-listed shot increase when statistical uncertainty is large.",
            applies_to_task_ids=("ground_state_energy",),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.optimizer_budget.v1",
            rule_version="1.0.0",
            priority=41,
            phase=AdvisorRulePhase.EXECUTION_DIAGNOSTIC,
            reason_code="EXTEND_OPTIMIZER_BUDGET",
            predicate_binding_id="advisor.binding.optimizer_budget.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Optimizer budget",
            description="Propose a bounded optimizer-budget extension after budget exhaustion.",
            applies_to_task_ids=("ground_state_energy",),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.warm_start.v1",
            rule_version="1.0.0",
            priority=42,
            phase=AdvisorRulePhase.EXECUTION_DIAGNOSTIC,
            reason_code="WARM_START_FROM_PREVIOUS_RUN",
            predicate_binding_id="advisor.binding.warm_start.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Warm start",
            description="Propose final parameters from a previous same-fingerprint QCOL run only.",
            applies_to_task_ids=("ground_state_energy",),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.jw_ansatz_depth.v1",
            rule_version="1.0.0",
            priority=43,
            phase=AdvisorRulePhase.EXECUTION_DIAGNOSTIC,
            reason_code="COMPARE_ACCEPTED_ANSATZ_DEPTH",
            predicate_binding_id="advisor.binding.jw_ansatz_depth.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Accepted JW ansatz depth",
            description="Compare one versus two layers inside the accepted WP11 ansatz family.",
            applies_to_task_ids=("ground_state_energy",),
            applies_to_variant_ids=(JW_GROUND_VARIANT,),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.seed_stability.v1",
            rule_version="1.0.0",
            priority=44,
            phase=AdvisorRulePhase.EXECUTION_DIAGNOSTIC,
            reason_code="CHECK_SEED_STABILITY",
            predicate_binding_id="advisor.binding.seed_stability.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Seed stability",
            description="Propose an independent seed when REVIEW is not explained by a scientific failure code.",
            applies_to_task_ids=("ground_state_energy",),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.mapping_comparison.v1",
            rule_version="1.0.0",
            priority=45,
            phase=AdvisorRulePhase.RESOURCE_DIAGNOSTIC,
            reason_code="COMPARE_MAPPING_RESOURCES",
            predicate_binding_id="advisor.binding.mapping_comparison.v1",
            output_kind=RecommendationKind.PATCH_HYPOTHESIS,
            title="Mapping comparison",
            description="Offer verified JW/BK analysis-only resource comparison on the same operator.",
            applies_to_task_ids=("mapping_analysis",),
            applies_to_variant_ids=(JW_ANALYSIS_VARIANT, BK_ANALYSIS_VARIANT),
        ),
        AdvisorRuleContract(
            rule_id="advisor.rule.resource_review.v1",
            rule_version="1.0.0",
            priority=46,
            phase=AdvisorRulePhase.RESOURCE_DIAGNOSTIC,
            reason_code="RESOURCE_LIMIT_REPORTED",
            predicate_binding_id="advisor.binding.resource_review.v1",
            output_kind=RecommendationKind.LIMITATION,
            title="Resource envelope",
            description="Report resource limits without inventing an unregistered reduction.",
        ),
    )


RULE_BINDINGS: Mapping[str, Predicate] = {
    "advisor.binding.support_boundary.v1": _support_boundary,
    "advisor.binding.historical_jw_failure.v1": _historical_jw_failure,
    "advisor.binding.bk_unresolved.v1": _bk_unresolved,
    "advisor.binding.stale_evidence.v1": _stale_evidence,
    "advisor.binding.sector_leakage.v1": _sector_leakage,
    "advisor.binding.sampling_uncertainty.v1": _sampling_uncertainty,
    "advisor.binding.optimizer_budget.v1": _optimizer_budget,
    "advisor.binding.warm_start.v1": _warm_start,
    "advisor.binding.jw_ansatz_depth.v1": _jw_ansatz_depth,
    "advisor.binding.seed_stability.v1": _seed_stability,
    "advisor.binding.mapping_comparison.v1": _mapping_comparison,
    "advisor.binding.resource_review.v1": _resource_review,
}


def rule_applies(rule: AdvisorRuleContract, context: AdvisorContext) -> bool:
    if rule.applies_to_task_ids and context.task_id not in rule.applies_to_task_ids:
        return False
    if rule.applies_to_variant_ids and context.variant_id not in rule.applies_to_variant_ids:
        return False
    return True


def evaluate_rule(rule: AdvisorRuleContract, context: AdvisorContext) -> Optional[RuleOutcome]:
    if not rule_applies(rule, context):
        return None
    try:
        predicate = RULE_BINDINGS[rule.predicate_binding_id]
    except KeyError as exc:
        raise RuntimeError(f"Advisor predicate binding is not registered: {rule.predicate_binding_id}") from exc
    return predicate(context)


__all__ = [
    "RuleOutcome",
    "Predicate",
    "RULE_BINDINGS",
    "build_advisor_rule_contracts",
    "rule_applies",
    "evaluate_rule",
]
