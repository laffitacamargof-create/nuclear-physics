"""Static architecture tripwires for semantic leakage and duplicate derivation."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, Iterable

AUTHORITATIVE_RESOURCE_PATHS = (
    "qcol/resolver.py",
    "qcol/model_task_resolver.py",
    "qcol/realization.py",
    "qcol/models/direct_qubit_resources.py",
    "qcol/models/resource_estimators.py",
    "qcol/resource_rules",
)
UI_PATHS = (
    "qcol/app.py",
    "qcol/model_ui_schema.py",
    "qcol/ui_service.py",
    "qcol/web/app.js",
)
BACKEND_DECISION_PATHS = (
    "qcol/runtime.py",
    "qcol/observable_runtime.py",
    "qcol/orchestrator.py",
    "qcol/models",
    "qcol/app.py",
    "qcol/ui_service.py",
)
TRANSPORT_ALLOWED_PATHS = (
    "qcol/translation.py",
    "qcol/execution",
)


def _py_files(root: Path, entries: Iterable[str]) -> list[Path]:
    result: list[Path] = []
    for entry in entries:
        path = root / entry
        if path.is_dir():
            result.extend(path.rglob("*.py"))
        elif path.suffix == ".py" and path.is_file():
            result.append(path)
    return sorted(set(result))


def _family_in_authoritative_condition(path: Path) -> list[dict[str, Any]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.IfExp, ast.Match, ast.comprehension)):
            continue
        segment = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
        if "model_family" in segment or ".family" in segment:
            violations.append({"path": str(path), "line": getattr(node, "lineno", 0), "source": segment[:240]})
    return violations


def _ui_resource_formula_violations(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    # UI may *display* names such as maximum_parameter_count from a contract.
    # Only actual derivation/formula signatures are forbidden here.
    terms = (
        "estimated_parameter_count =",
        "parameter_count =",
        "parameter_count=",
        "2 * n_qubits",
        "2*n_qubits",
        "n_qubits - 1",
        "n_qubits-1",
        "len(parameter_symbols)",
    )
    violations = []
    for term in terms:
        if term in text:
            violations.append({"path": str(path), "term": term})
    return violations



def _text_term_violations(path: Path, terms: tuple[str, ...]) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    return [
        {"path": str(path), "term": term}
        for term in terms
        if term in text
    ]


def _backend_bypass_violations(root: Path) -> list[dict[str, Any]]:
    terms = (
        "cirq.Simulator(",
        "AerSimulator(",
        "qiskit_aer",
        "AwsDevice(",
        "AwsQuantumTask(",
        "SamplerV2(",
        "QiskitRuntimeService(",
    )
    rows: list[dict[str, Any]] = []
    for path in _py_files(root, BACKEND_DECISION_PATHS):
        if "qcol/execution" in path.as_posix():
            continue
        rows.extend(_text_term_violations(path, terms))
    return rows


def _transport_bypass_violations(root: Path) -> list[dict[str, Any]]:
    allowed = {
        path.resolve()
        for path in _py_files(root, TRANSPORT_ALLOWED_PATHS)
    }
    rows: list[dict[str, Any]] = []
    for path in (root / "qcol").rglob("*.py"):
        if "__pycache__" in path.parts or path.resolve() in allowed:
            continue
        text = path.read_text(encoding="utf-8")
        # Mentions in metadata, messages, or dependency inventories are not imports.
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith(("import pyqasm", "from pyqasm")):
                rows.append({"path": str(path), "line": line_no, "source": stripped})
    return rows

def semantic_leakage_audit(project_root: Path | str) -> Dict[str, Any]:
    root = Path(project_root).resolve()
    family_violations: list[dict[str, Any]] = []
    for path in _py_files(root, AUTHORITATIVE_RESOURCE_PATHS):
        family_violations.extend(_family_in_authoritative_condition(path))
    ui_formula_violations: list[dict[str, Any]] = []
    for entry in UI_PATHS:
        path = root / entry
        if path.is_file():
            ui_formula_violations.extend(_ui_resource_formula_violations(path))
    backend_bypass = _backend_bypass_violations(root)
    transport_bypass = _transport_bypass_violations(root)
    return {
        "schema_version": "qcol-semantic-leakage-audit/1.1",
        "family_authoritative_condition_violations": family_violations,
        "ui_resource_formula_violations": ui_formula_violations,
        "backend_bypass_violations": backend_bypass,
        "transport_bypass_violations": transport_bypass,
        "family_leakage_free": not family_violations,
        "ui_display_only": not ui_formula_violations,
        "backend_invocation_owned_by_execution_adapter": not backend_bypass,
        "pyqasm_owned_by_translation_boundary": not transport_bypass,
        "pass": not (
            family_violations
            or ui_formula_violations
            or backend_bypass
            or transport_bypass
        ),
    }
