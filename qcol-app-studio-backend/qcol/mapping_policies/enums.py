"""Shared mapping-realization vocabulary for QCOL.

WP1 introduces dependency-light, JSON-safe ``StrEnum`` classes used by every
current and future mapping policy.  These enums are declarations only: they do
not resolve compatibility, bind callables, or change any scientific runtime
behaviour.

Two distinctions are intentionally explicit:

* ``AnsatzSemanticClass.QUBIT_NATIVE`` is not equivalent to
  ``MAPPED_FERMIONIC_GENERATOR`` merely because a circuit preserves Hamming
  weight or particle number.
* ``SectorRepresentationKind.DIRECT_POPCOUNT`` is not a universal particle
  number rule.  A mapping such as Bravyi--Kitaev may require a non-local mapped
  operator or mapping-specific decoder.
"""
from __future__ import annotations

from enum import StrEnum


class MappingFamily(StrEnum):
    """Broad, implementation-independent mapping family."""

    JORDAN_WIGNER = "jordan_wigner"
    BRAVYI_KITAEV = "bravyi_kitaev"
    PARITY = "parity"
    PAIR = "pair"
    CUSTOM = "custom"


class MappingScope(StrEnum):
    """Physical/code-space scope in which a mapping claim is valid."""

    FULL_FERMIONIC_FOCK_SPACE = "full_fermionic_fock_space"
    RESTRICTED_PHYSICAL_SUBSPACE = "restricted_physical_subspace"
    SYMMETRY_REDUCED_SUBSPACE = "symmetry_reduced_subspace"
    TAPERED_SUBSPACE = "tapered_subspace"
    CUSTOM_CODE_SPACE = "custom_code_space"


class AlgebraScope(StrEnum):
    """Algebra whose action the policy promises to preserve."""

    CANONICAL_ANTICOMMUTATION_RELATIONS = (
        "canonical_anticommutation_relations"
    )
    QUASISPIN_PAIR_ALGEBRA = "quasispin_pair_algebra"
    ENCODED_SUBSPACE_OPERATOR_ALGEBRA = "encoded_subspace_operator_algebra"
    CUSTOM_DECLARED_ALGEBRA = "custom_declared_algebra"


class PolicyStatus(StrEnum):
    """Canonical lifecycle/support vocabulary for policy assets.

    The broad set intentionally covers the status strings already used by QCOL
    before migration.  WP2+ will constrain which statuses are valid for each
    contract type; WP1 only exports a stable common language.
    """

    REGISTERED = "registered"
    RECOGNIZED = "recognized"
    NOT_IMPLEMENTED = "not_implemented"
    PLANNED = "planned"
    FUTURE = "future"
    UNRESOLVED = "unresolved"
    RECOGNIZED_NOT_EXECUTABLE = "recognized_not_executable"
    EXPERIMENTAL = "experimental"
    EXECUTABLE = "executable"
    EXECUTION_READY = "execution_ready"
    VERIFIED = "verified"
    ACCEPTANCE_VERIFIED = "acceptance_verified"
    UNSUPPORTED = "unsupported"
    DEPRECATED = "deprecated"


class CheckStatus(StrEnum):
    """Outcome of one explicit compatibility or acceptance check."""

    PASS = "pass"
    REVIEW = "review"
    FAIL = "fail"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"


class Severity(StrEnum):
    """Operational/scientific severity attached to a check or failure."""

    INFO = "info"
    WARNING = "warning"
    REVIEW = "review"
    ERROR = "error"
    FATAL = "fatal"


class GateApplicability(StrEnum):
    """Whether an acceptance gate is required for a realization variant."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"


class AnsatzSemanticClass(StrEnum):
    """What scientific claim an ansatz implementation is allowed to make.

    ``MAPPED_FERMIONIC_GENERATOR``
        Starts from a fermionic generator, maps it with the selected mapping
        convention, and requires generator/circuit equivalence evidence.

    ``MAPPING_NATIVE_VERIFIED``
        Is defined directly in the encoded qubit representation but carries
        accepted equivalence evidence on a named mapping, order, and sector.

    ``QUBIT_NATIVE``
        Is a hardware/qubit circuit with no automatic fermionic-generator
        claim.  Particle-number or Hamming-weight preservation alone cannot
        promote it to either stronger class.
    """

    MAPPED_FERMIONIC_GENERATOR = "mapped_fermionic_generator"
    MAPPING_NATIVE_VERIFIED = "mapping_native_verified"
    QUBIT_NATIVE = "qubit_native"


class SectorRepresentationKind(StrEnum):
    """How one conserved quantity/sector is represented after mapping."""

    DIRECT_POPCOUNT = "direct_popcount"
    LOCAL_DIAGONAL_OPERATOR = "local_diagonal_operator"
    NONLOCAL_MAPPED_OPERATOR = "nonlocal_mapped_operator"
    CODE_SPACE_PROJECTOR = "code_space_projector"
    FIXED_BY_PHYSICAL_DOMAIN = "fixed_by_physical_domain"
    UNSUPPORTED = "unsupported"


class EvidenceFreshnessStatus(StrEnum):
    """Whether acceptance evidence still matches the exact resolved tuple."""

    CURRENT = "current"
    STALE = "stale"
    MISSING = "missing"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class DecisionStatus(StrEnum):
    """Final bounded decision emitted by a resolver, gate, or comparison."""

    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"
    INCONCLUSIVE = "inconclusive"
    DEFER = "defer"
    NOT_APPLICABLE = "not_applicable"


EXPORTED_ENUMS = (
    MappingFamily,
    MappingScope,
    AlgebraScope,
    PolicyStatus,
    CheckStatus,
    Severity,
    GateApplicability,
    AnsatzSemanticClass,
    SectorRepresentationKind,
    EvidenceFreshnessStatus,
    DecisionStatus,
)


__all__ = [item.__name__ for item in EXPORTED_ENUMS] + ["EXPORTED_ENUMS"]
