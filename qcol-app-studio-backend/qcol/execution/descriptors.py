"""Dependency-light execution-adapter descriptors."""
from .contracts import ExecutionAdapterDescriptor

LOCAL_CIRQ_DESCRIPTOR = ExecutionAdapterDescriptor(
    adapter_id="execution.local_cirq.v1",
    adapter_version="1.0.0",
    provider="QCOL/Cirq",
    execution_mode="local_simulator",
    backend_kind="statevector_and_sampled_simulator",
    capabilities=(
        "sample_measurement_circuits",
        "ideal_statevector_diagnostics",
        "canonical_bitstring_counts",
    ),
    limitations=(
        "No real provider submission is performed.",
        "Provider target labels remain declarations until Phase 5 adapters pass acceptance.",
    ),
)

LOCAL_AER_DESCRIPTOR = ExecutionAdapterDescriptor(
    adapter_id="execution.local_aer.v1",
    adapter_version="1.0.1",
    provider="QCOL/Qiskit Aer",
    execution_mode="local_simulator",
    backend_kind="qasm2_sampled_simulator",
    capabilities=(
        "consume_frozen_qasm2_execution_profile",
        "sample_measurement_circuits",
        "canonical_bitstring_counts",
        "per_shot_memory",
        "deterministic_seed",
        "explicit_multi_register_measurement_map",
        "line_and_qasm_named_qubit_order",
    ),
    limitations=(
        "Ideal local Qiskit Aer simulator only.",
        "PyQASM validation remains owned by the shared QCOL pipeline.",
        "The E1 adapter does not submit IBM Runtime or hardware jobs.",
        "Statevector sector diagnostics remain on the frozen Cirq diagnostic path.",
    ),
)

__all__ = ["LOCAL_CIRQ_DESCRIPTOR", "LOCAL_AER_DESCRIPTOR"]
