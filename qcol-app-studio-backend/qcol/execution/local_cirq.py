"""The accepted local Cirq execution adapter.

This is the only local backend-invocation owner.  It preserves the current
scientific behaviour while making the execution boundary explicit for future
IBM/Google/AWS adapters.
"""
from __future__ import annotations

from typing import Sequence

import cirq
import numpy as np

from ..measurement import (
    counts_from_measurements,
    extract_measurement_matrix,
)
from .contracts import CanonicalExecutionResult
from .descriptors import LOCAL_CIRQ_DESCRIPTOR


class LocalCirqExecutionAdapter:
    descriptor = LOCAL_CIRQ_DESCRIPTOR

    def run_measurement(
        self,
        circuit: cirq.Circuit,
        *,
        repetitions: int,
        seed: int,
    ) -> CanonicalExecutionResult:
        simulator = cirq.Simulator(dtype=np.complex128, seed=int(seed))
        raw = simulator.run(circuit, repetitions=int(repetitions))
        bits, imported_order = extract_measurement_matrix(raw, circuit)
        counts = counts_from_measurements(bits)
        return CanonicalExecutionResult(
            measurement_bits=bits,
            counts=counts,
            imported_qubit_order=tuple(str(qubit) for qubit in imported_order),
            shots_requested=int(repetitions),
            shots_observed=int(bits.shape[0]),
            adapter=self.descriptor,
            raw_result_type=f"{type(raw).__module__}.{type(raw).__name__}",
            metadata={
                "seed": int(seed),
                "canonical_bit_order_declared": True,
                "hardware_submission_performed": False,
            },
        )

    def simulate_statevector(
        self,
        circuit: cirq.Circuit,
        *,
        qubit_order: Sequence[cirq.Qid],
    ) -> np.ndarray:
        return np.asarray(
            cirq.Simulator(dtype=np.complex128).simulate(
                circuit,
                qubit_order=tuple(qubit_order),
            ).final_state_vector,
            dtype=np.complex128,
        )


LOCAL_CIRQ_ADAPTER = LocalCirqExecutionAdapter()

__all__ = ["LocalCirqExecutionAdapter", "LOCAL_CIRQ_ADAPTER"]
