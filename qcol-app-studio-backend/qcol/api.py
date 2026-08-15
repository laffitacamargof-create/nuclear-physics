"""FastAPI + replayable SSE service for the QCOL model registry.

The service is a transport layer only.  It creates run records and consumes the
same ``run_pipeline_stream`` used by Gradio; it does not rebuild Hamiltonians,
optimizers, execution, reconstruction, or verification.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .catalog import get_catalog
from .fermion_registry import FermionProblemContractError, get_fermion_problem_spec, public_fermion_problem_catalog
from .model_contracts import ModelContractError
from .request_boundaries import copy_plain_data
from .model_registry import get_model_contract, public_model_registry
from .model_ui_schema import public_model_ui_schema, public_qho_ui_catalog
from .semantic_authority import (
    public_semantic_authority_catalog,
    semantic_authority_catalog_fingerprint,
    semantic_leakage_audit,
)
from .execution import public_execution_adapter_catalog
from .state import public_state_boundary_contract
from .policy_registries import public_policy_catalog
from .task_registry import get_task_contract, public_task_registry
from .task_policy_registries import public_task_policy_catalog
from .model_task_matrix import public_model_task_matrix
from .mappings import get_mapping_plugin, public_mapping_registry
from .acceptance.mapping_baseline import public_mapping_realization_baseline
from .compatibility import (
    build_wp4_rule_registry,
    public_compatibility_rule_catalog,
    public_failure_code_registry,
)
from .mapping_policies import public_mapping_realization_vocabulary
from .policy_contract_catalog import public_declarative_policy_contract_catalog
from .mapping_policies import (
    public_pair_mapping_migration_catalog,
    public_spin_orbital_mapping_migration_catalog,
    public_a3_2b_exit_decision,
)
from .mapping_policies.profiles import (
    public_wp11_jw_accepted_composition_catalog,
    build_wp11_acceptance_record,
)
from .implementation_bindings import (
    build_wp3_example_registries,
    public_implementation_binding_catalog,
)
from .realization_variants import (
    RealizationVariantResolver,
    build_wp5_candidates,
    build_wp5_fixture_registries,
    public_realization_resolver_catalog,
    public_model_task_realization_catalog,
    get_model_task_realization_view,
    get_public_realization_variant,
)
from .acceptance import (
    public_acceptance_fingerprint_catalog,
    public_acceptance_harness_catalog,
    public_wp12_surface_catalog,
)
from .governance import (
    public_governance_catalog,
    get_governed_asset,
    get_published_status,
    public_allowed_request_patch_registry,
    validate_advisor_request_patch,
    build_phase_b_handoff_contract,
    build_a3_2c_release_decision,
)
from .advisor import (
    SCENARIO_IDS,
    AdvisorContextError,
    advise_run_payload,
    build_advisor_context_fixture,
    deterministic_advisor_catalog_fingerprint,
    deterministic_advisor_rule_catalog_fingerprint,
    evaluate_advisor_context,
    prepare_candidate_request_plan,
    public_deterministic_advisor_catalog,
)
from .run_manager import RunManager, StoredEvent, service_json_safe
from .scientific_core import public_user_navigation_catalog, public_scientific_core_view, public_scientific_core_catalog
from .parameter_ownership import public_parameter_ownership_catalog
from .failure_model import public_failure_model_contract
from .composition_root import public_composition_root_contract
from .architecture_gates import public_architecture_gate_report
from .registry_consistency import public_registry_consistency_report
from .versioning import public_version_compatibility_policy
from .observability import public_observability_contract
from .freeze_manifest import build_unified_baseline_candidate_manifest
from .environment_gate import public_environment_scope_policy
from .evidence_transfer import public_execution_evidence_transferability_contract
from .freeze_sequence import public_unified_freeze_sequence_contract

from .comparison import (
    SCENARIO_IDS as PHASE_C_SCENARIO_IDS,
    build_phase_c_scenario,
    phase_c_catalog_fingerprint,
    public_comparison_policy_catalog,
    public_phase_c_catalog,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLIENT_FILE = PROJECT_ROOT / "docs" / "PHASE_A2B_SSE_CLIENT.html"
WEB_DIR = Path(__file__).resolve().parent / "web"
DASHBOARD_FILE = WEB_DIR / "index.html"
_DEFAULT_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:7860",
    "http://localhost:7860",
    # QCOL Quantum App Studio hosted by the public GitHub Pages ecosystem.
    "https://laffitacamargof-create.github.io",
]


def _cors_origins() -> list[str]:
    raw = os.getenv("QCOL_CORS_ORIGINS", "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()] or _DEFAULT_ORIGINS


app = FastAPI(
    title="QCOL Model × Task Registry + Capability Resolver Runtime API",
    version=__version__,
    description=(
        "QCOL model × task service: inspect model contracts and callable policy registries, resolve capabilities, load problem-specific schemas, submit a no-code physics-model request, stream the live "
        "journey through SSE, recover or cancel a run, inspect honest public views, "
        "and download final or interrupted evidence. Phase B adds a deterministic, read-only Advisor. Phase C requires explicit approval, reruns the candidate through the same pipeline, compares both evidence records under a declared uncertainty policy, and records ADOPT, REJECT, or INCONCLUSIVE without silent replacement."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

_manager: Optional[RunManager] = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        root = Path(os.getenv("QCOL_API_EVIDENCE_ROOT", "qcol_api_evidence"))
        _manager = RunManager(evidence_root=root)
    return _manager


def set_run_manager_for_testing(manager: Optional[RunManager]) -> None:
    global _manager
    _manager = manager


app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    if not DASHBOARD_FILE.exists():
        raise HTTPException(status_code=404, detail="QCOL dashboard file is missing.")
    return FileResponse(
        DASHBOARD_FILE,
        media_type="text/html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/catalog")
def catalog(response: Response) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return get_catalog()


@app.get("/catalog/model-contracts")
def model_contract_catalog() -> Dict[str, Any]:
    return public_model_registry()


@app.get("/catalog/model-contracts/{model_id:path}")
def model_contract_schema(model_id: str) -> Dict[str, Any]:
    try:
        return get_model_contract(model_id).to_dict()
    except ModelContractError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/model-ui-schemas/{model_id:path}")
def model_ui_schema(model_id: str) -> Dict[str, Any]:
    """Return the schema-driven UI description for one ModelContract."""
    try:
        return public_model_ui_schema(model_id)
    except ModelContractError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/qho-models")
def qho_model_catalog() -> Dict[str, Any]:
    """Return the four QHO contracts and their rendered parameter schemas."""
    return public_qho_ui_catalog()


@app.get("/catalog/semantic-authority")
def semantic_authority_catalog() -> Dict[str, Any]:
    """Publish the one-fact/one-owner architecture contract."""
    catalog = public_semantic_authority_catalog()
    return {
        "catalog": catalog,
        "fingerprint": semantic_authority_catalog_fingerprint(),
    }


@app.get("/catalog/user-navigation")
def user_navigation_catalog() -> Dict[str, Any]:
    return public_user_navigation_catalog()


@app.get("/catalog/scientific-core")
def scientific_core_catalog() -> Dict[str, Any]:
    return public_scientific_core_catalog()


@app.get("/catalog/scientific-core/{model_id:path}")
def scientific_core_model(model_id: str) -> Dict[str, Any]:
    try:
        return public_scientific_core_view(model_id)
    except ModelContractError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/parameter-ownership")
def parameter_ownership_catalog(model_id: str | None = None, task_id: str | None = None) -> Dict[str, Any]:
    return public_parameter_ownership_catalog(model_id=model_id, task_id=task_id)


@app.get("/catalog/failure-model")
def failure_model_catalog() -> Dict[str, Any]:
    return public_failure_model_contract()


@app.get("/catalog/composition-root")
def composition_root_catalog() -> Dict[str, Any]:
    return public_composition_root_contract()


@app.get("/catalog/architecture-gates")
def architecture_gate_catalog() -> Dict[str, Any]:
    return public_architecture_gate_report(PROJECT_ROOT)


@app.get("/catalog/registry-consistency")
def registry_consistency_catalog() -> Dict[str, Any]:
    return public_registry_consistency_report()


@app.get("/catalog/version-policy")
def version_policy_catalog() -> Dict[str, Any]:
    return public_version_compatibility_policy()


@app.get("/catalog/observability")
def observability_catalog() -> Dict[str, Any]:
    return public_observability_contract()


@app.get("/catalog/state-boundary")
def state_boundary_catalog() -> Dict[str, Any]:
    return public_state_boundary_contract()


@app.get("/catalog/unified-baseline-candidate")
def unified_baseline_candidate_catalog() -> Dict[str, Any]:
    return build_unified_baseline_candidate_manifest(PROJECT_ROOT)


@app.get("/catalog/environment-scope-policy")
def environment_scope_policy_catalog() -> Dict[str, Any]:
    return public_environment_scope_policy()


@app.get("/catalog/execution-evidence-transferability")
def execution_evidence_transferability_catalog() -> Dict[str, Any]:
    return public_execution_evidence_transferability_contract()


@app.get("/catalog/unified-freeze-sequence")
def unified_freeze_sequence_catalog() -> Dict[str, Any]:
    return public_unified_freeze_sequence_contract()


@app.get("/catalog/model-classifications")
def model_classification_catalog() -> Dict[str, Any]:
    rows = []
    for contract in public_model_registry()["contracts"]:
        rows.append({
            "model_id": contract["model_id"],
            "model_version": contract["model_version"],
            "family": contract.get("family"),
            "family_authority": contract.get("family_authority"),
            "classification": contract.get("classification"),
        })
    return {
        "schema_version": "qcol-model-classification-catalog/1.0",
        "models": rows,
        "rule": "Classification is metadata; scientific behaviour comes from resolved contracts and policies.",
    }


@app.get("/catalog/semantic-leakage-audit")
def semantic_leakage_audit_catalog() -> Dict[str, Any]:
    return semantic_leakage_audit(PROJECT_ROOT)


@app.get("/catalog/execution-adapters")
def execution_adapter_catalog() -> Dict[str, Any]:
    return public_execution_adapter_catalog()


@app.get("/catalog/architecture-decisions")
def architecture_decision_catalog() -> Dict[str, Any]:
    """Publish the accepted ownership, taxonomy, resource, and execution ADRs."""
    from .hardening.semantic_authority import build_architecture_decision_record_catalog

    return build_architecture_decision_record_catalog(PROJECT_ROOT)


@app.get("/catalog/pre-unified-baseline-quality-gate")
def pre_unified_baseline_quality_gate() -> Dict[str, Any]:
    """Publish the MUST semantic-authority/ownership freeze gate."""
    from .hardening.semantic_authority import (
        build_semantic_authority_hardening_manifest,
        validate_semantic_authority_hardening,
    )

    return copy_plain_data({
        "manifest": build_semantic_authority_hardening_manifest(PROJECT_ROOT),
        "validation": validate_semantic_authority_hardening(PROJECT_ROOT),
    })


@app.get("/catalog/task-contracts")
def task_contract_catalog() -> Dict[str, Any]:
    return public_task_registry()


@app.get("/catalog/task-contracts/{task_id:path}")
def task_contract_schema(task_id: str) -> Dict[str, Any]:
    try:
        return get_task_contract(task_id).to_dict()
    except ModelContractError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/model-task-matrix")
def model_task_matrix_catalog() -> Dict[str, Any]:
    return public_model_task_matrix()


@app.get("/catalog/model-task-realizations")
def model_task_realization_catalog() -> Dict[str, Any]:
    """Publish WP12 internal realization variants without adding matrix axes."""
    return public_model_task_realization_catalog()


@app.get("/catalog/wp12-model-task-surface")
def wp12_model_task_surface_catalog() -> Dict[str, Any]:
    """Publish the WP12 simple matrix, internal variants, and station-local errors."""
    return public_wp12_surface_catalog()


@app.get("/catalog/model-task-realizations/cell/{model_id}/{task_id}")
def model_task_realization_cell(model_id: str, task_id: str) -> Dict[str, Any]:
    """Return the internal realization variants for one public Model × Task cell."""
    try:
        return get_model_task_realization_view(model_id, task_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/model-task-realizations/variant/{variant_id:path}/eligibility")
def model_task_realization_variant_eligibility(variant_id: str) -> Dict[str, Any]:
    """Expose runnable/blocked status without attempting scientific execution."""
    try:
        variant = get_public_realization_variant(variant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "schema_version": "qcol-realization-variant-eligibility/1.0",
        "variant_id": variant.variant_id,
        "cell_id": variant.cell_id,
        "runnable": variant.runnable,
        "selectable": variant.selectable,
        "runtime_status": variant.runtime_status,
        "runtime_path": variant.runtime_path,
        "failure_code": variant.failure_code,
        "failure_message": variant.failure_message,
        "suggested_action": variant.suggested_action,
        "callable_payload_withheld": True,
    }


@app.get("/catalog/model-task-realizations/variant/{variant_id:path}")
def model_task_realization_variant(variant_id: str) -> Dict[str, Any]:
    """Return one exact public realization variant and its honest support boundary."""
    try:
        return get_public_realization_variant(variant_id).to_dict()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/task-policy-registries")
def task_policy_registry_catalog() -> Dict[str, Any]:
    return public_task_policy_catalog()


@app.post("/catalog/model-task/resolve")
def resolve_model_task_capability(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    from .model_task_resolver import resolve_model_task_request
    try:
        return resolve_model_task_request(dict(payload or {})).to_dict()
    except ModelContractError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "model_task_resolution_error", "message": str(exc)},
        ) from exc


@app.get("/catalog/mappings")
def mapping_plugin_catalog() -> Dict[str, Any]:
    return public_mapping_registry()


@app.get("/catalog/mappings/{mapping_id:path}")
def mapping_plugin_schema(mapping_id: str) -> Dict[str, Any]:
    try:
        plugin = get_mapping_plugin(mapping_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return plugin.public_descriptor()


@app.get("/catalog/mapping-realization-baseline")
def mapping_realization_baseline_catalog() -> Dict[str, Any]:
    """Publish the WP0 frozen mapper/composition/cell truth without executing a run."""
    return public_mapping_realization_baseline()


@app.get("/catalog/compatibility-failure-codes")
def compatibility_failure_code_catalog() -> Dict[str, Any]:
    """Publish stable scientific compatibility failure identifiers."""
    return public_failure_code_registry()


@app.get("/catalog/mapping-realization-vocabulary")
def mapping_realization_vocabulary_catalog() -> Dict[str, Any]:
    """Publish the WP1 dependency-light mapping-realization vocabulary."""
    return public_mapping_realization_vocabulary()

@app.get("/catalog/mapping-realization-policy-contracts")
def mapping_realization_policy_contract_catalog() -> Dict[str, Any]:
    """Publish WP2 frozen strict-JSON contract schemas and non-live examples."""
    return public_declarative_policy_contract_catalog()


@app.get("/catalog/mapping-realization-implementation-bindings")
def mapping_realization_implementation_binding_catalog() -> Dict[str, Any]:
    """Publish WP3 binding descriptors, exact resolution reports, and withheld callables."""
    return public_implementation_binding_catalog()


@app.get("/catalog/mapping-realization-implementation-bindings/{binding_id:path}")
def mapping_realization_implementation_binding_schema(binding_id: str) -> Dict[str, Any]:
    """Return one JSON-safe implementation-binding descriptor."""
    _, registry = build_wp3_example_registries()
    contract = registry.binding_contract(binding_id)
    if contract is None:
        raise HTTPException(status_code=404, detail=f"Unknown implementation binding: {binding_id}")
    return contract.to_dict()

@app.get("/catalog/compatibility-rules")
def compatibility_rule_catalog() -> Dict[str, Any]:
    """Publish WP4 versioned pairwise rules and global tuple invariants."""
    return public_compatibility_rule_catalog()


@app.get("/catalog/compatibility-rules/{rule_id:path}")
def compatibility_rule_schema(rule_id: str) -> Dict[str, Any]:
    """Return one exact compatibility-rule declaration."""
    registry = build_wp4_rule_registry()
    rule = registry.rule(rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Unknown compatibility rule: {rule_id}")
    return rule.to_dict()


@app.get("/catalog/realization-resolver")
def realization_resolver_catalog() -> Dict[str, Any]:
    """Publish WP5 named variants, complete reports, and runtime-gate evidence."""
    return public_realization_resolver_catalog()

@app.get("/catalog/acceptance-evidence-fingerprints")
def acceptance_evidence_fingerprint_catalog() -> Dict[str, Any]:
    """Publish WP6 exact composition/scale fingerprints and staleness examples."""
    return public_acceptance_fingerprint_catalog()


@app.get("/catalog/acceptance-evidence-fingerprints/{scenario}")
def acceptance_evidence_fingerprint_scenario(scenario: str) -> Dict[str, Any]:
    catalog = public_acceptance_fingerprint_catalog()
    aliases = {"current": "exact_match_report", "four_to_twenty": "declared_scale_20_modes"}
    scenario = aliases.get(str(scenario), str(scenario))
    if scenario == "exact_match_report":
        return catalog["exact_match_report"]
    report = catalog["staleness_scenarios"].get(scenario)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown WP6 fingerprint scenario: {scenario}")
    return report


@app.get("/catalog/acceptance-harness")
def acceptance_harness_catalog() -> Dict[str, Any]:
    """Publish WP7 gate contracts, tolerance profiles, and baseline classifications."""
    return public_acceptance_harness_catalog()


@app.get("/catalog/acceptance-harness/{variant_id:path}")
def acceptance_harness_variant(variant_id: str) -> Dict[str, Any]:
    catalog = public_acceptance_harness_catalog()
    aliases = {
        "one_pair": "baseline.pair.one_pair.ground_state.v1",
        "multi_pair": "baseline.pair.multi_pair.ground_state.v1",
        "jw_analysis": "baseline.jw.mapping_analysis.v1",
        "bk_analysis": "baseline.bk.mapping_analysis.v1",
        "invalid_jw": "baseline.jw.general_ground_state.current_composition.v1",
        "bk_ground": "baseline.bk.general_ground_state.v1",
    }
    variant_id = aliases.get(str(variant_id), str(variant_id))
    report = catalog["baseline_classifications"].get(variant_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Unknown WP7 baseline variant: {variant_id}")
    return report


def _resolve_wp5_scenario(scenario: str):
    aliases = {
        "invalid_jw": "known_invalid_jw",
        "valid": "valid_execution",
        "analysis": "mapping_analysis",
    }
    scenario = aliases.get(str(scenario), str(scenario))
    candidates = build_wp5_candidates()
    candidate = candidates.get(scenario)
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown WP5 resolver scenario: {scenario}",
        )
    contracts, bindings, rules = build_wp5_fixture_registries()
    resolver = RealizationVariantResolver(
        contract_registry=contracts,
        binding_registry=bindings,
        rule_registry=rules,
    )
    return resolver.resolve(candidate)


@app.post("/catalog/realization-variants/resolve")
def resolve_realization_variant_catalog(
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Resolve one bounded WP5 fixture without entering circuit runtime services."""
    scenario = str((payload or {}).get("scenario", "")).strip()
    if not scenario:
        raise HTTPException(
            status_code=422,
            detail="The WP5 fixture resolver requires a non-empty 'scenario'.",
        )
    return _resolve_wp5_scenario(scenario).to_public_dict()


@app.get("/catalog/realization-variants/{scenario}")
def realization_variant_scenario(scenario: str) -> Dict[str, Any]:
    """Return one exact bounded WP5 resolution example."""
    return _resolve_wp5_scenario(scenario).to_public_dict()


@app.get("/catalog/mapping-policies/pair-mapping")
def pair_mapping_policy_migration_catalog() -> Dict[str, Any]:
    return public_pair_mapping_migration_catalog()


@app.get("/catalog/mapping-policies/pair-mapping/{variant_id}")
def pair_mapping_policy_migration_variant(variant_id: str) -> Dict[str, Any]:
    catalog = public_pair_mapping_migration_catalog()
    key = str(variant_id).strip().lower().replace("-", "_")
    if key not in {"one_pair", "multi_pair"}:
        raise HTTPException(status_code=404, detail=f"Unknown Pair Mapping variant {variant_id!r}.")
    return {
        "schema_version": catalog["schema_version"],
        "profile": catalog["profile"],
        "variant_id": key,
        "resolution": catalog["resolutions"][key],
        "acceptance_harness": catalog["acceptance_harness"][key],
        "status_preservation": catalog["status_preservation"][key],
        "callable_payload_withheld": True,
    }


@app.get("/catalog/mapping-policies/jordan-wigner")
def jordan_wigner_policy_migration_catalog() -> Dict[str, Any]:
    return public_spin_orbital_mapping_migration_catalog()["jw"]


@app.get("/catalog/mapping-policies/jordan-wigner/{variant_id}")
def jordan_wigner_policy_migration_variant(variant_id: str) -> Dict[str, Any]:
    catalog = public_spin_orbital_mapping_migration_catalog()["jw"]
    key = str(variant_id).strip().lower().replace("-", "_")
    aliases = {"analysis": "jw_mapping_analysis", "mapping_analysis": "jw_mapping_analysis", "ground_state": "jw_ground_state_current", "ground_state_current": "jw_ground_state_current", "current": "jw_ground_state_current"}
    target = aliases.get(key)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Unknown Jordan–Wigner migration variant {variant_id!r}.")
    return {"schema_version": catalog["profile"]["schema_version"], "profile": catalog["profile"], "variant_id": target, "resolution": catalog["resolutions"][target], "acceptance_harness": catalog["acceptance_harness"][target], "callable_payload_withheld": True}


@app.get("/catalog/jw-accepted-composition")
def jw_accepted_composition_catalog() -> Dict[str, Any]:
    """Publish the WP11 mapped-fermionic JW composition and promotion identity."""
    return public_wp11_jw_accepted_composition_catalog()


@app.get("/catalog/jw-accepted-composition/promotion")
def jw_accepted_composition_promotion() -> Dict[str, Any]:
    """Return the exact WP11 promotion record; no runtime is executed."""
    return build_wp11_acceptance_record().to_dict()


@app.get("/catalog/mapping-policies/bravyi-kitaev")
def bravyi_kitaev_policy_migration_catalog() -> Dict[str, Any]:
    return public_spin_orbital_mapping_migration_catalog()["bk"]


@app.get("/catalog/mapping-policies/bravyi-kitaev/{variant_id}")
def bravyi_kitaev_policy_migration_variant(variant_id: str) -> Dict[str, Any]:
    catalog = public_spin_orbital_mapping_migration_catalog()["bk"]
    key = str(variant_id).strip().lower().replace("-", "_")
    aliases = {"analysis": "bk_mapping_analysis", "mapping_analysis": "bk_mapping_analysis", "ground_state": "bk_ground_state"}
    target = aliases.get(key)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Unknown Bravyi–Kitaev migration variant {variant_id!r}.")
    return {"schema_version": catalog["profile"]["schema_version"], "profile": catalog["profile"], "variant_id": target, "resolution": catalog["resolutions"][target], "acceptance_harness": catalog["acceptance_harness"][target], "callable_payload_withheld": True}


@app.get("/catalog/mapping-policies/a3-2b-exit")
def a3_2b_policy_migration_exit() -> Dict[str, Any]:
    return public_a3_2b_exit_decision()


@app.get("/catalog/governance")
def governance_catalog() -> Dict[str, Any]:
    """Publish WP13 governed scientific assets and release boundaries."""
    return public_governance_catalog()


@app.get("/catalog/governance/assets")
def governance_assets() -> Dict[str, Any]:
    catalog = public_governance_catalog()
    return {
        "schema_version": "qcol-governed-asset-registry/1.0",
        "count": len(catalog["governed_assets"]),
        "assets": catalog["governed_assets"],
    }


@app.get("/catalog/governance/assets/{asset_id:path}")
def governance_asset(asset_id: str) -> Dict[str, Any]:
    try:
        return get_governed_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/governance/statuses")
def governance_statuses() -> Dict[str, Any]:
    catalog = public_governance_catalog()
    return {
        "schema_version": "qcol-published-status-registry/1.0",
        "unqualified_mapping_verified_badge_allowed": False,
        "count": len(catalog["published_statuses"]),
        "records": catalog["published_statuses"],
    }


@app.get("/catalog/governance/statuses/{variant_id:path}")
def governance_status(variant_id: str) -> Dict[str, Any]:
    try:
        return get_published_status(variant_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/catalog/governance/deprecations")
def governance_deprecations() -> Dict[str, Any]:
    catalog = public_governance_catalog()
    return {"schema_version": "qcol-deprecation-rule-registry/1.0", "rules": catalog["deprecation_rules"]}


@app.get("/catalog/governance/migrations")
def governance_migrations() -> Dict[str, Any]:
    catalog = public_governance_catalog()
    return {"schema_version": "qcol-migration-rule-registry/1.0", "rules": catalog["migration_rules"]}


@app.get("/catalog/advisor-handoff")
def advisor_handoff() -> Dict[str, Any]:
    return build_phase_b_handoff_contract().to_dict()


@app.get("/catalog/advisor-handoff/allowed-patches")
def advisor_allowed_patches() -> Dict[str, Any]:
    return public_allowed_request_patch_registry()


@app.post("/catalog/advisor-handoff/validate-patch")
def advisor_validate_patch(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        return validate_advisor_request_patch(payload).to_dict()
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_request_patch", "message": str(exc)}) from exc


@app.get("/catalog/a3-2c-release")
def a3_2c_release() -> Dict[str, Any]:
    return build_a3_2c_release_decision().to_dict()


@app.get("/catalog/deterministic-advisor")
def deterministic_advisor_catalog() -> Dict[str, Any]:
    """Publish Phase B rule, context, patch, and safety contracts."""
    return public_deterministic_advisor_catalog()


@app.get("/catalog/deterministic-advisor/rules")
def deterministic_advisor_rules() -> Dict[str, Any]:
    catalog = public_deterministic_advisor_catalog()
    return {
        "schema_version": catalog["rule_catalog"]["schema_version"],
        "advisor_version": catalog["rule_catalog"]["advisor_version"],
        "fingerprint": deterministic_advisor_rule_catalog_fingerprint(),
        "rules": catalog["rule_catalog"]["rules"],
        "predicate_bindings": catalog["rule_catalog"]["predicate_bindings"],
        "callable_payload_withheld": True,
    }


@app.get("/catalog/deterministic-advisor/scenarios/{scenario}")
def deterministic_advisor_scenario(scenario: str) -> Dict[str, Any]:
    if scenario not in SCENARIO_IDS:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "unknown_advisor_scenario",
                "message": f"Unknown deterministic Advisor scenario: {scenario}",
                "available": list(SCENARIO_IDS),
            },
        )
    context = build_advisor_context_fixture(scenario)
    report = evaluate_advisor_context(context, enabled=True)
    return {
        "schema_version": "qcol-advisor-scenario-response/1.0",
        "scenario": scenario,
        "context": context.to_dict(),
        "report": report.to_dict(),
        "catalog_fingerprint": deterministic_advisor_catalog_fingerprint(),
    }


def _advisor_payload_response(
    snapshot: Dict[str, Any],
    *,
    previous_snapshot: Optional[Dict[str, Any]] = None,
    enabled: bool = True,
) -> Dict[str, Any]:
    try:
        context, report = advise_run_payload(
            snapshot,
            previous_snapshot=previous_snapshot,
            enabled=enabled,
        )
    except (AdvisorContextError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "advisor_context_invalid",
                "message": str(exc),
            },
        ) from exc
    return {
        "schema_version": "qcol-deterministic-advisor-response/1.0",
        "context": context.to_dict(),
        "report": report.to_dict(),
        "catalog_fingerprint": deterministic_advisor_catalog_fingerprint(),
        "execution_performed_by_advisor": False,
        "verification_retains_final_authority": True,
    }


@app.post("/advisor/evaluate")
def evaluate_advisor_payload(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Evaluate one caller-supplied public run snapshot without mutating it."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Advisor payload must be a JSON object.")
    snapshot = payload.get("snapshot", payload)
    previous = payload.get("previous_snapshot")
    enabled = bool(payload.get("enabled", True))
    if not isinstance(snapshot, dict):
        raise HTTPException(status_code=422, detail="snapshot must be a JSON object.")
    if previous is not None and not isinstance(previous, dict):
        raise HTTPException(status_code=422, detail="previous_snapshot must be a JSON object when supplied.")
    return _advisor_payload_response(snapshot, previous_snapshot=previous, enabled=enabled)


@app.get("/catalog/phase-c-try-compare")
def phase_c_try_compare_catalog() -> Dict[str, Any]:
    return public_phase_c_catalog()


@app.get("/catalog/phase-c-try-compare/policies")
def phase_c_comparison_policies() -> Dict[str, Any]:
    return public_comparison_policy_catalog()


@app.get("/catalog/phase-c-try-compare/fingerprint")
def phase_c_fingerprint() -> Dict[str, Any]:
    return {
        "schema_version": "qcol-phase-c-catalog-fingerprint/1.0",
        "fingerprint": phase_c_catalog_fingerprint(),
    }


@app.get("/catalog/phase-c-try-compare/scenarios/{scenario}")
def phase_c_scenario(scenario: str) -> Dict[str, Any]:
    if scenario not in PHASE_C_SCENARIO_IDS:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_phase_c_scenario", "scenario": scenario},
        )
    return build_phase_c_scenario(scenario)


@app.get("/catalog/policy-registries")
def policy_registry_catalog() -> Dict[str, Any]:
    """Publish stable policy IDs and import bindings without executing a model."""
    return public_policy_catalog()


@app.post("/catalog/model-contracts/{model_id:path}/resolve")
def resolve_model_capability(model_id: str, payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Resolve one candidate request to an honest callable CapabilityReport."""
    from .model_instance_adapters import instance_from_request
    from .resolver import resolve_model

    candidate = dict(payload or {})
    candidate["model_id"] = model_id
    try:
        instance = instance_from_request(candidate)
        plan = resolve_model(instance, request_metadata=candidate)
        return plan.to_dict()
    except ModelContractError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "capability_resolution_error", "message": str(exc)},
        ) from exc


@app.get("/catalog/fermion-problems")
def fermion_problem_catalog(include_unavailable: bool = True) -> Dict[str, Any]:
    problems = public_fermion_problem_catalog(include_unavailable=include_unavailable)
    return {"count": len(problems), "problems": problems}


@app.get("/catalog/fermion-problems/{problem_id}")
def fermion_problem_schema(problem_id: str) -> Dict[str, Any]:
    try:
        return get_fermion_problem_spec(problem_id).to_public_dict()
    except FermionProblemContractError as exc:
        raise HTTPException(status_code=404, detail=exc.to_dict()) from exc

def _not_found(run_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Unknown run_id: {run_id}")


def _record(run_id: str):
    try:
        return get_run_manager().get(run_id)
    except KeyError as exc:
        raise _not_found(run_id) from exc


@app.get("/health")
def health() -> Dict[str, Any]:
    manager = get_run_manager()
    return {
        "status": "ok",
        "service": "qcol-model-task-registry",
        "version": __version__,
        "registry": "in_memory_single_process",
        "active_run_count": sum(
            item["status"] not in {"completed", "cancelled", "failed"}
            for item in manager.list_runs()
        ),
        "dashboard_url": "/dashboard",
        "client_url": "/client",
        "catalog_url": "/catalog",
        "docs_url": "/docs",
    }


@app.get("/client", include_in_schema=False)
def portable_client() -> FileResponse:
    if not CLIENT_FILE.exists():
        raise HTTPException(status_code=404, detail="Portable client file is missing.")
    return FileResponse(CLIENT_FILE, media_type="text/html")


@app.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def create_run(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        raise HTTPException(status_code=422, detail="Request body must be a non-empty JSON object.")
    try:
        record = get_run_manager().create_run(payload)
    except FermionProblemContractError as exc:
        raise HTTPException(status_code=422, detail=exc.to_dict()) from exc
    except ModelContractError as exc:
        raise HTTPException(status_code=422, detail={"code": "model_contract_error", "message": str(exc)}) from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_request", "message": str(exc)}) from exc
    snapshot = record.snapshot()
    return {
        "run_id": record.run_id,
        "status": snapshot["status"],
        "status_url": f"/runs/{record.run_id}",
        "stream_url": f"/runs/{record.run_id}/stream",
        "cancel_url": f"/runs/{record.run_id}/cancel",
    }


@app.get("/runs")
def list_runs() -> Dict[str, Any]:
    runs = get_run_manager().list_runs()
    return {"count": len(runs), "runs": runs}


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    return _record(run_id).snapshot()


def _terminal_snapshot_for_advisor(run_id: str) -> Dict[str, Any]:
    snapshot = _record(run_id).snapshot()
    if snapshot.get("status") not in {"completed", "cancelled", "failed"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "advisor_requires_terminal_run",
                "message": "Deterministic feedback is generated from a terminal public run snapshot.",
                "status": snapshot.get("status"),
            },
        )
    return snapshot


@app.get("/runs/{run_id}/advisor")
def advise_run(
    run_id: str,
    previous_run_id: Optional[str] = Query(default=None),
    enabled: bool = Query(default=True),
) -> Dict[str, Any]:
    """Generate on-demand deterministic feedback for one terminal run."""
    snapshot = _terminal_snapshot_for_advisor(run_id)
    previous = None
    if previous_run_id:
        previous = _terminal_snapshot_for_advisor(previous_run_id)
    payload = _advisor_payload_response(snapshot, previous_snapshot=previous, enabled=enabled)
    payload["run_id"] = run_id
    payload["previous_run_id"] = previous_run_id
    return payload


@app.post("/runs/{run_id}/advisor/prepare-candidate")
def prepare_advisor_candidate(
    run_id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Prepare an approved candidate request; never execute it in Phase B."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Candidate-plan payload must be a JSON object.")
    card_id = str(payload.get("card_id", "")).strip()
    if not card_id:
        raise HTTPException(status_code=422, detail="card_id is required.")
    approved = payload.get("approved") is True
    previous_run_id = payload.get("previous_run_id")
    snapshot = _terminal_snapshot_for_advisor(run_id)
    previous = None
    if previous_run_id:
        previous = _terminal_snapshot_for_advisor(str(previous_run_id))
    try:
        context, report = advise_run_payload(
            snapshot,
            previous_snapshot=previous,
            enabled=True,
        )
        card = next(item for item in report.cards if item.card_id == card_id)
        plan = prepare_candidate_request_plan(
            snapshot["request"],
            card,
            approved=approved,
        )
    except StopIteration as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "advisor_card_not_found",
                "message": "The card ID does not belong to the current deterministic Advisor report.",
            },
        ) from exc
    except (AdvisorContextError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "candidate_request_not_preparable",
                "message": str(exc),
            },
        ) from exc
    return {
        "schema_version": "qcol-advisor-candidate-response/1.0",
        "run_id": run_id,
        "context_id": context.context_id,
        "report_id": report.report_id,
        "card": card.to_dict(),
        "candidate_plan": plan.to_dict(),
        "execution_performed_by_advisor": False,
        "next_entrypoint": "POST /runs",
        "canonical_pipeline_entrypoint": "qcol.orchestrator.run_pipeline",
        "phase_c_comparison_performed": False,
    }


@app.post("/runs/{baseline_run_id}/try-compare", status_code=status.HTTP_202_ACCEPTED)
def start_try_compare(
    baseline_run_id: str,
    payload: Dict[str, Any] = Body(...),
) -> Dict[str, Any]:
    """Approve one Phase B hypothesis, run it through the same pipeline, then compare."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Try/Compare payload must be a JSON object.")
    card_id = str(payload.get("card_id", "")).strip()
    if not card_id:
        raise HTTPException(status_code=422, detail="card_id is required.")
    if payload.get("approved") is not True:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "explicit_user_approval_required",
                "message": "Phase C will not execute a candidate until approved=true is supplied.",
            },
        )
    try:
        session = get_run_manager().start_try_compare(
            baseline_run_id,
            card_id=card_id,
            approved=True,
            previous_run_id=payload.get("previous_run_id"),
            policy_id=payload.get("policy_id"),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (AdvisorContextError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail={"code": "try_compare_not_startable", "message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail={"code": "try_compare_conflict", "message": str(exc)}) from exc
    snapshot = session.snapshot()
    return {
        **snapshot,
        "candidate_status_url": f"/runs/{session.candidate_run_id}",
        "candidate_stream_url": f"/runs/{session.candidate_run_id}/stream",
        "comparison_url": f"/comparisons/{session.session_id}",
    }


@app.get("/comparisons")
def list_comparisons() -> Dict[str, Any]:
    items = get_run_manager().list_comparisons()
    return {"count": len(items), "comparisons": items}


@app.get("/runs/{run_id}/comparisons")
def list_run_comparisons(run_id: str) -> Dict[str, Any]:
    try:
        _record(run_id)
    except HTTPException:
        raise
    items = get_run_manager().list_comparisons(run_id=run_id)
    return {"run_id": run_id, "count": len(items), "comparisons": items}


@app.get("/comparisons/{session_id}")
def get_comparison(session_id: str) -> Dict[str, Any]:
    try:
        return get_run_manager().get_comparison(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "comparison_not_found", "session_id": session_id}) from exc


@app.get("/comparisons/{session_id}/evidence")
def download_comparison_evidence(session_id: str) -> FileResponse:
    try:
        archive = get_run_manager().comparison_evidence_file(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "comparison_not_found", "session_id": session_id}) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Comparison Evidence is not available until the candidate is terminal and the decision record is complete.") from exc
    return FileResponse(archive, media_type="application/zip", filename=archive.name)


@app.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_run(
    run_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
) -> Dict[str, Any]:
    reason = str((payload or {}).get("reason", "user_requested"))
    try:
        record = get_run_manager().cancel(run_id, reason=reason)
    except KeyError as exc:
        raise _not_found(run_id) from exc
    return record.snapshot()


@app.get("/runs/{run_id}/technical-error")
def technical_error_log(run_id: str) -> Dict[str, Any]:
    """Return the local developer log separately from the user-facing station."""
    try:
        return get_run_manager().technical_error_info(run_id)
    except KeyError as exc:
        raise _not_found(run_id) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail="No technical error log is available for this run.",
        ) from exc


@app.get("/runs/{run_id}/evidence")
def download_evidence(run_id: str) -> FileResponse:
    try:
        archive = get_run_manager().evidence_file(run_id)
    except KeyError as exc:
        raise _not_found(run_id) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=409,
            detail="Evidence is not available until the run reaches a terminal state.",
        ) from exc
    return FileResponse(
        archive,
        media_type="application/zip",
        filename=archive.name,
    )


def _parse_last_event_id(request: Request, after: int) -> int:
    header = request.headers.get("last-event-id")
    if header is None:
        return max(0, after)
    try:
        return max(0, int(header), after)
    except ValueError:
        return max(0, after)


def _format_sse(item: StoredEvent) -> str:
    payload = json.dumps(
        service_json_safe(item.data),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return f"id: {item.id}\nevent: {item.event}\ndata: {payload}\n\n"


@app.get("/runs/{run_id}/stream")
def stream_run(
    run_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
) -> StreamingResponse:
    record = _record(run_id)
    cursor = _parse_last_event_id(request, after)

    def stream():
        yield "retry: 1500\n\n"
        for item in get_run_manager().iter_events(run_id, after=cursor):
            if item is None:
                yield ": heartbeat\n\n"
            else:
                yield _format_sse(item)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-QCOL-Run-ID": record.run_id,
        },
    )


@app.exception_handler(FermionProblemContractError)
def fermion_contract_error_handler(_: Request, exc: FermionProblemContractError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.to_dict()})


@app.exception_handler(ValueError)
def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "qcol.api:app",
        host="127.0.0.1",
        port=int(os.getenv("QCOL_API_PORT", "8000")),
        reload=False,
    )
