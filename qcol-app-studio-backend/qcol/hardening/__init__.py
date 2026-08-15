"""Post-Phase-C architectural-hardening utilities.

Step 1 freezes the accepted QCOL Phase C 1.23.0 baseline.  The package is
intentionally outside the scientific runtime: it inventories and verifies the
existing contracts, catalogs, public API, evidence, references, and status
claims without changing ``run_pipeline`` or any accepted realization.
"""
from .baseline_freeze import (
    BASELINE_BRANCH,
    BASELINE_PROJECT_VERSION,
    BASELINE_SOURCE_ARCHIVE_SHA256,
    BASELINE_SOURCE_PACKAGE,
    HARDENING_BRANCH,
    BaselineFreezeExport,
    baseline_commit_file_bytes,
    baseline_to_head_diff,
    build_dependency_lock,
    build_public_api_surface,
    build_scientific_status_snapshot,
    build_unified_baseline_manifest,
    catalog_fingerprints,
    export_frozen_baseline,
    verify_frozen_baseline,
)

__all__ = [
    "BASELINE_BRANCH",
    "BASELINE_PROJECT_VERSION",
    "BASELINE_SOURCE_ARCHIVE_SHA256",
    "BASELINE_SOURCE_PACKAGE",
    "HARDENING_BRANCH",
    "BaselineFreezeExport",
    "baseline_commit_file_bytes",
    "baseline_to_head_diff",
    "build_dependency_lock",
    "build_public_api_surface",
    "build_scientific_status_snapshot",
    "build_unified_baseline_manifest",
    "catalog_fingerprints",
    "export_frozen_baseline",
    "verify_frozen_baseline",
]


from .qho_extension import (
    QHO_EXTENSION_VERSION,
    QHOExtensionEvidenceExport,
    build_qho_extension_manifest,
    export_qho_extension_evidence,
    validate_qho_extension,
    verify_qho_extension_evidence,
)

__all__ += [
    "QHO_EXTENSION_VERSION",
    "QHOExtensionEvidenceExport",
    "build_qho_extension_manifest",
    "export_qho_extension_evidence",
    "validate_qho_extension",
    "verify_qho_extension_evidence",
]


from .semantic_authority import (
    PRE_FREEZE_PROJECT_VERSION,
    SemanticAuthorityEvidenceExport,
    build_architecture_decision_record_catalog,
    build_core_regression_attestation,
    build_identity_mutation_matrix,
    build_model_classification_catalog,
    build_resource_authority_scenarios,
    build_semantic_authority_hardening_manifest,
    export_semantic_authority_evidence,
    validate_semantic_authority_hardening,
    verify_semantic_authority_evidence,
)

__all__ += [
    "PRE_FREEZE_PROJECT_VERSION",
    "SemanticAuthorityEvidenceExport",
    "build_architecture_decision_record_catalog",
    "build_core_regression_attestation",
    "build_identity_mutation_matrix",
    "build_model_classification_catalog",
    "build_resource_authority_scenarios",
    "build_semantic_authority_hardening_manifest",
    "export_semantic_authority_evidence",
    "validate_semantic_authority_hardening",
    "verify_semantic_authority_evidence",
]
