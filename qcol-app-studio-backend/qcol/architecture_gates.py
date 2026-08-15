"""Pre-freeze static architecture gates."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

CORE_PREFIXES = (
    "qcol/model_contracts",
    "qcol/task_contracts",
    "qcol/semantic_authority",
    "qcol/compatibility",
    "qcol/resource_rules",
    "qcol/semantic_identity.py",
    "qcol/composition_root.py",
    "qcol/failure_model.py",
)
FORBIDDEN_CORE_IMPORT_PREFIXES = (
    "gradio",
    "fastapi",
    "uvicorn",
    "qiskit",
    "qiskit_aer",
    "amazon_braket",
    "braket",
    "cirq_google",
    "cirq_ionq",
    "cirq_pasqal",
    "cirq_rigetti",
)


def _files(root: Path, entries: tuple[str, ...]) -> list[Path]:
    rows: list[Path] = []
    for entry in entries:
        path = root / entry
        if path.is_dir():
            rows.extend(path.rglob("*.py"))
        elif path.is_file():
            rows.append(path)
    return sorted(set(rows))


def _imports(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            rows.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            rows.append((node.lineno, node.module or ""))
    return rows


def dependency_direction_audit(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    violations: list[dict[str, Any]] = []
    for path in _files(root, CORE_PREFIXES):
        for line, module in _imports(path):
            if module.startswith(FORBIDDEN_CORE_IMPORT_PREFIXES):
                violations.append(
                    {
                        "path": str(path.relative_to(root)),
                        "line": line,
                        "module": module,
                    }
                )
    return {
        "gate_id": "ARCH-DEP-001",
        "violations": violations,
        "pass": not violations,
    }


def composition_root_audit(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    entries = (
        "qcol/runtime.py",
        "qcol/observable_runtime.py",
        "qcol/controllers",
        "qcol/execution",
        "qcol/evidence.py",
    )
    forbidden_calls = (
        "resolve_model_task_request(",
        "resolve_request_to_quantum_realization(",
        "get_model_contract(",
        "get_task_contract(",
    )
    violations: list[dict[str, Any]] = []
    for path in _files(root, entries):
        text = path.read_text(encoding="utf-8")
        for term in forbidden_calls:
            for line_no, line in enumerate(text.splitlines(), 1):
                stripped = line.lstrip()
                if term in line and not stripped.startswith(("#", '"', "'")):
                    violations.append(
                        {
                            "path": str(path.relative_to(root)),
                            "line": line_no,
                            "term": term,
                        }
                    )
    return {
        "gate_id": "ARCH-COMP-001",
        "composition_root": "QuantumRealizationArtifact",
        "violations": violations,
        "pass": not violations,
    }


def semantic_authority_dispatch_audit(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    violations: list[dict[str, Any]] = []
    allowed = (
        "qcol/semantic_authority/",
        "qcol/hardening/",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/architecture_gates.py",
        "tests/",
    )
    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(allowed) or "__pycache__" in rel:
            continue
        text = path.read_text(encoding="utf-8")
        if "SEMANTIC_AUTHORITY_REGISTRY" in text:
            violations.append(
                {
                    "path": rel,
                    "reason": "semantic authority catalog used outside governance/audit surface",
                }
            )
    return {
        "gate_id": "ARCH-AUTH-001",
        "catalog_role": "governance_audit_only",
        "violations": violations,
        "pass": not violations,
    }


def public_architecture_gate_report(project_root: Path | str) -> dict[str, Any]:
    from .semantic_authority import semantic_leakage_audit

    reports = {
        "semantic_leakage": semantic_leakage_audit(project_root),
        "dependency_direction": dependency_direction_audit(project_root),
        "composition_root": composition_root_audit(project_root),
        "semantic_authority_governance_only": semantic_authority_dispatch_audit(
            project_root
        ),
    }
    return {
        "schema_version": "qcol-architecture-gate-report/1.0",
        "reports": reports,
        "pass": all(row["pass"] for row in reports.values()),
    }


__all__ = [
    "dependency_direction_audit",
    "composition_root_audit",
    "semantic_authority_dispatch_audit",
    "public_architecture_gate_report",
]
