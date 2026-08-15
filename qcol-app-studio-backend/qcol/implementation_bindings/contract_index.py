"""Contract-ID → binding-ID index for WP3.

This module reads declarative WP2 contracts and extracts their implementation
requirements without loading any callable.  The separate binding registry then
resolves those exact IDs.  Scientific compatibility remains outside WP3.
"""
from __future__ import annotations

import hashlib
import json
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from qcol.acceptance import ToleranceProfile
from qcol.mapping_policies import MappingPolicyContract
from qcol.realization_policies import (
    AnsatzPolicyContract,
    EncodingContext,
    MeasurementPolicyContract,
    ModeOrderingContract,
    ReferencePolicyContract,
    SectorEncodingProfile,
    StatePreparationPolicyContract,
    VerificationPolicyContract,
)
from qcol.realization_policies.base import DeclarativeContract

from .contracts import BindingRequirement, ResolvedBindingPlan
from .enums import BindingKind
from .registry import ImplementationBindingRegistry


_SUPPORTED_CONTRACT_TYPES = (
    MappingPolicyContract,
    ModeOrderingContract,
    EncodingContext,
    SectorEncodingProfile,
    StatePreparationPolicyContract,
    AnsatzPolicyContract,
    MeasurementPolicyContract,
    ReferencePolicyContract,
    VerificationPolicyContract,
    ToleranceProfile,
)


def contract_identity(contract: DeclarativeContract) -> tuple[str, str]:
    if isinstance(contract, MappingPolicyContract):
        return contract.policy_id, type(contract).__name__
    if isinstance(contract, ModeOrderingContract):
        return contract.ordering_id, type(contract).__name__
    if isinstance(contract, EncodingContext):
        return contract.context_id, type(contract).__name__
    if isinstance(contract, SectorEncodingProfile):
        return contract.profile_id, type(contract).__name__
    if isinstance(
        contract,
        (
            StatePreparationPolicyContract,
            AnsatzPolicyContract,
            MeasurementPolicyContract,
            ReferencePolicyContract,
            VerificationPolicyContract,
        ),
    ):
        return contract.policy_id, type(contract).__name__
    if isinstance(contract, ToleranceProfile):
        return contract.profile_id, type(contract).__name__
    raise TypeError(
        f"Unsupported declarative contract type: {type(contract).__name__}."
    )


def _requirement(
    contract_id: str,
    contract_type: str,
    role: str,
    binding_id: str | None,
    kind: BindingKind,
    *,
    required: bool = True,
    expected_binding_version: str | None = "1.0.0",
    expected_convention_id: str | None = None,
) -> BindingRequirement | None:
    if binding_id is None:
        return None
    return BindingRequirement(
        contract_id=contract_id,
        contract_type=contract_type,
        role=role,
        binding_id=binding_id,
        binding_kind=kind,
        required=required,
        expected_binding_version=expected_binding_version,
        expected_convention_id=expected_convention_id,
    )


def binding_requirements_for_contract(
    contract: DeclarativeContract,
) -> tuple[BindingRequirement, ...]:
    """Extract versioned binding requirements without importing implementations."""

    contract_id, contract_type = contract_identity(contract)
    items: list[BindingRequirement | None] = []

    if isinstance(contract, MappingPolicyContract):
        convention = contract.convention_id
        items.extend(
            [
                _requirement(
                    contract_id,
                    contract_type,
                    "mapping.operator_transform",
                    contract.implementation_binding_id,
                    BindingKind.OPERATOR_TRANSFORM,
                    expected_convention_id=convention,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "mapping.basis_encoder",
                    contract.encoder_policy_id,
                    BindingKind.BASIS_ENCODER,
                    expected_convention_id=convention,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "mapping.basis_decoder",
                    contract.decoder_policy_id,
                    BindingKind.BASIS_DECODER,
                    required=contract.decoder_policy_id is not None,
                    expected_convention_id=convention,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "mapping.physical_subspace",
                    contract.physical_subspace_policy_id,
                    BindingKind.PHYSICAL_SUBSPACE,
                    expected_convention_id=convention,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "mapping.resource_assessor",
                    contract.resource_assessor_binding_id,
                    BindingKind.RESOURCE_ASSESSOR,
                    expected_convention_id=convention,
                ),
            ]
        )
        for profile in contract.sector_profiles:
            profile_id, profile_type = contract_identity(profile)
            items.extend(
                [
                    _requirement(
                        profile_id,
                        profile_type,
                        f"sector.{profile.quantity_id}.diagnostic",
                        profile.diagnostic_policy_id,
                        BindingKind.SECTOR_DIAGNOSTIC,
                    ),
                    _requirement(
                        profile_id,
                        profile_type,
                        f"sector.{profile.quantity_id}.projector",
                        profile.projector_policy_id,
                        BindingKind.SECTOR_PROJECTOR,
                        required=False,
                    ),
                    _requirement(
                        profile_id,
                        profile_type,
                        f"sector.{profile.quantity_id}.decoder",
                        profile.decoder_policy_id,
                        BindingKind.BASIS_DECODER,
                        required=False,
                    ),
                ]
            )

    elif isinstance(contract, SectorEncodingProfile):
        items.extend(
            [
                _requirement(
                    contract_id,
                    contract_type,
                    f"sector.{contract.quantity_id}.diagnostic",
                    contract.diagnostic_policy_id,
                    BindingKind.SECTOR_DIAGNOSTIC,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    f"sector.{contract.quantity_id}.projector",
                    contract.projector_policy_id,
                    BindingKind.SECTOR_PROJECTOR,
                    required=False,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    f"sector.{contract.quantity_id}.decoder",
                    contract.decoder_policy_id,
                    BindingKind.BASIS_DECODER,
                    required=False,
                ),
            ]
        )

    elif isinstance(contract, StatePreparationPolicyContract):
        items.append(
            _requirement(
                contract_id,
                contract_type,
                "state_preparation.builder",
                contract.implementation_binding_id,
                BindingKind.STATE_PREPARATION,
            )
        )

    elif isinstance(contract, AnsatzPolicyContract):
        items.extend(
            [
                _requirement(
                    contract_id,
                    contract_type,
                    "ansatz.factory",
                    contract.implementation_binding_id,
                    BindingKind.ANSATZ_FACTORY,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "ansatz.parameterization",
                    contract.parameterization_policy_id,
                    BindingKind.PARAMETERIZATION,
                ),
            ]
        )

    elif isinstance(contract, MeasurementPolicyContract):
        items.extend(
            [
                _requirement(
                    contract_id,
                    contract_type,
                    "measurement.builder",
                    contract.implementation_binding_id,
                    BindingKind.MEASUREMENT_BUILDER,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "measurement.grouping",
                    contract.grouping_policy_id,
                    BindingKind.GROUPING,
                ),
                _requirement(
                    contract_id,
                    contract_type,
                    "measurement.reconstruction",
                    contract.reconstruction_policy_id,
                    BindingKind.RECONSTRUCTION,
                ),
            ]
        )

    elif isinstance(contract, ReferencePolicyContract):
        items.append(
            _requirement(
                contract_id,
                contract_type,
                "reference.solver",
                contract.independent_solver_binding_id,
                BindingKind.REFERENCE_SOLVER,
            )
        )

    elif isinstance(contract, VerificationPolicyContract):
        items.append(
            _requirement(
                contract_id,
                contract_type,
                "verification.handler",
                contract.implementation_binding_id,
                BindingKind.VERIFICATION,
            )
        )

    # ModeOrderingContract, EncodingContext, and ToleranceProfile are pure
    # declarative values and intentionally have no executable binding.
    return tuple(item for item in items if item is not None)


class DeclarativePolicyContractRegistry:
    """Dependency-light registry of declarative contracts and their binding edges."""

    def __init__(self, *, registry_id: str, registry_version: str) -> None:
        self.registry_id = str(registry_id)
        self.registry_version = str(registry_version)
        self._contracts: dict[str, DeclarativeContract] = {}

    def register(self, contract: DeclarativeContract, *, replace: bool = False) -> None:
        if not isinstance(contract, _SUPPORTED_CONTRACT_TYPES):
            raise TypeError(
                f"Unsupported declarative contract type: {type(contract).__name__}."
            )
        contract_id, _ = contract_identity(contract)
        if contract_id in self._contracts and not replace:
            raise ValueError(f"Contract {contract_id!r} is already registered.")
        self._contracts[contract_id] = contract

    def get(self, contract_id: str) -> DeclarativeContract:
        try:
            return self._contracts[str(contract_id)]
        except KeyError as exc:
            raise KeyError(f"Unknown declarative contract {contract_id!r}.") from exc

    def requirements(self, contract_id: str) -> tuple[BindingRequirement, ...]:
        return binding_requirements_for_contract(self.get(contract_id))

    def list_contracts(self) -> tuple[DeclarativeContract, ...]:
        return tuple(self._contracts[key] for key in sorted(self._contracts))

    def public_catalog(self) -> dict[str, Any]:
        rows = []
        for contract in self.list_contracts():
            contract_id, contract_type = contract_identity(contract)
            rows.append(
                {
                    "contract_id": contract_id,
                    "contract_type": contract_type,
                    "contract_fingerprint": contract.fingerprint(),
                    "binding_requirements": [
                        item.to_dict()
                        for item in binding_requirements_for_contract(contract)
                    ],
                    "callable_payload_withheld": True,
                }
            )
        return {
            "schema_version": "qcol-declarative-contract-binding-index/1.0",
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "count": len(rows),
            "contracts": rows,
            "callable_payload_withheld": True,
        }

    @property
    def contracts(self) -> Mapping[str, DeclarativeContract]:
        return MappingProxyType(dict(self._contracts))


def resolve_contracts(
    contract_registry: DeclarativePolicyContractRegistry,
    binding_registry: ImplementationBindingRegistry,
    contract_ids: Iterable[str],
    *,
    plan_label: str,
) -> ResolvedBindingPlan:
    ordered_ids = tuple(dict.fromkeys(str(item) for item in contract_ids))
    resolutions = []
    seen: set[tuple[str, str, str]] = set()
    for contract_id in ordered_ids:
        for requirement in contract_registry.requirements(contract_id):
            key = (
                requirement.contract_id,
                requirement.role,
                requirement.binding_id,
            )
            if key in seen:
                continue
            seen.add(key)
            resolutions.append(binding_registry.resolve(requirement))

    public_seed = {
        "plan_label": str(plan_label),
        "contract_ids": list(ordered_ids),
        "requirements": [
            item.report.requirement.to_dict() for item in resolutions
        ],
    }
    plan_id = "binding-plan-" + hashlib.sha256(
        json.dumps(
            public_seed,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return ResolvedBindingPlan(
        plan_id=plan_id,
        contract_ids=ordered_ids,
        implementations=tuple(resolutions),
        scientific_behavior_change=False,
        live_policy_migration_performed=False,
    )


__all__ = [
    "contract_identity",
    "binding_requirements_for_contract",
    "DeclarativePolicyContractRegistry",
    "resolve_contracts",
]
