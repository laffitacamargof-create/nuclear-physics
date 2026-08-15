"""Comparable operator-level resource metrics for mapping analysis."""
from __future__ import annotations

from collections import Counter
import math
import statistics
import time
from typing import Any, Dict, Iterable, Mapping, Sequence

from .base import MappingResourceReport


def _qwc_compatible(active: Mapping[int, str], candidate: Mapping[int, str]) -> bool:
    return all(active.get(index, pauli) == pauli for index, pauli in candidate.items())


def qwc_group_count(qubit_operator: Any, *, coefficient_threshold: float = 0.0) -> int:
    terms = [
        term
        for term, coefficient in qubit_operator.terms.items()
        if term and abs(complex(coefficient)) > float(coefficient_threshold)
    ]
    terms.sort(key=lambda term: (-len(term), term))
    groups: list[Dict[int, str]] = []
    for term in terms:
        basis = {int(index): str(pauli) for index, pauli in term}
        for group in groups:
            if _qwc_compatible(group, basis):
                group.update(basis)
                break
        else:
            groups.append(dict(basis))
    return len(groups)


def mapping_resource_report(
    mapping_id: str,
    qubit_operator: Any,
    *,
    n_modes: int,
    n_qubits: int,
    transform_seconds: float,
    coefficient_threshold: float = 1e-12,
) -> MappingResourceReport:
    weighted_terms = []
    identity_count = 0
    axes: Counter[str] = Counter()
    l1 = 0.0
    for term, coefficient in qubit_operator.terms.items():
        magnitude = abs(complex(coefficient))
        if magnitude <= coefficient_threshold:
            continue
        l1 += magnitude
        if not term:
            identity_count += 1
            weighted_terms.append((0, magnitude))
            continue
        weight = len(term)
        weighted_terms.append((weight, magnitude))
        for _, pauli in term:
            axes[str(pauli)] += 1
    weights = [item[0] for item in weighted_terms]
    nonzero = [item for item in weights if item > 0]
    minimum = min(nonzero) if nonzero else 0
    maximum = max(weights) if weights else 0
    mean = float(statistics.fmean(weights)) if weights else 0.0
    median = float(statistics.median(weights)) if weights else 0.0
    weighted_denominator = sum(magnitude for _, magnitude in weighted_terms)
    weighted_mean = (
        sum(weight * magnitude for weight, magnitude in weighted_terms) / weighted_denominator
        if weighted_denominator > 0 else 0.0
    )
    return MappingResourceReport(
        mapping_id=mapping_id,
        n_modes=int(n_modes),
        n_qubits=int(n_qubits),
        pauli_term_count=len(weighted_terms),
        identity_term_count=identity_count,
        minimum_pauli_weight=int(minimum),
        maximum_pauli_weight=int(maximum),
        mean_pauli_weight=float(mean),
        median_pauli_weight=float(median),
        coefficient_weighted_mean_pauli_weight=float(weighted_mean),
        coefficient_l1_norm=float(l1),
        axis_support_profile={axis: int(axes.get(axis, 0)) for axis in ("X", "Y", "Z")},
        qwc_measurement_group_count=qwc_group_count(
            qubit_operator, coefficient_threshold=coefficient_threshold
        ),
        transform_seconds=float(transform_seconds),
    )
