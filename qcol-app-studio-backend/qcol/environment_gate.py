"""Scoped environment reproducibility contracts for QCOL.

A shared Colab runtime is not an isolated QCOL installation.  Consequently,
``pip check`` over the whole Colab host is retained as a diagnostic, while the
blocking gate is scoped to QCOL's exact lock, dependency closure, imports, and
secret hygiene.  A clean isolated virtual environment remains mandatory before
an actual Unified Baseline Freeze can be issued.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import importlib.metadata as metadata
import os
import platform
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ENVIRONMENT_POLICY_SCHEMA = "qcol-environment-scope-policy/1.0"
ENVIRONMENT_MANIFEST_SCHEMA = "qcol-environment-manifest/2.0"
DEPENDENCY_CONFLICT_SCHEMA = "qcol-dependency-conflict/1.0"

IMPORTANT_PACKAGES = (
    "numpy",
    "scipy",
    "cirq-core",
    "openfermion",
    "pyqasm",
    "ply",
    "gradio",
    "fastapi",
    "uvicorn",
)

_PIP_CONFLICT_RE = re.compile(
    r"^(?P<owner>[^\s]+)(?:\s+[^\s]+)?\s+has requirement\s+"
    r"(?P<requirement>.+?),\s+but you have\s+(?P<actual>.+?)\.?$",
    re.IGNORECASE,
)
_PIP_MISSING_RE = re.compile(
    r"^(?P<owner>[^\s]+)(?:\s+[^\s]+)?\s+requires\s+"
    r"(?P<requirement>.+?),\s+which is not installed\.?$",
    re.IGNORECASE,
)


def _hash(path: Path) -> str | None:
    return sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def parse_locked_requirements(path: Path | str) -> dict[str, str]:
    """Return exact ``name -> version`` pins from a QCOL lock file."""

    source = Path(path)
    rows: dict[str, str] = {}
    for raw in source.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        name, version = line.split("==", 1)
        rows[canonicalize_name(name.strip())] = version.strip()
    return dict(sorted(rows.items()))


def detect_environment_scope() -> str:
    """Classify the active Python host without treating that label as science."""

    if (
        os.environ.get("COLAB_RELEASE_TAG")
        or os.environ.get("COLAB_BACKEND_VERSION")
        or "google.colab" in sys.modules
    ):
        return "colab_host"
    if os.environ.get("VIRTUAL_ENV") or sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return "isolated_venv"
    return "shared_host"


def select_dependency_lock(
    project_root: Path | str,
    *,
    environment_scope: str,
    requested: str | None = None,
) -> Path:
    """Select the lock that actually defines the evaluated QCOL environment.

    Colab/shared-host portability is evaluated against the accepted Colab lock;
    an isolated virtual environment is evaluated against the clean local lock.
    An explicit path remains available for audit/reproduction.
    """

    root = Path(project_root).resolve()
    if requested and requested != "auto":
        candidate = Path(requested)
        if not candidate.is_absolute():
            candidate = root / candidate
        return candidate.resolve()
    filename = (
        "requirements.txt"
        if environment_scope == "isolated_venv"
        else "requirements-colab-scientific.txt"
    )
    return (root / filename).resolve()


def installed_versions(names: Iterable[str]) -> dict[str, str | None]:
    rows: dict[str, str | None] = {}
    for raw_name in names:
        name = canonicalize_name(raw_name)
        try:
            rows[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            rows[name] = None
    return dict(sorted(rows.items()))


def build_qcol_dependency_closure(root_packages: Iterable[str]) -> tuple[str, ...]:
    """Resolve the installed dependency closure rooted at QCOL's locked stack.

    This is deliberately an installed-environment closure.  Missing packages are
    still retained in the set so that exact-version checks can report them.
    Optional dependencies whose markers do not apply to the active interpreter
    are ignored.
    """

    pending = [canonicalize_name(name) for name in root_packages]
    seen: set[str] = set()
    marker_environment = default_environment()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            distribution = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        for raw_requirement in distribution.requires or ():
            try:
                requirement = Requirement(raw_requirement)
            except Exception:
                continue
            if requirement.marker is not None:
                try:
                    if not requirement.marker.evaluate(marker_environment):
                        continue
                except Exception:
                    continue
            dependency = canonicalize_name(requirement.name)
            if dependency not in seen:
                pending.append(dependency)
    return tuple(sorted(seen))


@dataclass(frozen=True)
class DependencyConflictRecord:
    owner_distribution: str
    requirement: str
    actual: str | None
    raw_line: str
    scope: str
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DEPENDENCY_CONFLICT_SCHEMA,
            "owner_distribution": self.owner_distribution,
            "requirement": self.requirement,
            "actual": self.actual,
            "raw_line": self.raw_line,
            "scope": self.scope,
            "blocking": self.blocking,
        }


def parse_pip_check_output(text: str) -> tuple[dict[str, str | None], ...]:
    """Parse the stable human-readable forms currently emitted by pip check."""

    rows: list[dict[str, str | None]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "No broken requirements found.":
            continue
        match = _PIP_CONFLICT_RE.match(line)
        if match:
            rows.append(
                {
                    "owner_distribution": canonicalize_name(match.group("owner")),
                    "requirement": match.group("requirement").strip(),
                    "actual": match.group("actual").strip().rstrip("."),
                    "raw_line": line,
                }
            )
            continue
        missing = _PIP_MISSING_RE.match(line)
        if missing:
            rows.append(
                {
                    "owner_distribution": canonicalize_name(missing.group("owner")),
                    "requirement": missing.group("requirement").strip(),
                    "actual": None,
                    "raw_line": line,
                }
            )
            continue
        # Preserve unparsed diagnostics rather than dropping them silently.
        rows.append(
            {
                "owner_distribution": "unparsed-host-diagnostic",
                "requirement": "unparsed",
                "actual": None,
                "raw_line": line,
            }
        )
    return tuple(rows)


def classify_dependency_conflicts(
    parsed_conflicts: Sequence[Mapping[str, str | None]],
    *,
    qcol_dependency_closure: Iterable[str],
    environment_scope: str,
) -> tuple[DependencyConflictRecord, ...]:
    closure = {canonicalize_name(name) for name in qcol_dependency_closure}
    isolated = environment_scope == "isolated_venv"
    records: list[DependencyConflictRecord] = []
    for row in parsed_conflicts:
        owner = canonicalize_name(str(row.get("owner_distribution") or "unknown"))
        in_qcol_closure = owner in closure
        # In an isolated QCOL environment every pip-check conflict is blocking.
        # In Colab/shared hosts only conflicts owned by QCOL's dependency closure
        # block the QCOL gate; all other host conflicts remain recorded.
        blocking = isolated or in_qcol_closure
        scope = "qcol_dependency_closure" if in_qcol_closure else "unrelated_host_package"
        records.append(
            DependencyConflictRecord(
                owner_distribution=owner,
                requirement=str(row.get("requirement") or "unknown"),
                actual=None if row.get("actual") is None else str(row.get("actual")),
                raw_line=str(row.get("raw_line") or ""),
                scope=scope,
                blocking=blocking,
            )
        )
    return tuple(records)


def evaluate_environment_policy(
    *,
    environment_scope: str,
    python_version_allowed: bool,
    version_mismatches: Sequence[Mapping[str, Any]],
    import_smoke_passed: bool,
    secret_scan_passed: bool,
    pip_check_returncode: int,
    conflicts: Sequence[DependencyConflictRecord],
    scope_attestation_valid: bool = True,
    detected_environment_scope: str | None = None,
) -> dict[str, Any]:
    blocking_conflicts = [row.to_dict() for row in conflicts if row.blocking]
    host_conflicts = [row.to_dict() for row in conflicts if not row.blocking]
    qcol_consistency_pass = (
        scope_attestation_valid
        and python_version_allowed
        and not version_mismatches
        and import_smoke_passed
        and secret_scan_passed
        and not blocking_conflicts
    )
    isolated = environment_scope == "isolated_venv"
    clean_install_proof = isolated and pip_check_returncode == 0 and qcol_consistency_pass
    return {
        "schema_version": "qcol-environment-policy-evaluation/1.0",
        "environment_scope": environment_scope,
        "detected_environment_scope": detected_environment_scope or environment_scope,
        "scope_attestation": {
            "valid": bool(scope_attestation_valid),
            "failure_code": None if scope_attestation_valid else "ENVIRONMENT_SCOPE_ATTESTATION_MISMATCH",
        },
        "qcol_environment_consistency": {
            "blocking": True,
            "scope_attestation_valid": bool(scope_attestation_valid),
            "python_version_allowed": bool(python_version_allowed),
            "exact_locked_versions_match": not version_mismatches,
            "qcol_import_and_scientific_smoke_passed": bool(import_smoke_passed),
            "secret_scan_passed": bool(secret_scan_passed),
            "qcol_scoped_dependency_conflicts": blocking_conflicts,
            "pass": qcol_consistency_pass,
        },
        "host_environment_diagnostics": {
            "global_pip_check_returncode": int(pip_check_returncode),
            "global_pip_check_clean": pip_check_returncode == 0,
            "unrelated_host_conflicts": host_conflicts,
            "blocking_in_this_scope": isolated,
            "status": (
                "clean"
                if pip_check_returncode == 0
                else "blocking_conflicts"
                if isolated
                else "diagnostic_conflicts_present"
            ),
        },
        "clean_isolated_environment_proof": {
            "required_for_final_unified_baseline_freeze": True,
            "this_run_is_isolated": isolated,
            "satisfied": clean_install_proof,
            "evidence_rule": (
                "An isolated QCOL installation must pass global pip check and the full regression pack."
            ),
        },
        "pass": qcol_consistency_pass and (not isolated or pip_check_returncode == 0),
    }


POLICY_REGISTRY_REQUIRED_TRUE_FIELDS: tuple[str, ...] = (
    "registry_kinds_complete",
    "all_registries_nonempty",
    "policy_ids_unique_across_kinds",
    "callable_imports_pass",
)
POLICY_REGISTRY_REQUIRED_EMPTY_FIELDS: tuple[str, ...] = (
    "duplicates",
    "load_errors",
)


def evaluate_policy_registry_smoke(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Evaluate the policy-registry smoke report by field semantics.

    Healthy diagnostic mappings such as ``duplicates == {}`` and
    ``load_errors == {}`` are success states.  They must never be aggregated
    with ``all(report.values())`` because an empty mapping is falsey in Python.
    """

    missing_fields = [
        name
        for name in (
            *POLICY_REGISTRY_REQUIRED_TRUE_FIELDS,
            *POLICY_REGISTRY_REQUIRED_EMPTY_FIELDS,
        )
        if name not in report
    ]
    true_checks = {
        name: report.get(name) is True
        for name in POLICY_REGISTRY_REQUIRED_TRUE_FIELDS
    }
    empty_diagnostics = {
        name: isinstance(report.get(name), Mapping) and not report.get(name)
        for name in POLICY_REGISTRY_REQUIRED_EMPTY_FIELDS
    }
    passed = (
        not missing_fields
        and all(true_checks.values())
        and all(empty_diagnostics.values())
    )
    return {
        "schema_version": "qcol-policy-registry-smoke-evaluation/1.0",
        "required_true_checks": true_checks,
        "required_empty_diagnostics": empty_diagnostics,
        "missing_fields": missing_fields,
        "pass": passed,
    }


def public_environment_scope_policy() -> dict[str, Any]:
    return {
        "schema_version": ENVIRONMENT_POLICY_SCHEMA,
        "adr_id": "ADR-QCOL-ENVIRONMENT-SCOPE-001",
        "smoke_aggregation_adr_id": "ADR-QCOL-ENVIRONMENT-SMOKE-AGGREGATION-001",
        "invariants": {
            "global_host_consistency_is_not_qcol_dependency_consistency": True,
            "qcol_scoped_conflicts_are_blocking": True,
            "unrelated_colab_host_conflicts_are_diagnostic": True,
            "clean_isolated_environment_required_for_final_freeze": True,
            "environment_gate_may_not_be_bypassed": True,
            "claimed_scope_must_match_detected_scope": True,
            "isolated_clean_proof_cannot_be_claimed_from_a_shared_host": True,
            "empty_registry_diagnostics_are_semantic_success": True,
        },
        "blocking_qcol_checks": [
            "accepted_python_version",
            "exact_qcol_lock_versions",
            "qcol_dependency_closure_consistency",
            "qcol_import_and_scientific_smoke",
            "semantic_policy_registry_smoke_aggregation",
            "secret_scan",
        ],
        "dependency_lock_selection": {
            "colab_host": "requirements-colab-scientific.txt",
            "shared_host": "requirements-colab-scientific.txt",
            "isolated_venv": "requirements.txt",
        },
        "colab_host_diagnostics": ["global_pip_check", "unrelated_host_conflicts"],
        "clean_environment_proof": {
            "recommended_surface": "fresh Windows/Linux virtual environment",
            "global_pip_check_must_pass": True,
            "full_regression_pack_must_pass": True,
        },
    }


def public_environment_manifest(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    versions = installed_versions(IMPORTANT_PACKAGES)
    reqs = {
        name: _hash(root / name)
        for name in (
            "requirements.txt",
            "requirements-colab-scientific.txt",
            "pyproject.toml",
        )
    }
    return {
        "schema_version": ENVIRONMENT_MANIFEST_SCHEMA,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "detected_environment_scope": detect_environment_scope(),
        "important_package_versions": versions,
        "dependency_file_hashes": reqs,
        "scope_policy": public_environment_scope_policy(),
        "clean_install_test_required_for_final_freeze": True,
        "pip_check_policy": {
            "colab_host": "diagnostic_except_qcol_dependency_closure",
            "shared_host": "diagnostic_except_qcol_dependency_closure",
            "isolated_venv": "globally_blocking",
        },
        "provider_credentials_recorded": False,
    }


__all__ = [
    "IMPORTANT_PACKAGES",
    "DependencyConflictRecord",
    "parse_locked_requirements",
    "detect_environment_scope",
    "installed_versions",
    "select_dependency_lock",
    "build_qcol_dependency_closure",
    "parse_pip_check_output",
    "classify_dependency_conflicts",
    "evaluate_environment_policy",
    "evaluate_policy_registry_smoke",
    "public_environment_scope_policy",
    "public_environment_manifest",
]
