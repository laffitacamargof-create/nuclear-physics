"""Built-in project-wide semantic owners and governance facts.

This catalog is an audit manifest.  Runtime services do not consult it to
select scientific implementations; it checks that the implementation's real
ownership boundaries match the declared architecture.
"""
from __future__ import annotations

from .contracts import SemanticFactContract, SemanticOwnerContract
from .registry import SEMANTIC_AUTHORITY_REGISTRY

_REGISTERED = False


def register_builtin_semantic_authority() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    owner_specs = (
        ("owner.model_contract", "declarative_contract", "ModelContract",
         ("model physics", "physical parameter schema", "phenomenon", "degrees of freedom", "Hamiltonian components", "sector and reference capabilities"),
         ("resolver", "resource assessor", "UI", "Evidence"),
         ("aggregate resources", "backend behaviour", "UI layout")),
        ("owner.task_contract", "declarative_contract", "TaskContract",
         ("objective", "task/controller parameter schema", "controller semantics", "measurement requirements", "termination", "verification meaning"),
         ("resolver", "controller", "resource assessor", "UI", "Evidence"),
         ("model physics", "provider specifics")),
        ("owner.sector_policy", "declarative_policy", "SectorProfile / SectorPolicy",
         ("sector representation", "conserved-quantity diagnostics", "projector semantics"),
         ("resolver", "state preparation", "ansatz", "verification", "Evidence"),
         ("UI inference", "mapping selection")),
        ("owner.mapping_policy", "declarative_policy", "Mapping / Encoding Policy",
         ("encoding semantics", "ordering obligations", "mapped operator semantics"),
         ("resolver", "state preparation", "ansatz", "resource assessor", "Evidence"),
         ("model phenomenon", "task objective")),
        ("owner.state_preparation_policy", "declarative_policy", "StatePreparationPolicy",
         ("reference-state encoding", "state-preparation semantics"),
         ("resolver", "runtime", "Evidence"),
         ("model physics", "ansatz parameterization")),
        ("owner.ansatz_policy", "declarative_policy", "AnsatzPolicy",
         ("ansatz family", "generator semantics", "variational parameter schema", "sharing and layer semantics"),
         ("resolver", "resource assessor", "controller", "UI", "Evidence"),
         ("total backend cost", "UI display logic")),
        ("owner.measurement_policy", "declarative_policy", "MeasurementPolicy",
         ("measurement semantics", "grouping requirements", "reconstruction inputs"),
         ("resolver", "resource assessor", "runtime", "Evidence"),
         ("model physics", "UI layout")),
        ("owner.execution_target", "execution_contract", "ExecutionTarget / ExecutionRequestContract",
         ("execution parameter schema", "backend capabilities", "connectivity", "native gate and execution constraints"),
         ("resolver", "resource assessor", "ExecutionAdapter", "UI", "Evidence"),
         ("model physics", "ansatz generator semantics")),
        ("owner.model_instance_adapter", "boundary_adapter", "ModelInstance Adapter",
         ("request-to-instance translation", "contract-declared fixed values", "validated instance identity"),
         ("resolver", "resource assessor", "UI", "Evidence"),
         ("invented scientific defaults", "silent model substitution", "UI policy")),
        ("owner.capability_resolver", "composition_service", "Capability Resolver / Composition Root",
         ("compatibility", "implementation selection", "global composition invariants", "resolved realization identity"),
         ("resource assessor", "shared pipeline", "UI", "Evidence"),
         ("redefinition of physics", "family-based resource formulas")),
        ("owner.resource_assessor", "derivation_service", "ResourceAssessor",
         ("aggregate resource reports", "resource fingerprints", "resource-envelope decision"),
         ("resolver", "UI", "Advisor", "Comparison", "Evidence"),
         ("model-family heuristics", "UI values", "scientific compatibility")),
        ("owner.shared_pipeline", "orchestration_service", "Shared Execution Pipeline",
         ("station ordering", "artifact handoff", "controller-to-execution flow", "evidence handoff"),
         ("ExecutionAdapter", "Evidence", "UI"),
         ("model-specific scientific re-selection", "direct backend invocation")),
        ("owner.execution_adapter", "transport_service", "ExecutionAdapter",
         ("serialization", "transport", "backend invocation", "result normalization"),
         ("shared pipeline", "Evidence", "UI"),
         ("Hamiltonian interpretation", "sector", "ansatz semantics")),
        ("owner.evidence_service", "evidence_service", "Evidence Service",
         ("identity", "freshness", "provenance", "acceptance metadata"),
         ("verification", "Advisor", "Comparison", "UI"),
         ("recalculation of physics", "result repair")),
        ("owner.failure_model", "failure_contract", "Failure Model",
         ("failure schema", "failure namespaces", "station-local failure semantics"),
         ("resolver", "pipeline", "UI", "Evidence"),
         ("scientific recovery decisions",)),
        ("owner.model_catalog", "catalog_metadata", "User Navigation Catalog",
         ("navigation grouping", "display labels", "browse order"),
         ("UI", "documentation"),
         ("parameter counting", "mapping selection", "ansatz selection", "sector selection", "task compatibility", "resource calculation")),
        ("owner.ui", "presentation_layer", "User Interface",
         ("user input collection", "presentation", "explanation"),
         ("model catalog", "model contracts", "resolved plans", "resource reports", "evidence views"),
         ("parameter counting", "scientific compatibility", "resource formulas")),
    )
    for owner_id, kind, label, responsibilities, consumers, forbidden in owner_specs:
        SEMANTIC_AUTHORITY_REGISTRY.register_owner(SemanticOwnerContract(
            owner_id, "1.0.0", kind, label, responsibilities, consumers, forbidden
        ))

    facts = (
        SemanticFactContract("fact.scientific.model_definition", "1.1.0", "Model physics and physical-parameter schema", "owner.model_contract", "declared", (), ("owner.capability_resolver", "owner.resource_assessor", "owner.ui", "owner.evidence_service"), ("owner.ui", "owner.resource_assessor", "owner.model_catalog"), "ModelContract owns the physical problem definition and model parameters."),
        SemanticFactContract("fact.presentation.model_grouping", "1.1.0", "Navigation-only user grouping", "owner.model_catalog", "declared", (), ("owner.ui",), ("owner.capability_resolver", "owner.resource_assessor"), "Oscillators, Fermions, and Custom are user navigation only."),
        SemanticFactContract("fact.presentation.descriptive_taxonomy", "1.1.0", "Descriptive taxonomy and discovery tags", "owner.model_catalog", "derived", ("fact.scientific.model_definition",), ("owner.ui", "owner.evidence_service"), ("owner.capability_resolver", "owner.resource_assessor"), "Descriptive taxonomy is a read-only projection and is excluded from scientific identity."),
        SemanticFactContract("fact.scientific.model_instance", "1.0.0", "Validated requested model instance", "owner.model_instance_adapter", "derived", ("fact.scientific.model_definition",), ("owner.capability_resolver", "owner.resource_assessor", "owner.ui", "owner.evidence_service"), ("owner.ui", "owner.model_catalog"), "The boundary adapter turns the request into one validated ModelInstance."),
        SemanticFactContract("fact.scientific.task_requirements", "1.1.0", "Task computation and controller requirements", "owner.task_contract", "declared", (), ("owner.capability_resolver", "owner.resource_assessor", "owner.ui", "owner.evidence_service"), ("owner.ui",), "TaskContract owns task/controller inputs and semantics."),
        SemanticFactContract("fact.scientific.sector_semantics", "1.0.0", "Sector and conserved-quantity semantics", "owner.sector_policy", "declared", ("fact.scientific.model_definition",), ("owner.capability_resolver", "owner.resource_assessor", "owner.evidence_service"), ("owner.ui", "owner.model_catalog"), "SectorProfile owns the representation and diagnostic of conserved quantities."),
        SemanticFactContract("fact.scientific.encoding_semantics", "1.0.0", "Mapping and encoding semantics", "owner.mapping_policy", "declared", ("fact.scientific.model_definition",), ("owner.capability_resolver", "owner.resource_assessor", "owner.evidence_service"), ("owner.ui", "owner.model_catalog"), "MappingPolicy owns qubit meaning, ordering, and transformed-operator semantics."),
        SemanticFactContract("fact.scientific.state_preparation", "1.0.0", "State-preparation semantics", "owner.state_preparation_policy", "declared", ("fact.scientific.model_definition", "fact.scientific.sector_semantics", "fact.scientific.encoding_semantics"), ("owner.capability_resolver", "owner.evidence_service"), ("owner.ui",), "StatePreparationPolicy owns the encoded reference-state construction."),
        SemanticFactContract("fact.scientific.ansatz_parameterization", "1.1.0", "Ansatz structure and variational parameter schema", "owner.ansatz_policy", "declared", ("fact.scientific.encoding_semantics", "fact.scientific.sector_semantics"), ("owner.capability_resolver", "owner.resource_assessor", "owner.ui", "owner.evidence_service"), ("owner.ui", "owner.model_catalog"), "AnsatzPolicy owns variational parameterization; ModelFamily owns neither."),
        SemanticFactContract("fact.scientific.measurement_semantics", "1.0.0", "Measurement and grouping semantics", "owner.measurement_policy", "declared", ("fact.scientific.model_definition", "fact.scientific.task_requirements"), ("owner.capability_resolver", "owner.resource_assessor", "owner.evidence_service"), ("owner.ui",), "MeasurementPolicy owns basis/grouping and reconstruction requirements."),
        SemanticFactContract("fact.execution.target_constraints", "1.1.0", "Execution parameter schema and target constraints", "owner.execution_target", "declared", (), ("owner.capability_resolver", "owner.resource_assessor", "owner.execution_adapter", "owner.ui", "owner.evidence_service"), ("owner.ui",), "ExecutionTarget owns shots, seed, backend, and provider constraints."),
        SemanticFactContract("fact.scientific.resolved_realization", "1.1.0", "Authoritative resolved scientific composition", "owner.capability_resolver", "derived", ("fact.scientific.model_definition", "fact.scientific.model_instance", "fact.scientific.task_requirements", "fact.scientific.sector_semantics", "fact.scientific.encoding_semantics", "fact.scientific.state_preparation", "fact.scientific.ansatz_parameterization", "fact.scientific.measurement_semantics"), ("owner.resource_assessor", "owner.shared_pipeline", "owner.ui", "owner.evidence_service"), ("owner.ui", "owner.shared_pipeline"), "ResolvedRealization is the composition root. Downstream services may consume it but may not reconstruct scientific choices."),
        SemanticFactContract("fact.resource.ansatz_parameter_count", "1.1.0", "Derived variational parameter count", "owner.resource_assessor", "derived", ("fact.scientific.ansatz_parameterization", "fact.scientific.resolved_realization"), ("owner.capability_resolver", "owner.ui", "owner.evidence_service"), ("owner.ui", "owner.model_catalog"), "ResourceAssessor derives parameter count from the exact ansatz policy and resolved scale."),
        SemanticFactContract("fact.resource.aggregate_report", "1.1.0", "Aggregate resource report", "owner.resource_assessor", "derived", ("fact.scientific.resolved_realization", "fact.execution.target_constraints", "fact.resource.ansatz_parameter_count", "fact.scientific.measurement_semantics"), ("owner.capability_resolver", "owner.ui", "owner.evidence_service"), ("owner.ui",), "Aggregate resources are derived from the complete resolved composition."),
        SemanticFactContract("fact.execution.shared_pipeline_flow", "1.1.0", "Canonical shared-pipeline orchestration", "owner.shared_pipeline", "derived", ("fact.scientific.resolved_realization", "fact.scientific.task_requirements"), ("owner.execution_adapter", "owner.evidence_service", "owner.ui"), ("owner.model_contract", "owner.task_contract", "owner.ui"), "The shared pipeline consumes the composition root and owns station ordering only."),
        SemanticFactContract("fact.execution.canonical_result", "1.0.0", "Canonical backend execution record", "owner.execution_adapter", "derived", ("fact.execution.shared_pipeline_flow", "fact.execution.target_constraints"), ("owner.shared_pipeline", "owner.evidence_service", "owner.ui"), ("owner.model_contract", "owner.ui"), "ExecutionAdapter owns transport, backend invocation, and normalization."),
        SemanticFactContract("fact.evidence.identity_freshness_provenance", "1.0.0", "Evidence identity, freshness, and provenance", "owner.evidence_service", "derived", ("fact.scientific.resolved_realization", "fact.resource.aggregate_report", "fact.execution.canonical_result"), ("owner.ui", "owner.capability_resolver"), ("owner.ui",), "Evidence proves the exact identity and becomes stale when semantic inputs change."),
        SemanticFactContract("fact.failure.unified_record", "1.0.0", "Unified failure record", "owner.failure_model", "declared", (), ("owner.capability_resolver", "owner.shared_pipeline", "owner.execution_adapter", "owner.evidence_service", "owner.ui"), (), "Expected architectural failures use one FailureRecord schema and stable namespaces."),
    )
    for fact in facts:
        SEMANTIC_AUTHORITY_REGISTRY.register_fact(fact)
    _REGISTERED = True


register_builtin_semantic_authority()
