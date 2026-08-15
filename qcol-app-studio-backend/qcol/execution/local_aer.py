"""Post-freeze LocalAer ExecutionAdapter.

The frozen QCOL pipeline remains authoritative for:
Cirq circuit construction -> OpenQASM 2 export -> PyQASM validation/unrolling.
The adapter receives the already validated/re-imported executable circuit,
re-emits the bounded OpenQASM 2 transport artifact, invokes Qiskit Aer, and
normalizes provider-style memory back to canonical q[0]...q[n-1] order.

Qiskit/Aer is optional and exists only behind the ExecutionAdapter seam.
"""
from __future__ import annotations

from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import time
from typing import Sequence

import cirq
import numpy as np

from ..measurement import counts_from_measurements
from ..translation import export_openqasm2
from .contracts import CanonicalExecutionResult
from .descriptors import LOCAL_AER_DESCRIPTOR
from .qiskit_normalization import (
    normalize_qiskit_memory,
    ordered_execution_qubits,
    qasm_measurement_pairs,
    qasm_registers,
    qiskit_measurement_pairs,
)


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unknown"


class LocalAerExecutionAdapter:
    descriptor = LOCAL_AER_DESCRIPTOR

    @classmethod
    def availability(cls) -> dict[str, object]:
        try:
            import qiskit  # noqa: F401
            import qiskit_aer  # noqa: F401
        except Exception as exc:
            return {"available": False, "reason": repr(exc)}
        return {"available": True, "reason": None}

    def run_measurement(
        self,
        circuit: cirq.Circuit,
        *,
        repetitions: int,
        seed: int,
    ) -> CanonicalExecutionResult:
        try:
            from qiskit import qasm2, transpile
            from qiskit_aer import AerSimulator
        except Exception as exc:
            raise RuntimeError(
                "LocalAer requires the optional execution profile: "
                "qiskit==2.2.2 and qiskit-aer==0.17.2."
            ) from exc

        started = time.perf_counter()
        ordered_qubits = ordered_execution_qubits(circuit)
        n_qubits = len(ordered_qubits)
        if n_qubits <= 0:
            raise ValueError("LocalAer received an empty executable circuit.")
        qasm_text = export_openqasm2(circuit, ordered_qubits)
        qregs, cregs = qasm_registers(qasm_text)
        if len(qregs) != 1 or not cregs:
            raise ValueError(
                "E1 LocalAer requires one declared qreg and one or more declared cregs."
            )
        n_clbits = sum(int(size) for size in cregs.values())
        expected_pairs = qasm_measurement_pairs(
            qasm_text,
            expected_n_qubits=n_qubits,
        )

        imported = qasm2.loads(qasm_text, strict=False)
        imported_pairs = qiskit_measurement_pairs(imported)
        if imported_pairs != expected_pairs:
            raise AssertionError(
                "Qiskit imported a measurement map different from the QASM2 map: "
                f"expected={expected_pairs}, imported={imported_pairs}."
            )

        backend = AerSimulator(method="automatic", seed_simulator=int(seed))
        compiled = transpile(
            imported,
            backend,
            optimization_level=0,
            seed_transpiler=int(seed),
        )
        compiled_pairs = qiskit_measurement_pairs(compiled)
        if compiled_pairs != expected_pairs:
            raise AssertionError(
                "Aer transpilation changed logical-to-classical measurement semantics: "
                f"expected={expected_pairs}, compiled={compiled_pairs}."
            )

        job = backend.run(
            compiled,
            shots=int(repetitions),
            seed_simulator=int(seed),
            memory=True,
        )
        result = job.result()
        memory = [str(value) for value in result.get_memory(compiled)]
        bits = normalize_qiskit_memory(
            memory,
            n_clbits=int(n_clbits),
            n_qubits=n_qubits,
            measurement_pairs=expected_pairs,
        )
        counts = counts_from_measurements(bits)

        job_id = None
        try:
            job_id = str(job.job_id())
        except Exception:
            pass
        elapsed = time.perf_counter() - started
        qasm_hash = sha256(qasm_text.encode("utf-8")).hexdigest()
        return CanonicalExecutionResult(
            measurement_bits=bits,
            counts=counts,
            imported_qubit_order=tuple(str(qubit) for qubit in ordered_qubits),
            shots_requested=int(repetitions),
            shots_observed=int(bits.shape[0]),
            adapter=self.descriptor,
            raw_result_type=f"{type(result).__module__}.{type(result).__name__}",
            metadata={
                "seed": int(seed),
                "canonical_bit_order_declared": True,
                "canonical_bit_order": [f"q[{index}]" for index in range(n_qubits)],
                "measurement_pairs": [list(pair) for pair in expected_pairs],
                "qasm_quantum_registers": dict(qregs),
                "qasm_classical_registers": dict(cregs),
                "qasm_classical_register_count": len(cregs),
                "qasm_classical_bit_count": int(n_clbits),
                "transport_profile": "one_qreg_explicit_one_or_more_cregs.v1",
                "qasm2_sha256": qasm_hash,
                "qasm2_source": "re-emitted from the frozen PyQASM-validated Cirq executable",
                "validation_authority": "PyQASM in the shared QCOL pipeline",
                "qasm_importer": "qiskit.qasm2.loads",
                "transpiler": "qiskit.transpile",
                "optimization_level": 0,
                "compiled_depth": int(compiled.depth()),
                "compiled_size": int(compiled.size()),
                "qiskit_version": _package_version("qiskit"),
                "qiskit_aer_version": _package_version("qiskit-aer"),
                "job_id": job_id,
                "wall_time_seconds": float(elapsed),
                "hardware_submission_performed": False,
                "remote_provider_invoked": False,
            },
        )

    def simulate_statevector(
        self,
        circuit: cirq.Circuit,
        *,
        qubit_order: Sequence[cirq.Qid],
    ) -> np.ndarray:
        """Keep exact scientific diagnostics on the accepted Cirq definition.

        E1 changes sampled execution only.  Sector diagnostics remain independent
        of the execution framework and therefore retain the frozen Cirq
        statevector implementation.
        """
        return np.asarray(
            cirq.Simulator(dtype=np.complex128).simulate(
                circuit,
                qubit_order=tuple(qubit_order),
            ).final_state_vector,
            dtype=np.complex128,
        )


LOCAL_AER_ADAPTER = LocalAerExecutionAdapter()

__all__ = ["LocalAerExecutionAdapter", "LOCAL_AER_ADAPTER"]
