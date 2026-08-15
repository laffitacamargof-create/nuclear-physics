"""Exact-ID semantic-authority registry and freeze-gate validation."""
from __future__ import annotations

from typing import Any, Dict

from .contracts import (
    SemanticAuthorityError,
    SemanticFactContract,
    SemanticOwnerContract,
    stable_sha256,
)


class SemanticAuthorityRegistry:
    def __init__(self) -> None:
        self._owners: Dict[str, SemanticOwnerContract] = {}
        self._facts: Dict[str, SemanticFactContract] = {}

    def register_owner(self, owner: SemanticOwnerContract) -> None:
        if owner.owner_id in self._owners:
            raise SemanticAuthorityError(
                "SEMANTIC_AUTHORITY_DUPLICATE_OWNER",
                f"Owner {owner.owner_id!r} is already registered.",
            )
        self._owners[owner.owner_id] = owner

    def register_fact(self, fact: SemanticFactContract) -> None:
        if fact.fact_id in self._facts:
            raise SemanticAuthorityError(
                "DUPLICATE_SEMANTIC_DERIVATION",
                f"Fact {fact.fact_id!r} has more than one authoritative declaration.",
            )
        self._facts[fact.fact_id] = fact

    def owner(self, owner_id: str) -> SemanticOwnerContract:
        try:
            return self._owners[str(owner_id)]
        except KeyError as exc:
            raise SemanticAuthorityError(
                "SEMANTIC_AUTHORITY_OWNER_MISSING",
                f"Unknown semantic owner {owner_id!r}.",
            ) from exc

    def fact(self, fact_id: str) -> SemanticFactContract:
        try:
            return self._facts[str(fact_id)]
        except KeyError as exc:
            raise SemanticAuthorityError(
                "SEMANTIC_AUTHORITY_FACT_MISSING",
                f"Unknown semantic fact {fact_id!r}.",
            ) from exc

    def validate(self) -> Dict[str, bool]:
        owner_ids = set(self._owners)
        fact_ids = set(self._facts)
        owners_exist = all(
            fact.authoritative_owner_id in owner_ids for fact in self._facts.values()
        )
        inputs_exist = all(
            set(fact.required_input_fact_ids).issubset(fact_ids)
            for fact in self._facts.values()
        )
        no_owner_forbidden = all(
            fact.authoritative_owner_id not in set(fact.forbidden_owner_ids)
            for fact in self._facts.values()
        )
        ui_not_scientific_owner = all(
            not (
                fact.authoritative_owner_id == "owner.ui"
                and fact.fact_id.startswith(("fact.scientific.", "fact.resource."))
            )
            for fact in self._facts.values()
        )
        family_not_authoritative = all(
            "model_family" not in fact.authoritative_owner_id
            for fact in self._facts.values()
        )
        return {
            "owners_present": bool(owner_ids),
            "facts_present": bool(fact_ids),
            "exactly_one_owner_per_fact": len(fact_ids) == len(self._facts),
            "all_fact_owners_registered": owners_exist,
            "all_derivation_inputs_registered": inputs_exist,
            "authoritative_owner_not_forbidden": no_owner_forbidden,
            "ui_is_read_only_for_scientific_and_resource_facts": ui_not_scientific_owner,
            "model_family_is_not_an_authoritative_owner": family_not_authoritative,
        }

    def to_dict(self) -> Dict[str, Any]:
        validation = self.validate()
        payload = {
            "schema_version": "qcol-semantic-authority-registry/1.0",
            "catalog_role": "governance_audit_machine_checkable_manifest",
            "runtime_dispatcher": False,
            "invariant": [
                "one_semantic_fact",
                "one_authoritative_owner",
                "explicit_derivation_inputs",
                "many_read_only_consumers",
                "zero_duplicate_derivations",
            ],
            "invariants": {
                "one_authoritative_owner_per_fact": validation["exactly_one_owner_per_fact"],
                "explicit_derivation_inputs": validation["all_derivation_inputs_registered"],
                "many_read_only_consumers": True,
                "zero_duplicate_derivations": validation["exactly_one_owner_per_fact"],
                "governance_only_not_runtime_dispatch": True,
            },
            "owners": [self._owners[key].to_dict() for key in sorted(self._owners)],
            "facts": [self._facts[key].to_dict() for key in sorted(self._facts)],
            "validation": validation,
            "silent_fallback_allowed": False,
            "runtime_selection_authority": None,
        }
        payload["catalog_fingerprint"] = stable_sha256(payload)
        return payload


SEMANTIC_AUTHORITY_REGISTRY = SemanticAuthorityRegistry()
