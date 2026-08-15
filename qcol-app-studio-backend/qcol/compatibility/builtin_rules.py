"""The nine initial versioned compatibility rules required by WP4."""
from __future__ import annotations

from qcol.compatibility.failure_codes import CompatibilityFailureCode
from qcol.mapping_policies import Severity

from .bindings import PREDICATE_BINDING_VERSION, PREDICATE_CONVENTION_ID
from .enums import CompatibilityParticipant as P
from .enums import CompatibilityRulePhase as Phase
from .rule_contracts import CompatibilityRuleContract


RULES: tuple[CompatibilityRuleContract, ...] = (
    CompatibilityRuleContract(
        rule_id="model_mapping.domain.v1",
        rule_version="1.0.0",
        display_name="Model ↔ Mapping domain",
        phase=Phase.PAIRWISE,
        participants=(P.MODEL, P.MAPPING),
        predicate_binding_id="compatibility.predicate.model_mapping_domain.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.MAPPING_DOMAIN_MISMATCH,
        severity=Severity.FATAL,
        pass_condition=(
            "Operator type, physical domain, required metadata, Hermiticity, "
            "and declared symmetries fit the mapping scope."
        ),
        required_evidence=(
            "model.operator_type",
            "model.physical_domain",
            "model.metadata",
            "model.hermiticity",
            "mapping.operator_domain",
        ),
        suggested_action=(
            "Choose a mapping whose declared domain contains the model or add "
            "a scientifically reviewed adapter."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="mapping_sector.representation.v1",
        rule_version="1.0.0",
        display_name="Mapping ↔ Sector representation",
        phase=Phase.PAIRWISE,
        participants=(P.MAPPING, P.SECTOR, P.TASK),
        predicate_binding_id="compatibility.predicate.mapping_sector_representation.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.SECTOR_REPRESENTATION_UNAVAILABLE,
        severity=Severity.FATAL,
        pass_condition=(
            "Every conserved quantity required by the model/task has an "
            "explicit accepted SectorEncodingProfile and diagnostic."
        ),
        required_evidence=(
            "task.required_conserved_quantities",
            "mapping.sector_profiles",
            "sector.target",
        ),
        suggested_action=(
            "Choose a mapping with a registered sector profile or add an "
            "accepted mapped observable/projector."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="mapping_state.encoder_match.v1",
        rule_version="1.0.0",
        display_name="Mapping ↔ Initial state encoder",
        phase=Phase.PAIRWISE,
        participants=(P.MAPPING, P.STATE_PREPARATION, P.SECTOR, P.ORDERING),
        predicate_binding_id="compatibility.predicate.mapping_state_encoder_match.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.INITIAL_STATE_ENCODING_MISMATCH,
        severity=Severity.FATAL,
        pass_condition=(
            "The state uses the exact mapping convention and order, lies in "
            "the code space, and matches the target sector."
        ),
        required_evidence=(
            "state.mapping_policy_id",
            "state.mapping_convention_id",
            "state.encoding_context_fingerprint",
            "state.code_space",
            "state.target_sector",
        ),
        suggested_action=(
            "Use the state encoder registered for the exact mapping convention "
            "and shared EncodingContext."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="mapping_ansatz.generator_semantics.v1",
        rule_version="1.0.0",
        display_name="Mapping ↔ Ansatz generator semantics",
        phase=Phase.PAIRWISE,
        participants=(P.MAPPING, P.ANSATZ, P.SECTOR, P.ORDERING),
        predicate_binding_id="compatibility.predicate.mapping_ansatz_generator_semantics.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.ANSATZ_GENERATOR_MAPPING_MISMATCH,
        severity=Severity.FATAL,
        pass_condition=(
            "The ansatz supplies the abstract capabilities required by the "
            "mapping, uses the same convention/order, and carries current "
            "mapped-generator or mapping-native equivalence evidence."
        ),
        required_evidence=(
            "ansatz.semantic_class",
            "ansatz.provided_capabilities",
            "ansatz.generator_equivalence",
            "ansatz.invariants",
        ),
        suggested_action=(
            "Use generators mapped by the selected policy, a fermionic-swap "
            "construction, or accepted mapping-native equivalence evidence."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="mapping_task.all_operators_mapped.v1",
        rule_version="1.0.0",
        display_name="Mapping ↔ Task operator coverage",
        phase=Phase.PAIRWISE,
        participants=(P.MAPPING, P.TASK, P.MEASUREMENT),
        predicate_binding_id="compatibility.predicate.mapping_task_all_operators_mapped.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.TASK_OPERATOR_NOT_MAPPABLE,
        severity=Severity.FATAL,
        pass_condition=(
            "The Hamiltonian and every observable, penalty, excitation, or "
            "evolution generator required by the task are transformable."
        ),
        required_evidence=(
            "task.required_operator_kinds",
            "mapping.transformable_operator_kinds",
        ),
        suggested_action=(
            "Select a mapping that covers every task operator or implement and "
            "accept the missing transformation."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="model_task_reference.same_problem.v1",
        rule_version="1.0.0",
        display_name="Model/Task ↔ Independent reference",
        phase=Phase.PAIRWISE,
        participants=(P.MODEL, P.TASK, P.REFERENCE, P.SECTOR, P.ORDERING),
        predicate_binding_id="compatibility.predicate.model_task_reference_same_problem.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.REFERENCE_SECTOR_MISMATCH,
        severity=Severity.FATAL,
        pass_condition=(
            "The reference describes the same source problem, quantity, units, "
            "order, sector, constant shift, and declared scale, and is "
            "independent of the tested mapping implementation."
        ),
        required_evidence=(
            "reference.source_problem_fingerprint",
            "reference.task_quantity",
            "reference.sector",
            "reference.validity_envelope",
            "reference.independence",
        ),
        suggested_action=(
            "Rebuild an independent reference from the same source-domain "
            "problem and declared sector."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="ordering.same_context.v1",
        rule_version="1.0.0",
        display_name="Ordering ↔ Complete tuple",
        phase=Phase.GLOBAL_INVARIANT,
        participants=(P.ORDERING, P.COMPLETE_TUPLE),
        predicate_binding_id="compatibility.predicate.ordering_same_context.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.MODE_ORDER_CONTEXT_MISMATCH,
        severity=Severity.FATAL,
        pass_condition=(
            "Every component in the resolved tuple carries the same "
            "EncodingContext fingerprint."
        ),
        required_evidence=(
            "ordering.encoding_context_fingerprint",
            "ordering.component_context_fingerprints",
        ),
        suggested_action=(
            "Resolve one shared EncodingContext and rebuild every dependent "
            "artifact from it."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="composition.resource_envelope.v1",
        rule_version="1.0.0",
        display_name="Complete tuple ↔ Resource envelope",
        phase=Phase.GLOBAL_INVARIANT,
        participants=(P.COMPLETE_TUPLE, P.RESOURCES),
        predicate_binding_id="compatibility.predicate.composition_resource_envelope.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.RESOURCE_ENVELOPE_EXCEEDED,
        severity=Severity.REVIEW,
        pass_condition=(
            "The instance-specific operator/circuit estimates remain inside the "
            "declared executable resource envelope."
        ),
        required_evidence=(
            "resources.instance_estimate",
            "resources.declared_envelope",
        ),
        suggested_action=(
            "Reduce the declared scale, select a lower-cost realization, or "
            "expand and reaccept the resource envelope."
        ),
    ),
    CompatibilityRuleContract(
        rule_id="composition.acceptance_fingerprint.v1",
        rule_version="1.0.0",
        display_name="Complete tuple ↔ Acceptance evidence fingerprint",
        phase=Phase.GLOBAL_INVARIANT,
        participants=(P.COMPLETE_TUPLE, P.ACCEPTANCE_EVIDENCE),
        predicate_binding_id="compatibility.predicate.composition_acceptance_fingerprint.v1",
        predicate_binding_version=PREDICATE_BINDING_VERSION,
        predicate_convention_id=PREDICATE_CONVENTION_ID,
        failure_code=CompatibilityFailureCode.ACCEPTANCE_EVIDENCE_STALE,
        severity=Severity.FATAL,
        pass_condition=(
            "Current evidence matches the exact policy versions, ordering, "
            "sector, task, dependencies, and declared scale of the tuple."
        ),
        required_evidence=(
            "acceptance.resolved_variant_fingerprint",
            "acceptance.evidence_fingerprint",
            "acceptance.freshness_status",
        ),
        suggested_action=(
            "Rerun the exact acceptance suite and issue evidence for the current "
            "resolved tuple and scale."
        ),
    ),
)


RULE_IDS = tuple(rule.rule_id for rule in RULES)


__all__ = ["RULES", "RULE_IDS"]
