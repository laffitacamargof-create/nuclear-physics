"""Fermion problem registry and dynamic parameter schemas for QCOL.

The registry separates three decisions that were previously conflated:

1. the physical model/problem,
2. the target physical sector, and
3. the qubit mapping / ansatz / reference policy compatible with that problem.

It is intentionally dependency-light: this module imports no Cirq, OpenFermion,
NumPy, or Gradio objects.  The same registry can therefore be consumed by the
FastAPI catalog, the web dashboard, the Gradio shell, tests, and the scientific
builder without duplicating physical constraints.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


FERMION_REGISTRY_VERSION = "fermion-problem-registry/1.0"
FERMION_SCHEMA_VERSION = "fermion-dynamic-schema/1.0"


class FermionProblemContractError(ValueError):
    """Structured error raised when a request violates a problem contract."""

    def __init__(
        self,
        message: str,
        *,
        code: str,
        problem_id: Optional[str] = None,
        field_name: Optional[str] = None,
        expected: Any = None,
        received: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = str(message)
        self.code = str(code)
        self.problem_id = problem_id
        self.field_name = field_name
        self.expected = expected
        self.received = received

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "message": self.message,
            "code": self.code,
        }
        if self.problem_id is not None:
            payload["problem_id"] = self.problem_id
        if self.field_name is not None:
            payload["field"] = self.field_name
        if self.expected is not None:
            payload["expected"] = deepcopy(self.expected)
        if self.received is not None:
            payload["received"] = deepcopy(self.received)
        return payload


@dataclass(frozen=True)
class ParameterFieldSpec:
    """One field in a problem-specific, no-code parameter schema."""

    key: str
    label: str
    kind: str
    role: str = "editable"  # editable | fixed | derived
    default: Any = None
    fixed_value: Any = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    exact_length: Optional[int] = None
    length_from: Optional[str] = None
    item_kind: Optional[str] = None
    unit_key: Optional[str] = None
    help_text: str = ""
    visible: bool = True
    order: int = 0

    def to_public_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "role": self.role,
            "default": deepcopy(self.default),
            "fixed_value": deepcopy(self.fixed_value),
            "minimum": self.minimum,
            "maximum": self.maximum,
            "step": self.step,
            "exact_length": self.exact_length,
            "length_from": self.length_from,
            "item_kind": self.item_kind,
            "unit_key": self.unit_key,
            "help_text": self.help_text,
            "visible": self.visible,
            "order": self.order,
        }


@dataclass(frozen=True)
class FermionProblemSpec:
    """The complete physical/software contract for one fermion problem route."""

    problem_id: str
    label: str
    description: str
    model_id: str
    support_status: str
    execution_status: str
    selectable: bool
    parameter_fields: Tuple[ParameterFieldSpec, ...]
    mapping_policy: str
    encoding: str
    sector_policy: str
    state_preparation_policy: str
    ansatz_family: str
    reference_policy: str
    supported_observables: Tuple[str, ...]
    assumptions: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    implementation_requirements: Tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = FERMION_SCHEMA_VERSION

    @property
    def executable(self) -> bool:
        return self.execution_status in {"execution_ready", "experimental", "acceptance_verified"}

    def field(self, key: str) -> ParameterFieldSpec:
        for item in self.parameter_fields:
            if item.key == key:
                return item
        raise KeyError(key)

    def to_public_dict(self) -> Dict[str, Any]:
        fields = sorted(self.parameter_fields, key=lambda item: item.order)
        return {
            "id": self.problem_id,
            "label": self.label,
            "description": self.description,
            "model_id": self.model_id,
            "support_status": self.support_status,
            "execution_status": self.execution_status,
            "selectable": self.selectable,
            "executable": self.executable,
            "schema_version": self.schema_version,
            "mapping_policy": self.mapping_policy,
            "encoding": self.encoding,
            "sector_policy": self.sector_policy,
            "state_preparation_policy": self.state_preparation_policy,
            "ansatz_family": self.ansatz_family,
            "reference_policy": self.reference_policy,
            "supported_observables": list(self.supported_observables),
            "assumptions": list(self.assumptions),
            "limitations": list(self.limitations),
            "implementation_requirements": list(self.implementation_requirements),
            "parameter_schema": {
                "version": self.schema_version,
                "fields": [item.to_public_dict() for item in fields],
            },
        }


def _fixed_integer(key: str, label: str, value: int, order: int, help_text: str) -> ParameterFieldSpec:
    return ParameterFieldSpec(
        key=key,
        label=label,
        kind="integer",
        role="fixed",
        default=value,
        fixed_value=value,
        help_text=help_text,
        order=order,
    )


def _fixed_text(key: str, label: str, value: str, order: int, help_text: str) -> ParameterFieldSpec:
    return ParameterFieldSpec(
        key=key,
        label=label,
        kind="text",
        role="fixed",
        default=value,
        fixed_value=value,
        help_text=help_text,
        order=order,
    )


FOUR_LEVEL_ONE_PAIR = FermionProblemSpec(
    problem_id="four_level_one_pair",
    label="Four-level one-pair benchmark",
    description=(
        "Verified acceptance benchmark for one correlated pair distributed across "
        "exactly four single-particle levels."
    ),
    model_id="reduced_bcs_pairing",
    support_status="verified_acceptance_case",
    execution_status="execution_ready",
    selectable=True,
    parameter_fields=(
        _fixed_integer(
            "n_levels", "Number of levels", 4, 10,
            "Fixed by the four-level benchmark contract.",
        ),
        ParameterFieldSpec(
            key="epsilon",
            label="Single-particle energies ε",
            kind="vector",
            item_kind="number",
            role="editable",
            default=[0.0, 1.0, 2.0, 3.0],
            exact_length=4,
            unit_key="energy_unit",
            help_text="Exactly four finite energies, one for each declared level.",
            order=20,
        ),
        ParameterFieldSpec(
            key="g",
            label="Pairing strength G",
            kind="number",
            role="editable",
            default=0.5,
            minimum=0.0,
            step=0.01,
            unit_key="energy_unit",
            help_text="Finite attractive pairing strength; G must be strictly positive.",
            order=30,
        ),
        _fixed_integer(
            "n_particles", "Number of particles", 2, 40,
            "One pair contains exactly two particles.",
        ),
        _fixed_integer(
            "n_pairs", "Number of pairs", 1, 50,
            "Fixed one-pair sector.",
        ),
        _fixed_integer(
            "seniority", "Seniority", 0, 60,
            "The verified route is restricted to fully paired seniority-zero states.",
        ),
        _fixed_text(
            "mapping", "Mapping", "pair_mapping", 70,
            "Selected automatically because this route is a one-pair seniority-zero model.",
        ),
        ParameterFieldSpec(
            key="energy_unit",
            label="Energy unit",
            kind="text",
            role="editable",
            default="MeV",
            help_text="Unit applied consistently to ε, G, and reconstructed energy.",
            order=80,
        ),
    ),
    mapping_policy="pair_mapping_required",
    encoding="seniority_zero_pair_occupation",
    sector_policy="fixed particle_number=2, pair_number=1, seniority=0",
    state_preparation_policy="one occupied pair level followed by pair-number-conserving rotations",
    ansatz_family="one_pair_chain_givens",
    reference_policy="exact diagonalisation in the declared one-pair sector",
    supported_observables=("sector energy", "pair occupations when measured"),
    assumptions=(
        "reduced attractive pairing Hamiltonian",
        "one correlated pair",
        "seniority-zero sector",
    ),
    limitations=(
        "not a multi-pair model",
        "not a general shell-model Hamiltonian",
        "small-system exact reference is part of the acceptance case",
    ),
)


GENERAL_ONE_PAIR = FermionProblemSpec(
    problem_id="one_pair_pairing",
    label="General one-pair pairing model",
    description=(
        "A bounded one-pair seniority-zero family with a configurable number of "
        "levels.  'General' refers to the level count and ε values, not to a "
        "general fermionic many-body model."
    ),
    model_id="reduced_bcs_pairing",
    support_status="supported_bounded_route",
    execution_status="execution_ready",
    selectable=True,
    parameter_fields=(
        ParameterFieldSpec(
            key="n_levels",
            label="Number of levels",
            kind="integer",
            role="editable",
            default=4,
            minimum=2,
            maximum=6,
            step=1,
            help_text="Bounded to 2–6 levels so exact-sector and QASM checks remain tractable.",
            order=10,
        ),
        ParameterFieldSpec(
            key="epsilon",
            label="Single-particle energies ε",
            kind="vector",
            item_kind="number",
            role="editable",
            default=[0.0, 1.0, 2.0, 3.0],
            length_from="n_levels",
            unit_key="energy_unit",
            help_text="The interface creates one ε field per selected level.",
            order=20,
        ),
        ParameterFieldSpec(
            key="g",
            label="Pairing strength G",
            kind="number",
            role="editable",
            default=0.5,
            minimum=0.0,
            step=0.01,
            unit_key="energy_unit",
            help_text="Finite attractive pairing strength; G must be strictly positive.",
            order=30,
        ),
        _fixed_integer(
            "n_particles", "Number of particles", 2, 40,
            "The currently supported generalized route still contains one pair only.",
        ),
        _fixed_integer(
            "n_pairs", "Number of pairs", 1, 50,
            "Fixed one-pair sector.",
        ),
        _fixed_integer(
            "seniority", "Seniority", 0, 60,
            "The execution-ready path remains seniority zero.",
        ),
        _fixed_text(
            "mapping", "Mapping", "pair_mapping", 70,
            "Selected automatically for the supported one-pair sector.",
        ),
        ParameterFieldSpec(
            key="energy_unit",
            label="Energy unit",
            kind="text",
            role="editable",
            default="MeV",
            help_text="Unit applied consistently to ε, G, and reconstructed energy.",
            order=80,
        ),
    ),
    mapping_policy="pair_mapping_required",
    encoding="seniority_zero_pair_occupation",
    sector_policy="fixed particle_number=2, pair_number=1, seniority=0",
    state_preparation_policy="one occupied pair level followed by pair-number-conserving rotations",
    ansatz_family="one_pair_chain_givens",
    reference_policy="exact diagonalisation in the declared one-pair sector",
    supported_observables=("sector energy", "pair occupations when measured"),
    assumptions=(
        "reduced attractive pairing Hamiltonian",
        "one correlated pair",
        "seniority-zero sector",
    ),
    limitations=(
        "the number of pairs is not configurable",
        "the route does not represent a general fermionic Hamiltonian",
        "level count is bounded to six in QCOL v1",
    ),
)


MULTI_PAIR_SENIORITY_ZERO = FermionProblemSpec(
    problem_id="multi_pair_seniority_zero",
    label="Multi-pair seniority-zero pairing model",
    description=(
        "An independent reduced-pairing model contract for two or more intact "
        "correlated pairs.  The implementation reuses Bathri's multi-pair-capable "
        "pair mapping, lowest-level reference occupation, and occupied-to-virtual "
        "Givens topology, while the shared QCOL runtime remains unchanged."
    ),
    model_id="nuclear.reduced_pairing.multi_pair",
    support_status="execution_ready_experimental",
    execution_status="experimental",
    selectable=True,
    parameter_fields=(
        ParameterFieldSpec(
            key="n_levels", label="Number of levels", kind="integer", role="editable",
            default=4, minimum=4, maximum=6, step=1, order=10,
            help_text="Bounded to 4–6 levels for the first multi-pair acceptance envelope.",
        ),
        ParameterFieldSpec(
            key="epsilon", label="Single-particle energies ε", kind="vector",
            item_kind="number", role="editable", default=[0.0, 1.0, 2.0, 3.0],
            length_from="n_levels", unit_key="energy_unit", order=20,
            help_text="Exactly one finite energy per declared level.",
        ),
        ParameterFieldSpec(
            key="g", label="Pairing strength G", kind="number", role="editable",
            default=0.5, minimum=0.0, step=0.01, unit_key="energy_unit", order=30,
            help_text="Finite attractive pairing strength; G must be strictly positive.",
        ),
        ParameterFieldSpec(
            key="n_pairs", label="Number of pairs", kind="integer", role="editable",
            default=2, minimum=2, maximum=3, step=1, order=40,
            help_text="Must satisfy 2 ≤ n_pairs < n_levels inside the bounded route.",
        ),
        ParameterFieldSpec(
            key="n_particles", label="Number of particles", kind="integer",
            role="derived", default=4, help_text="Derived as 2 × n_pairs.", order=50,
        ),
        _fixed_integer("seniority", "Seniority", 0, 60, "Fully paired seniority-zero sector."),
        _fixed_text("mapping", "Mapping", "pair_mapping", 70, "Selected by this model contract."),
        ParameterFieldSpec(
            key="energy_unit", label="Energy unit", kind="text", role="editable",
            default="MeV", help_text="Applied consistently to ε, G, and energy.", order=80,
        ),
    ),
    mapping_policy="pair_mapping_required",
    encoding="multi_pair_seniority_zero_pair_occupation",
    sector_policy="fixed n_pairs >= 2, particle_number=2*n_pairs, seniority=0",
    state_preparation_policy="Bathri lowest-level multi-pair occupation state",
    ansatz_family="bathri_multi_pair_givens",
    reference_policy="small exact fixed-pair-sector solver inside the acceptance envelope",
    supported_observables=("sector energy", "pair occupations when measured", "sector leakage when measured"),
    assumptions=(
        "reduced attractive pairing Hamiltonian",
        "two or more intact correlated pairs",
        "seniority-zero pair-occupation encoding",
    ),
    limitations=(
        "experimental until the multi-pair acceptance suite promotes it",
        "not a broken-pair or general shell-model route",
        "small exact-sector reference only in the current implementation",
    ),
    implementation_requirements=(
        "multi-pair acceptance matrix",
        "end-to-end energy/reference agreement",
        "sector-preservation and QASM semantic checks",
    ),
)


GENERAL_FERMIONIC_MODEL = FermionProblemSpec(
    problem_id="general_fermionic_model",
    label="General fermionic / shell-model Hamiltonian",
    description=(
        "Registered as a separate future family requiring a general occupation "
        "mapping, state preparation, ansatz, constraints, and reference policy."
    ),
    model_id="general_fermionic_shell_model",
    support_status="registered_future_problem",
    execution_status="not_implemented",
    selectable=False,
    parameter_fields=tuple(),
    mapping_policy="JW_or_BK_after_route_specific_validation",
    encoding="general_spin_orbital_occupation_or_parity_encoding",
    sector_policy="problem-specific particle number, parity, angular momentum, and symmetries",
    state_preparation_policy="mapping-aware occupation or symmetry-adapted preparation",
    ansatz_family="problem-specific fermionic ansatz",
    reference_policy="problem-specific classical reference or bounded verification policy",
    supported_observables=("problem-specific observables",),
    limitations=("not executable in the current release",),
    implementation_requirements=(
        "second-quantized problem schema",
        "JW/BK-aware state preparation",
        "sector and symmetry checks",
        "fermionic ansatz registry",
        "reference/verification policy",
    ),
)


FERMION_PROBLEM_REGISTRY: Dict[str, FermionProblemSpec] = {
    spec.problem_id: spec
    for spec in (
        FOUR_LEVEL_ONE_PAIR,
        GENERAL_ONE_PAIR,
        MULTI_PAIR_SENIORITY_ZERO,
        GENERAL_FERMIONIC_MODEL,
    )
}


def list_fermion_problem_specs(*, include_unavailable: bool = True) -> Tuple[FermionProblemSpec, ...]:
    specs = tuple(FERMION_PROBLEM_REGISTRY.values())
    if include_unavailable:
        return specs
    return tuple(spec for spec in specs if spec.selectable and spec.executable)


def get_fermion_problem_spec(
    problem_id: str,
    *,
    require_executable: bool = False,
) -> FermionProblemSpec:
    try:
        spec = FERMION_PROBLEM_REGISTRY[str(problem_id)]
    except KeyError as exc:
        raise FermionProblemContractError(
            f"Unknown fermion problem {problem_id!r}.",
            code="unknown_fermion_problem",
            problem_id=str(problem_id),
            expected=sorted(FERMION_PROBLEM_REGISTRY),
            received=problem_id,
        ) from exc
    if require_executable and not spec.executable:
        raise FermionProblemContractError(
            (
                f"{spec.label} is registered as a distinct problem contract but is "
                "not executable in the current release."
            ),
            code="fermion_problem_not_executable",
            problem_id=spec.problem_id,
            expected="execution_ready",
            received=spec.execution_status,
        )
    return spec


def public_fermion_problem_catalog(*, include_unavailable: bool = True) -> list[Dict[str, Any]]:
    return [
        spec.to_public_dict()
        for spec in list_fermion_problem_specs(include_unavailable=include_unavailable)
    ]


def _as_integer(value: Any, *, field_name: str, problem_id: str) -> int:
    if isinstance(value, bool):
        raise FermionProblemContractError(
            f"{field_name} must be an integer, not a boolean.",
            code="invalid_integer",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        )
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise FermionProblemContractError(
            f"{field_name} must be an integer.",
            code="invalid_integer",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        ) from exc
    try:
        if float(value) != float(number):
            raise ValueError
    except (TypeError, ValueError):
        raise FermionProblemContractError(
            f"{field_name} must be an integer.",
            code="invalid_integer",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        )
    return number


def _as_float(value: Any, *, field_name: str, problem_id: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FermionProblemContractError(
            f"{field_name} must be numeric.",
            code="invalid_number",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        ) from exc
    if not math.isfinite(number):
        raise FermionProblemContractError(
            f"{field_name} must be finite.",
            code="non_finite_number",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        )
    return number


def _as_vector(value: Any, *, field_name: str, problem_id: str) -> list[float]:
    if isinstance(value, str):
        raw = [item.strip() for item in value.split(",") if item.strip()]
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        raw = list(value)
    else:
        raise FermionProblemContractError(
            f"{field_name} must be a list or a comma-separated list.",
            code="invalid_vector",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        )
    if not raw:
        raise FermionProblemContractError(
            f"{field_name} must not be empty.",
            code="empty_vector",
            problem_id=problem_id,
            field_name=field_name,
            received=value,
        )
    return [
        _as_float(item, field_name=f"{field_name}[{index}]", problem_id=problem_id)
        for index, item in enumerate(raw)
    ]


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)
    return left == right


def _default_epsilon(n_levels: int, declared_default: Any) -> list[float]:
    if isinstance(declared_default, Sequence) and not isinstance(declared_default, str):
        values = [float(item) for item in declared_default]
        if len(values) == n_levels:
            return values
    return [float(index) for index in range(n_levels)]


def normalize_fermion_parameters(
    problem_id: str,
    parameters: Optional[Mapping[str, Any]],
    *,
    require_executable: bool = True,
) -> Dict[str, Any]:
    """Validate and canonicalize parameters against one problem contract."""
    spec = get_fermion_problem_spec(problem_id, require_executable=require_executable)
    supplied = dict(parameters or {})
    allowed = {field.key for field in spec.parameter_fields}
    unknown = sorted(set(supplied) - allowed)
    if unknown:
        raise FermionProblemContractError(
            f"Unsupported parameter(s) for {spec.label}: {', '.join(unknown)}.",
            code="unknown_problem_parameter",
            problem_id=problem_id,
            expected=sorted(allowed),
            received=unknown,
        )

    normalized: Dict[str, Any] = {}
    for field_spec in sorted(spec.parameter_fields, key=lambda item: item.order):
        key = field_spec.key
        if field_spec.role == "fixed":
            fixed = deepcopy(field_spec.fixed_value)
            if key in supplied and not _values_equal(supplied[key], fixed):
                raise FermionProblemContractError(
                    (
                        f"{field_spec.label} is fixed to {fixed!r} by the "
                        f"{spec.label} contract."
                    ),
                    code="fixed_parameter_conflict",
                    problem_id=problem_id,
                    field_name=key,
                    expected=fixed,
                    received=supplied[key],
                )
            normalized[key] = fixed

    if spec.problem_id == "four_level_one_pair":
        n_levels = 4
    else:
        n_levels_field = spec.field("n_levels")
        if "n_levels" in supplied:
            n_levels = _as_integer(supplied["n_levels"], field_name="n_levels", problem_id=problem_id)
        elif "epsilon" in supplied:
            n_levels = len(_as_vector(supplied["epsilon"], field_name="epsilon", problem_id=problem_id))
        else:
            n_levels = int(n_levels_field.default)
        if n_levels_field.minimum is not None and n_levels < int(n_levels_field.minimum):
            raise FermionProblemContractError(
                f"n_levels must be at least {int(n_levels_field.minimum)}.",
                code="parameter_below_minimum",
                problem_id=problem_id,
                field_name="n_levels",
                expected={"minimum": int(n_levels_field.minimum)},
                received=n_levels,
            )
        if n_levels_field.maximum is not None and n_levels > int(n_levels_field.maximum):
            raise FermionProblemContractError(
                f"n_levels must be at most {int(n_levels_field.maximum)} in QCOL v1.",
                code="parameter_above_maximum",
                problem_id=problem_id,
                field_name="n_levels",
                expected={"maximum": int(n_levels_field.maximum)},
                received=n_levels,
            )
        normalized["n_levels"] = n_levels

    epsilon_field = spec.field("epsilon")
    epsilon = (
        _as_vector(supplied["epsilon"], field_name="epsilon", problem_id=problem_id)
        if "epsilon" in supplied
        else _default_epsilon(n_levels, epsilon_field.default)
    )
    expected_length = epsilon_field.exact_length or n_levels
    if len(epsilon) != int(expected_length):
        raise FermionProblemContractError(
            (
                f"{spec.label} requires exactly {int(expected_length)} ε values; "
                f"received {len(epsilon)}."
            ),
            code="epsilon_length_mismatch",
            problem_id=problem_id,
            field_name="epsilon",
            expected={"length": int(expected_length)},
            received={"length": len(epsilon), "values": epsilon},
        )
    normalized["epsilon"] = epsilon

    g_field = spec.field("g")
    g_value = _as_float(supplied.get("g", g_field.default), field_name="g", problem_id=problem_id)
    if g_value <= 0:
        raise FermionProblemContractError(
            "The supported attractive pairing routes require G > 0.",
            code="non_positive_pairing_strength",
            problem_id=problem_id,
            field_name="g",
            expected={"exclusive_minimum": 0},
            received=g_value,
        )
    normalized["g"] = g_value

    unit_field = spec.field("energy_unit")
    energy_unit = str(supplied.get("energy_unit", unit_field.default) or "").strip()
    if not energy_unit:
        raise FermionProblemContractError(
            "energy_unit must not be empty.",
            code="empty_energy_unit",
            problem_id=problem_id,
            field_name="energy_unit",
            received=energy_unit,
        )
    normalized["energy_unit"] = energy_unit

    # Complete model-specific derived/fixed sector declarations.
    normalized["n_levels"] = int(normalized.get("n_levels", n_levels))
    if spec.problem_id == "multi_pair_seniority_zero":
        pairs_field = spec.field("n_pairs")
        n_pairs = _as_integer(
            supplied.get("n_pairs", pairs_field.default),
            field_name="n_pairs",
            problem_id=problem_id,
        )
        if pairs_field.minimum is not None and n_pairs < int(pairs_field.minimum):
            raise FermionProblemContractError(
                f"n_pairs must be at least {int(pairs_field.minimum)}.",
                code="parameter_below_minimum", problem_id=problem_id,
                field_name="n_pairs", expected={"minimum": int(pairs_field.minimum)},
                received=n_pairs,
            )
        if pairs_field.maximum is not None and n_pairs > int(pairs_field.maximum):
            raise FermionProblemContractError(
                f"n_pairs must be at most {int(pairs_field.maximum)} in the current acceptance envelope.",
                code="parameter_above_maximum", problem_id=problem_id,
                field_name="n_pairs", expected={"maximum": int(pairs_field.maximum)},
                received=n_pairs,
            )
        if n_pairs >= normalized["n_levels"]:
            raise FermionProblemContractError(
                "n_pairs must be strictly smaller than n_levels.",
                code="invalid_pair_sector", problem_id=problem_id,
                field_name="n_pairs", expected={"less_than": normalized["n_levels"]},
                received=n_pairs,
            )
        normalized["n_pairs"] = n_pairs
        normalized["n_particles"] = 2 * n_pairs
    normalized["n_particles"] = int(normalized["n_particles"])
    normalized["n_pairs"] = int(normalized["n_pairs"])
    normalized["seniority"] = int(normalized["seniority"])
    normalized["mapping"] = str(normalized["mapping"])
    return normalized


def normalize_fermion_request(
    request: Mapping[str, Any],
    *,
    require_executable: bool = True,
) -> Dict[str, Any]:
    payload = deepcopy(dict(request))
    problem_id = str(payload.get("problem", "four_level_one_pair"))
    spec = get_fermion_problem_spec(problem_id, require_executable=require_executable)
    payload["method"] = "fermion_pairing"
    payload["problem"] = spec.problem_id
    payload["parameters"] = normalize_fermion_parameters(
        spec.problem_id,
        payload.get("parameters") if isinstance(payload.get("parameters"), Mapping) else {},
        require_executable=require_executable,
    )
    payload["problem_contract"] = {
        "registry_version": FERMION_REGISTRY_VERSION,
        "schema_version": spec.schema_version,
        "problem_id": spec.problem_id,
        "support_status": spec.support_status,
        "execution_status": spec.execution_status,
    }
    return payload


def validate_registry_integrity() -> Dict[str, bool]:
    """Static self-check used by tests and the environment gate."""
    executable = list_fermion_problem_specs(include_unavailable=False)
    checks = {
        "registry_has_verified_benchmark": FOUR_LEVEL_ONE_PAIR.problem_id in FERMION_PROBLEM_REGISTRY,
        "registry_has_general_one_pair": GENERAL_ONE_PAIR.problem_id in FERMION_PROBLEM_REGISTRY,
        "multi_pair_is_distinct_problem": MULTI_PAIR_SENIORITY_ZERO.problem_id in FERMION_PROBLEM_REGISTRY,
        "general_fermion_is_distinct_problem": GENERAL_FERMIONIC_MODEL.problem_id in FERMION_PROBLEM_REGISTRY,
        "only_executable_routes_are_selectable": all(spec.selectable and spec.executable for spec in executable),
        "problem_ids_unique": len(FERMION_PROBLEM_REGISTRY) == len({spec.problem_id for spec in FERMION_PROBLEM_REGISTRY.values()}),
    }
    return checks
