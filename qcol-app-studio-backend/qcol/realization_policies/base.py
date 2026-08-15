"""Dependency-light helpers for declarative mapping-realization contracts.

WP2 contracts are scientific declarations, not executable implementations.  The
public representation is strict JSON and contains only identifiers, versions,
capabilities, bounded numeric declarations, and provenance.  Python callables
remain in WP3 registries.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import StrEnum
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping


_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:+-]*$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9_.:-]*$")


class PolicyContractError(ValueError):
    """Raised when a declarative policy contract is structurally invalid."""


def require_text(label: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyContractError(f"{label} must be a non-empty string.")
    return value.strip()


def require_token(label: str, value: str) -> str:
    value = require_text(label, value)
    if not _TOKEN.fullmatch(value):
        raise PolicyContractError(
            f"{label} must be a transport-safe token; received {value!r}."
        )
    return value


def normalize_capabilities(values: tuple[str, ...] | list[str], *, label: str) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in values:
        value = require_text(label, str(raw))
        if not _CAPABILITY.fullmatch(value):
            raise PolicyContractError(
                f"{label} entries must be lower-case capability tokens; received {value!r}."
            )
        normalized.append(value)
    if len(set(normalized)) != len(normalized):
        raise PolicyContractError(f"{label} must not contain duplicates.")
    return tuple(normalized)


def _freeze_json(value: Any, *, path: str = "value") -> Any:
    """Freeze a strict-JSON value while rejecting callables and opaque objects."""
    if callable(value):
        raise PolicyContractError(
            f"{path} contains a Python callable. Public contracts may store only binding IDs."
        )
    if isinstance(value, StrEnum):
        return value.value
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PolicyContractError(f"{path} contains a non-finite float.")
        return float(value)
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            frozen[key_text] = _freeze_json(item, path=f"{path}.{key_text}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(
            _freeze_json(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if is_dataclass(value) and hasattr(value, "to_dict"):
        return _freeze_json(value.to_dict(), path=path)
    raise PolicyContractError(
        f"{path} contains unsupported type {type(value).__module__}.{type(value).__name__}; "
        "contracts must be strict JSON declarations."
    )


def freeze_json(value: Any, *, path: str = "value") -> Any:
    return _freeze_json(value, path=path)


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and hasattr(value, "to_dict"):
        return value.to_dict()
    return value


def json_contract_value(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value) and hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(key): json_contract_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_contract_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise PolicyContractError("A public contract contains a non-finite float.")
        return value
    if callable(value):
        raise PolicyContractError("A public contract contains a callable.")
    raise PolicyContractError(
        f"Public contract contains unsupported value type {type(value).__name__}."
    )


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        json_contract_value(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def contract_fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def contains_callable(value: Any) -> bool:
    if callable(value):
        return True
    if is_dataclass(value):
        return any(contains_callable(getattr(value, field.name)) for field in fields(value))
    if isinstance(value, Mapping):
        return any(contains_callable(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_callable(item) for item in value)
    return False


class DeclarativeContract:
    """Mixin that gives frozen dataclasses deterministic public views."""

    def to_dict(self) -> dict[str, Any]:
        if not is_dataclass(self):
            raise TypeError("DeclarativeContract must be mixed into a dataclass.")
        payload = {
            field.name: json_contract_value(getattr(self, field.name))
            for field in fields(self)
        }
        if contains_callable(self):
            raise PolicyContractError("Public contract contains a Python callable.")
        # Strict JSON round trip is part of the public-contract promise.
        return json.loads(json.dumps(payload, sort_keys=True, allow_nan=False))

    def fingerprint(self) -> str:
        return contract_fingerprint(self.to_dict())

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )


__all__ = [
    "PolicyContractError",
    "DeclarativeContract",
    "require_text",
    "require_token",
    "normalize_capabilities",
    "freeze_json",
    "thaw_json",
    "json_contract_value",
    "canonical_json",
    "contract_fingerprint",
    "contains_callable",
]
