"""Shared runtime constants and reproducibility metadata for the QCOL local scientific runtime."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as package_version
import platform
from typing import Dict

APP_VERSION = "phase4.1-fermion-registry-v1.1.0"
SEED = 42
DEFAULT_SHOTS = 2048
DEFAULT_MAX_EVALUATIONS = 24
DEFAULT_ENERGY_TOLERANCE = 0.01
DEFAULT_RHOBEG = 0.7
REFERENCE_POLICY = "mentor_decision_pending"
NUMERIC_TOL = 1e-10
QASM_EQUIVALENCE_ATOL = 1e-8
QASM_EQUIVALENCE_MAX_QUBITS = 8
QCOL_QASM2_EXTERNAL_GATES = (
    "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg",
    "rx", "ry", "rz", "u1", "u2", "u3", "cx", "cz", "swap",
)


def safe_package_version(name: str) -> str:
    try:
        return package_version(name)
    except PackageNotFoundError:
        return "NOT_INSTALLED"


def collect_versions() -> Dict[str, str]:
    distributions = {
        "numpy": "numpy",
        "scipy": "scipy",
        "sympy": "sympy",
        "matplotlib": "matplotlib",
        "pandas": "pandas",
        "cirq_core": "cirq-core",
        "openfermion": "openfermion",
        "pyqasm": "pyqasm",
        "gradio": "gradio",
    }
    return {
        "qcol_app": APP_VERSION,
        "python": platform.python_version(),
        **{key: safe_package_version(dist) for key, dist in distributions.items()},
    }


VERSIONS = collect_versions()
