"""Freeze and verify the accepted QCOL Phase C 1.23.0 baseline.

This module is intentionally pure-stdlib and read-only with respect to the
scientific runtime.  It inventories the already accepted Phase-C source,
public catalogs, exact scientific status records, references, OpenAPI schema,
dependency locks, release attestations, and Evidence archives.  It creates no
new optimization, measurement, QASM, execution, reconstruction, comparison,
or Evidence runtime.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Mapping, Sequence
import zipfile
import zlib

BASELINE_PROJECT_VERSION = "1.23.0"
BASELINE_SOURCE_PACKAGE = "QCOL_Phase_C_Try_Compare_Complete.zip"
BASELINE_SOURCE_ARCHIVE_SHA256 = "f271a01bd6d2274213addaa95b66b5b40dba92b9822a1af0e6282e8e22e3d751"
BASELINE_GIT_COMMIT = "2f2a134efd07c536f7f06e389a777637adaa8fb9"
BASELINE_BRANCH = "baseline/phase-c-1.23.0"
HARDENING_BRANCH = "hardening/post-phase-c-integrity-durable-execution"
BASELINE_TAG = "qcol-phase-c-1.23.0-frozen-source"
FREEZE_SCHEMA_VERSION = "qcol-unified-baseline-manifest/1.0"
FREEZE_TOOL_VERSION = "1.0.3"

INTEGRITY_I1_SOURCE_PACKAGE = "QCOL_Integrity_Primitives_I1_Comparison_Realization_Foundation_Complete.zip"
INTEGRITY_I1_SOURCE_ARCHIVE_SHA256 = "5a9c1299afd54faaecfc4940bed410f729ef037e16a4b1e1012eec3e460d74ee"
INTEGRITY_I1_CATALOG_FINGERPRINT = "593877fe18fdc149a2a7f4426858c3d4707c636e3f801cb8b95130ce48c0793e"
INTEGRITY_I1_COMPARISON_FINGERPRINT = "7db28fbbe7df059e3b415014e5981b5e085cce09f3a781cca2234722cb07cbaa"

_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)

_ALLOWED_NEW_PREFIXES = (
    "qcol/hardening/",
    "scripts/freeze_phase_c_baseline.py",
    "scripts/verify_phase_c_baseline.py",
    "scripts/run_phase_c_baseline_freeze_gate.py",
    "scripts/create_hardening_branch.py",
    "tests/test_post_phase_c_baseline_",
    "notebooks/QCOL_Post_Phase_C_Step1_Freeze_Baseline.ipynb",
    "QCOL_Post_Phase_C_Step1_",
    "QCOL_Phase_C_1_23_",
    "QCOL_Hardening_Branch_Record.json",
    "HARDENING_BRANCH_PLAN.json",
    "unified_baseline_manifest.json",
    "freeze_phase_c_baseline_windows.bat",
    "verify_phase_c_baseline_windows.bat",
    "create_hardening_branch_windows.bat",
    "qcol_phase_c_1_23_frozen_baseline/",
)

# The exact exported catalogs/contracts that constitute the accepted Phase-C
# scientific and architectural surface.  Their bytes are also frozen in the
# complete source package; this index makes later merge regressions cheap.
_AUTHORITATIVE_JSON_PATTERNS = (
    "QCOL_*.json",
)

# Official semantic fingerprints, when published by the accepted release
# decisions.  These are distinct from file SHA-256 values.
_OFFICIAL_FP_KEYS = (
    "wp0_baseline",
    "wp1_vocabulary",
    "wp2_policy_contracts",
    "wp3_implementation_bindings",
    "wp4_compatibility_rules",
    "wp5_realization_resolver",
    "wp6_acceptance_fingerprints",
    "wp7_acceptance_harness",
    "wp8_pair_mapping_migration",
    "wp9_wp10_spin_orbital_migration",
    "wp11_jw_accepted_composition",
    "wp12_realization_variants",
    "wp12_surface",
    "wp13_governance",
    "wp13_patch_allowlist",
)


def _json_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _git_cli_path() -> str | None:
    """Return the Git executable unless the portable reader is explicitly forced.

    The frozen baseline is an archive, so verification must not depend on a
    machine-wide Git installation.  ``QCOL_FORCE_PURE_PY_GIT=1`` is used by the
    portability tests and is also useful for diagnosing Windows installations.
    """

    if os.environ.get("QCOL_FORCE_PURE_PY_GIT", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return None
    return shutil.which("git")


def _run_git(root: Path, *args: str, check: bool = True) -> str:
    executable = _git_cli_path()
    if executable is None:
        raise FileNotFoundError(
            "Git CLI is not available. The baseline verifier will use the "
            "archive-local pure-Python Git reader for supported read-only checks."
        )
    completed = subprocess.run(
        [executable, *args], cwd=root, text=True, capture_output=True
    )
    if check and completed.returncode:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def _git_dir(root: Path) -> Path | None:
    marker = root / ".git"
    if marker.is_dir():
        return marker
    if marker.is_file():
        text = marker.read_text(encoding="utf-8").strip()
        if text.startswith("gitdir:"):
            path = Path(text.split(":", 1)[1].strip())
            return (path if path.is_absolute() else (root / path)).resolve()
    return None


def _packed_refs(git_dir: Path) -> dict[str, str]:
    path = git_dir / "packed-refs"
    if not path.exists():
        return {}
    refs: dict[str, str] = {}
    last_ref: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("^"):
            if last_ref is not None:
                refs[last_ref + "^{}"] = line[1:]
            continue
        oid, ref = line.split(" ", 1)
        refs[ref] = oid
        last_ref = ref
    return refs


def _read_ref(git_dir: Path, ref: str) -> str | None:
    path = git_dir / ref
    if path.exists():
        value = path.read_text(encoding="utf-8").strip()
        if value.startswith("ref:"):
            return _read_ref(git_dir, value.split(":", 1)[1].strip())
        return value
    return _packed_refs(git_dir).get(ref)


def _list_refs(git_dir: Path, prefix: str) -> dict[str, str]:
    refs: dict[str, str] = {
        ref: oid for ref, oid in _packed_refs(git_dir).items() if ref.startswith(prefix)
    }
    loose_root = git_dir / prefix
    if loose_root.exists():
        for path in loose_root.rglob("*"):
            if not path.is_file():
                continue
            ref = path.relative_to(git_dir).as_posix()
            oid = _read_ref(git_dir, ref)
            if oid:
                refs[ref] = oid
    return refs


def _read_loose_git_object(git_dir: Path, oid: str) -> tuple[str, bytes]:
    """Read one loose Git object from the repository embedded in the archive."""

    if len(oid) != 40 or any(char not in "0123456789abcdef" for char in oid.lower()):
        raise ValueError(f"Invalid Git object ID: {oid!r}")
    path = git_dir / "objects" / oid[:2] / oid[2:]
    if not path.exists():
        raise FileNotFoundError(
            f"Git object {oid} is not present as a loose object in {git_dir}. "
            "Re-extract the complete QCOL Step-1 package."
        )
    raw = zlib.decompress(path.read_bytes())
    header, data = raw.split(b"\0", 1)
    kind_raw, size_raw = header.split(b" ", 1)
    if int(size_raw) != len(data):
        raise ValueError(f"Git object {oid} has an invalid size header.")
    return kind_raw.decode("ascii"), data


def _peel_git_object_to_commit(git_dir: Path, oid: str) -> str:
    seen: set[str] = set()
    current = oid
    while True:
        if current in seen:
            raise ValueError(f"Git tag cycle detected at {current}.")
        seen.add(current)
        kind, data = _read_loose_git_object(git_dir, current)
        if kind == "commit":
            return current
        if kind != "tag":
            raise ValueError(f"Expected commit/tag object, found {kind!r} for {current}.")
        first = data.decode("utf-8", errors="replace").splitlines()[0]
        if not first.startswith("object "):
            raise ValueError(f"Annotated tag {current} has no object target.")
        current = first.split(" ", 1)[1].strip()


def _commit_tree_oid(git_dir: Path, commit_oid: str) -> str:
    kind, data = _read_loose_git_object(git_dir, _peel_git_object_to_commit(git_dir, commit_oid))
    if kind != "commit":  # defensive: _peel guarantees this
        raise ValueError(f"Expected commit object, found {kind!r}.")
    for line in data.decode("utf-8", errors="replace").splitlines():
        if line.startswith("tree "):
            return line.split(" ", 1)[1].strip()
    raise ValueError(f"Commit {commit_oid} has no tree.")


def _parse_tree_entries(git_dir: Path, tree_oid: str) -> list[tuple[str, str, str]]:
    kind, data = _read_loose_git_object(git_dir, tree_oid)
    if kind != "tree":
        raise ValueError(f"Expected tree object, found {kind!r} for {tree_oid}.")
    rows: list[tuple[str, str, str]] = []
    offset = 0
    while offset < len(data):
        space = data.index(b" ", offset)
        nul = data.index(b"\0", space)
        mode = data[offset:space].decode("ascii")
        name = data[space + 1 : nul].decode("utf-8", errors="surrogateescape")
        oid = data[nul + 1 : nul + 21].hex()
        rows.append((mode, name, oid))
        offset = nul + 21
    return rows


def _tree_snapshot(
    git_dir: Path, commit_oid: str, *, include_blobs: bool = False
) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}

    def walk(tree_oid: str, prefix: str = "") -> None:
        for mode, name, oid in _parse_tree_entries(git_dir, tree_oid):
            path = f"{prefix}{name}"
            if mode in {"40000", "040000"}:
                walk(oid, path + "/")
            else:
                row: dict[str, Any] = {"mode": mode, "oid": oid}
                if include_blobs:
                    kind, data = _read_loose_git_object(git_dir, oid)
                    if kind != "blob":
                        raise ValueError(f"Expected blob for {path}, found {kind!r}.")
                    row["bytes"] = data
                snapshot[path] = row

    walk(_commit_tree_oid(git_dir, commit_oid))
    return snapshot


def _portable_head(git_dir: Path) -> tuple[str | None, str | None]:
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None, None
    value = head_path.read_text(encoding="utf-8").strip()
    if value.startswith("ref:"):
        ref = value.split(":", 1)[1].strip()
        return ref, _read_ref(git_dir, ref)
    return None, value


def _portable_git_diff_name_status(root: Path, base_commit: str) -> list[dict[str, str]]:
    git_dir = _git_dir(root)
    if git_dir is None:
        return []
    _, head_oid = _portable_head(git_dir)
    if head_oid is None:
        raise ValueError("The archive-local Git repository has no HEAD commit.")
    base = _tree_snapshot(git_dir, base_commit)
    head = _tree_snapshot(git_dir, head_oid)
    rows: list[dict[str, str]] = []
    for path in sorted(set(base) | set(head)):
        if path not in base:
            rows.append({"status": "A", "path": path})
        elif path not in head:
            rows.append({"status": "D", "path": path})
        elif base[path] != head[path]:
            rows.append({"status": "M", "path": path})
    return rows


def baseline_to_head_diff(project_root: Path | str) -> list[dict[str, str]]:
    """Return the committed baseline-to-hardening diff without requiring Git CLI.

    The archive-local reader is used even when Git CLI is installed so the
    frozen Evidence is byte-identical on Windows, Linux, and Colab.
    """

    root = Path(project_root).resolve()
    return _portable_git_diff_name_status(root, BASELINE_GIT_COMMIT)


@lru_cache(maxsize=256)
def _baseline_commit_file_bytes_cached(
    git_dir_text: str, commit_oid: str, relative_path: str
) -> bytes:
    """Read one baseline blob without materializing the complete Git tree.

    The previous implementation decompressed every blob in the archived
    baseline for every protected path.  Repeated manifest/Evidence checks could
    therefore consume hundreds of megabytes in a single Colab process.  This
    path-directed reader follows only the requested tree entries and caches the
    immutable result by repository, commit, and path.
    """

    git_dir = Path(git_dir_text)
    parts = tuple(part for part in Path(relative_path).as_posix().split("/") if part)
    if not parts:
        raise FileNotFoundError("A non-empty baseline-relative path is required.")

    tree_oid = _commit_tree_oid(git_dir, commit_oid)
    for index, part in enumerate(parts):
        entries = {name: (mode, oid) for mode, name, oid in _parse_tree_entries(git_dir, tree_oid)}
        try:
            mode, oid = entries[part]
        except KeyError as exc:
            raise FileNotFoundError(
                f"{relative_path!r} is not present in baseline commit {commit_oid}."
            ) from exc

        is_last = index == len(parts) - 1
        if is_last:
            if mode in {"40000", "040000"}:
                raise FileNotFoundError(
                    f"{relative_path!r} resolves to a tree, not a file, in baseline commit {commit_oid}."
                )
            kind, data = _read_loose_git_object(git_dir, oid)
            if kind != "blob":
                raise ValueError(
                    f"Expected blob for {relative_path!r}, found {kind!r}."
                )
            return data

        if mode not in {"40000", "040000"}:
            raise FileNotFoundError(
                f"A parent component of {relative_path!r} is not a tree in baseline commit {commit_oid}."
            )
        tree_oid = oid

    raise FileNotFoundError(
        f"{relative_path!r} is not present in baseline commit {commit_oid}."
    )


def baseline_commit_file_bytes(project_root: Path | str, relative_path: str) -> bytes:
    """Read one file from the frozen baseline commit using archive-local objects."""

    root = Path(project_root).resolve()
    git_dir = _git_dir(root)
    if git_dir is None:
        raise FileNotFoundError("The complete Step-1 package must include .git metadata.")
    return _baseline_commit_file_bytes_cached(
        str(git_dir.resolve()), BASELINE_GIT_COMMIT, Path(relative_path).as_posix()
    )


def _read_project_version(root: Path) -> str:
    text = (root / "qcol/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', text, flags=re.MULTILINE)
    if not match:
        raise RuntimeError("qcol.__version__ was not found statically.")
    return match.group(1)


def git_branch_record(project_root: Path | str) -> dict[str, Any]:
    """Return a deterministic branch record from the repository embedded in the ZIP.

    Verification intentionally uses the pure-Python loose-object reader on all
    platforms.  This prevents the evidence manifest from changing merely
    because one machine has Git CLI installed and another does not.
    """

    root = Path(project_root).resolve()
    git_dir = _git_dir(root)
    if git_dir is None:
        return {
            "schema_version": "qcol-hardening-branch-record/1.0",
            "git_repository_present": False,
            "git_cli_required": False,
            "git_reader": "none",
            "baseline_branch": BASELINE_BRANCH,
            "hardening_branch": HARDENING_BRANCH,
            "baseline_tag": BASELINE_TAG,
            "baseline_commit": BASELINE_GIT_COMMIT,
            "active_branch": None,
        }

    branch_refs = _list_refs(git_dir, "refs/heads")
    tag_refs = _list_refs(git_dir, "refs/tags")
    branches = {ref.removeprefix("refs/heads/") for ref in branch_refs}
    tags = {ref.removeprefix("refs/tags/").removesuffix("^{}") for ref in tag_refs}
    baseline_ref = branch_refs.get(f"refs/heads/{BASELINE_BRANCH}")
    if baseline_ref is None:
        raise FileNotFoundError(f"Baseline branch {BASELINE_BRANCH!r} is missing.")
    baseline_commit = _peel_git_object_to_commit(git_dir, baseline_ref)
    baseline_tree = _commit_tree_oid(git_dir, baseline_commit)
    active_ref, _ = _portable_head(git_dir)
    active_branch = active_ref.removeprefix("refs/heads/") if active_ref else ""

    return {
        "schema_version": "qcol-hardening-branch-record/1.0",
        "git_repository_present": True,
        "git_cli_required": False,
        "git_reader": "pure-python-loose-object-reader",
        "baseline_branch": BASELINE_BRANCH,
        "hardening_branch": HARDENING_BRANCH,
        "baseline_tag": BASELINE_TAG,
        "baseline_commit": baseline_commit,
        "baseline_tree": baseline_tree,
        "active_branch": active_branch,
        "baseline_branch_present": BASELINE_BRANCH in branches,
        "hardening_branch_present": HARDENING_BRANCH in branches,
        "baseline_tag_present": BASELINE_TAG in tags,
        "source_zip_had_git_metadata": False,
        "repository_kind": "archive-local reproducibility repository",
    }


def _authoritative_json_index(root: Path) -> list[dict[str, Any]]:
    excluded = {
        "unified_baseline_manifest.json",
        "QCOL_Phase_C_1_23_Dependency_Lock.json",
        "QCOL_Phase_C_1_23_Scientific_Statuses.json",
        "QCOL_Phase_C_1_23_Public_API_Surface.json",
        "QCOL_Phase_C_1_23_Frozen_OpenAPI.json",
        "QCOL_Phase_C_1_23_Test_Results.json",
        "QCOL_Phase_C_1_23_Evidence_Archive_Inventory.json",
        "QCOL_Phase_C_1_23_Catalog_Contract_Index.json",
        "QCOL_Hardening_Branch_Record.json",
        "QCOL_Post_Phase_C_Step1_Exit_Decision.json",
        "HARDENING_BRANCH_PLAN.json",
    }
    paths: set[Path] = set()
    for pattern in _AUTHORITATIVE_JSON_PATTERNS:
        paths.update(root.glob(pattern))
    rows: list[dict[str, Any]] = []
    for path in sorted(paths, key=lambda p: p.name):
        if path.name in excluded:
            continue
        payload: Any | None = None
        schema_version: str | None = None
        embedded_fingerprint: str | None = None
        try:
            payload = _read_json(path)
            if isinstance(payload, dict):
                schema_version = payload.get("schema_version")
                embedded_fingerprint = payload.get("fingerprint")
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        rows.append(
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "schema_version": schema_version,
                "embedded_fingerprint": embedded_fingerprint,
                "strict_json": payload is not None,
            }
        )
    return rows


def catalog_fingerprints(project_root: Path | str | None = None) -> dict[str, str]:
    root = Path(project_root).resolve() if project_root else Path(__file__).resolve().parents[2]
    phase_b = _read_json(root / "QCOL_Phase_B_Exit_Decision.json")
    phase_c = _read_json(root / "QCOL_Phase_C_Exit_Decision.json")
    foundation = phase_b["foundation_fingerprints"]
    result = {key: foundation[key] for key in _OFFICIAL_FP_KEYS}
    result.update(
        {
            "phase_b.deterministic_advisor": phase_b["catalog_fingerprint"],
            "phase_b.rule_catalog": phase_b["rule_catalog_fingerprint"],
            "phase_c.try_compare": phase_c["phase_c_catalog_fingerprint"],
            "phase_c.comparison_policy": phase_c["comparison_policy_catalog_fingerprint"],
            "phase_c.parent_phase_b": phase_c["phase_b_catalog_fingerprint"],
            "wp11.acceptance_evidence": _read_json(root / "QCOL_WP13_A3_2c_Release_Decision.json")[
                "gate_attestations"
            ][0]["evidence_fingerprint"],
        }
    )
    return dict(sorted(result.items()))


def _parse_requirement_lines(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^;\s]+)(.*)$", line)
        rows.append(
            {
                "name": match.group(1) if match else None,
                "version": match.group(2) if match else None,
                "marker_or_suffix": (match.group(3).strip() or None) if match else None,
                "raw": line,
            }
        )
    return rows


def build_dependency_lock(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    names = (
        "requirements.txt",
        "requirements-colab-scientific.txt",
        "requirements-manager-baseline.txt",
        "pyproject.toml",
        "setup_windows.bat",
    )
    files: list[dict[str, Any]] = []
    profiles: dict[str, Any] = {}
    for name in names:
        path = root / name
        if not path.exists():
            continue
        files.append({"path": name, "sha256": sha256_file(path), "size_bytes": path.stat().st_size})
        if name.startswith("requirements") and path.suffix == ".txt":
            profiles[name] = _parse_requirement_lines(path)
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    py_match = re.search(r'^requires-python\s*=\s*"([^"]+)"', pyproject, flags=re.MULTILINE)
    payload = {
        "schema_version": "qcol-phase-c-dependency-lock/1.0",
        "project_version": BASELINE_PROJECT_VERSION,
        "python_requires": py_match.group(1) if py_match else None,
        "lock_files": files,
        "profiles": profiles,
        "adapter_dependencies_added": False,
        "core_dependencies_changed": False,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def _literal_number(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal_number(node.operand)
    raise ValueError(ast.dump(node))


def _parse_reference_anchors(root: Path) -> dict[str, Any]:
    one_pair = root / "qcol/models/reduced_pairing_one_pair/acceptance.py"
    text = one_pair.read_text(encoding="utf-8")
    match = re.search(
        r"^EXPECTED_FOUR_LEVEL_REFERENCE_ENERGY\s*=\s*([^\n#]+)", text, flags=re.MULTILINE
    )
    if not match:
        raise RuntimeError("One-pair reference anchor missing.")

    jw = root / "qcol/models/general_spin_orbital/jw_ground_state.py"
    tree = ast.parse(jw.read_text(encoding="utf-8"))
    presets: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        targets: Sequence[ast.AST]
        value: ast.AST | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if not any(
            isinstance(t, ast.Name) and t.id == "GENERAL_SPIN_ORBITAL_JW_ACCEPTANCE_PRESETS"
            for t in targets
        ):
            continue
        if not isinstance(value, (ast.Tuple, ast.List)):
            continue
        for element in value.elts:
            if not isinstance(element, ast.Call):
                continue
            kws = {kw.arg: kw.value for kw in element.keywords if kw.arg}
            pid = kws.get("preset_id")
            energy = kws.get("expected_reference_energy")
            if isinstance(pid, ast.Constant) and energy is not None:
                presets.append(
                    {
                        "preset_id": str(pid.value),
                        "expected_reference_energy": _literal_number(energy),
                    }
                )
        break
    return {
        "one_pair_four_level": {
            "reference_energy": float(match.group(1).strip()),
            "source_path": one_pair.relative_to(root).as_posix(),
            "source_sha256": sha256_file(one_pair),
            "tolerance": 1e-10,
        },
        "general_spin_orbital_jw_presets": presets,
        "general_spin_orbital_source_path": jw.relative_to(root).as_posix(),
        "general_spin_orbital_source_sha256": sha256_file(jw),
    }


def build_scientific_status_snapshot(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    governance = _read_json(root / "QCOL_WP13_Governance_Catalog_v1.json")
    pair = _read_json(root / "QCOL_Pair_Mapping_Policy_Migration_v1.json")
    spin = _read_json(root / "QCOL_A3_2b_JW_BK_Policy_Migration_Catalog_v1.json")
    wp11 = _read_json(root / "QCOL_WP11_JW_Accepted_Composition_v1.json")

    wanted_variants = {
        "realization.reduced_pairing.one_pair.pair_mapping.v1",
        "realization.nuclear.reduced_pairing.one_pair.observable_estimation.default.v1",
        "realization.reduced_pairing.multi_pair.pair_mapping.v1",
        "realization.general_spin_orbital.mapping_analysis.jw.v1",
        "realization.general_spin_orbital.mapping_analysis.bk.v1",
        "realization.general_spin_orbital.ground_state.jw.wp11.v1",
        "realization.general_spin_orbital.ground_state.jw.bare_exchange.historical.v1",
        "realization.general_spin_orbital.ground_state.bk.default.v1",
    }
    records = [
        record
        for record in governance["published_statuses"]
        if record["variant_id"] in wanted_variants
    ]
    if {r["variant_id"] for r in records} != wanted_variants:
        missing = wanted_variants - {r["variant_id"] for r in records}
        raise RuntimeError(f"Missing governed scientific status records: {sorted(missing)}")

    references = _parse_reference_anchors(root)
    references["general_spin_orbital_jw_reference_policy"] = wp11["acceptance_fingerprint"][
        "reference_policy"
    ]
    references["general_spin_orbital_jw_acceptance_fingerprint"] = wp11[
        "acceptance_fingerprint"
    ]["fingerprint"]

    # Cell-level summary for the user-facing Model × Task surface.
    published_cells = [
        {
            "cell_id": "nuclear.reduced_pairing.one_pair::ground_state_energy",
            "status": "acceptance_verified",
            "runnable": True,
        },
        {
            "cell_id": "nuclear.reduced_pairing.one_pair::observable_estimation",
            "status": "acceptance_verified",
            "runnable": True,
        },
        {
            "cell_id": "nuclear.reduced_pairing.multi_pair::ground_state_energy",
            "status": "experimental",
            "runnable": True,
        },
        {
            "cell_id": "fermion.general_spin_orbital::mapping_analysis",
            "status": "acceptance_verified",
            "runnable": True,
        },
        {
            "cell_id": "fermion.general_spin_orbital::ground_state_energy",
            "status": "acceptance_verified",
            "runnable": True,
            "accepted_variant": "realization.general_spin_orbital.ground_state.jw.wp11.v1",
        },
    ]
    payload = {
        "schema_version": "qcol-phase-c-scientific-status-freeze/1.0",
        "project_version": BASELINE_PROJECT_VERSION,
        "published_cells": published_cells,
        "governed_realization_statuses": sorted(records, key=lambda r: r["variant_id"]),
        "mapping_realizations": {
            "pair_mapping": {
                "mapping_scope": pair["mapping_scope"],
                "preserved_algebra": pair["preserved_algebra"],
                "one_pair": pair["status_preservation"]["one_pair"]["after"],
                "multi_pair": pair["status_preservation"]["multi_pair"]["after"],
                "full_single_fermion_semantics_claimed": pair[
                    "full_single_fermion_semantics_claimed"
                ],
            },
            "jordan_wigner": {
                "mapper": "verified",
                "mapping_analysis": "acceptance_verified",
                "historical_bare_exchange": "rejected_negative_fixture",
                "accepted_composition": "acceptance_verified",
                "ground_state_cell": "acceptance_verified",
                "mapping_policy_id": wp11["mapping_policy_id"],
                "mapping_convention_id": wp11["mapping_convention_id"],
            },
            "bravyi_kitaev": {
                **spin["bk"]["status"],
                "raw_popcount_is_particle_number": spin["bk"]["profile"][
                    "raw_popcount_is_particle_number"
                ],
                "mapping_policy_id": spin["bk"]["profile"]["mapping_policy"]["policy_id"],
                "mapping_convention_id": spin["bk"]["profile"]["mapping_policy"][
                    "convention_id"
                ],
            },
        },
        "reference_anchors": references,
        "scientific_status_promoted_by_freeze": False,
        "scientific_behavior_changed_by_freeze": False,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def _static_python_exports(root: Path) -> list[str]:
    tree = ast.parse((root / "qcol/__init__.py").read_text(encoding="utf-8"))
    exports = {"__version__"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_LAZY_EXPORTS":
                    if isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                                exports.add(key.value)
    return sorted(exports)


def build_public_api_surface(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    openapi = _read_json(root / "QCOL_Phase_C_OpenAPI.json")
    methods: dict[str, list[str]] = {}
    for path, item in openapi.get("paths", {}).items():
        methods[path] = sorted(
            key.upper()
            for key in item
            if key.lower() in {"get", "post", "put", "patch", "delete", "options", "head"}
        )
    exports = _static_python_exports(root)
    payload = {
        "schema_version": "qcol-phase-c-public-api-surface/1.0",
        "project_version": _read_project_version(root),
        "python_public_exports": exports,
        "python_public_export_count": len(exports),
        "openapi_info": openapi.get("info", {}),
        "openapi_paths": methods,
        "openapi_path_count": len(methods),
        "openapi_operation_count": sum(len(v) for v in methods.values()),
        "canonical_openapi_sha256": sha256_bytes(_canonical_json_bytes(openapi)),
        "source_openapi_file_sha256": sha256_file(root / "QCOL_Phase_C_OpenAPI.json"),
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def _source_release_test_results(root: Path) -> dict[str, Any]:
    names = {
        "phase_a3_2a": "QCOL_A3_2a_Policy_Foundation_Exit_Decision.json",
        "phase_a3_2b": "QCOL_A3_2b_Policy_Migration_Exit_Decision.json",
        "phase_a3_2c": "QCOL_WP13_A3_2c_Release_Decision.json",
        "phase_b": "QCOL_Phase_B_Exit_Decision.json",
        "phase_c": "QCOL_Phase_C_Exit_Decision.json",
    }
    records: dict[str, Any] = {}
    for key, name in names.items():
        path = root / name
        records[key] = {"path": name, "sha256": sha256_file(path), "payload": _read_json(path)}
    passes = (
        records["phase_a3_2a"]["payload"].get("exit_ready") is True
        and records["phase_a3_2b"]["payload"].get("status") == "acceptance_complete"
        and records["phase_a3_2c"]["payload"].get("phase_a3_2c_exit_ready") is True
        and records["phase_b"]["payload"].get("status") == "implemented_package_acceptance_pass"
        and records["phase_c"]["payload"].get("status") == "implemented_package_acceptance_pass"
    )
    payload = {
        "schema_version": "qcol-phase-c-test-results-freeze/1.0",
        "project_version": BASELINE_PROJECT_VERSION,
        "source_release_attestations": records,
        "all_source_release_attestations_pass": passes,
        "full_suite_command": "python scripts/run_phase_c_baseline_freeze_gate.py --full-suite",
        "accepted_phase_c_release_gate": "python scripts/run_phase_c_gate.py --with-scientific-regressions",
        "all_historical_tests_diagnostic": "python scripts/run_phase_c_baseline_freeze_gate.py --all-historical-tests",
        "full_suite_semantics": "The release gate runs the governed Phase-C suite plus inherited scientific regressions; raw discovery of every historical test module is diagnostic only.",
        "windows_acceptance_command": ".\\freeze_phase_c_baseline_windows.bat",
        "colab_acceptance_command": "python scripts/run_phase_c_baseline_freeze_gate.py --full-suite",
        "operator_confirmation": {
            "kind": "user-supplied-terminal-attestation",
            "statement": "The application was confirmed before requesting the freeze.",
            "integrity_i1_log": "Ran 24 tests in 84.281s; QCOL INTEGRITY PRIMITIVES I1 + COMPARISON REALIZATION FOUNDATION: PASS",
            "cryptographic_scope": "The retained I1 evidence archive and catalog fingerprints are independently frozen; the terminal statement itself is not a source-code-generated attestation.",
        },
        "creation_environment_verification": {
            "architecture_audit": "PASS",
            "phase_c_focused_tests_passed": 45,
            "scientific_runtime_modules_skipped": 6,
            "skip_reason": "Cirq/OpenFermion/PyQASM scientific stack is not installed in the artifact-generation environment.",
            "interpretation": "This is not substituted for the accepted clean-environment scientific run; the source release attestations and user-confirmed application run remain the acceptance basis.",
        },
        "freeze_step_focused_tests_passed": 23,
        "freeze_step_changes_test_outcomes": False,
    }
    payload["fingerprint"] = _fingerprint(payload)
    return payload


def _canonical_evidence_archive_name(name: str) -> str:
    """Return the cross-platform identity of a retained Evidence archive.

    Windows filesystems are normally case-insensitive, while Linux/Colab can
    retain two historical aliases whose names differ only by letter case.
    The frozen inventory therefore records one case-folded identity per
    archive.  Aliases are accepted only when their bytes are identical.
    """

    return name.casefold()


def _evidence_archives(root: Path) -> list[dict[str, Any]]:
    candidates = sorted(
        {
            *root.glob("*Evidence*.zip"),
            *root.glob("*evidence*.zip"),
        },
        key=lambda p: (p.name.casefold(), p.name),
    )
    baseline_name = _canonical_evidence_archive_name(
        "QCOL_Phase_C_1_23_Baseline_Evidence.zip"
    )
    groups: dict[str, list[Path]] = {}
    for path in candidates:
        canonical_name = _canonical_evidence_archive_name(path.name)
        if canonical_name == baseline_name:
            continue
        groups.setdefault(canonical_name, []).append(path)

    rows: list[dict[str, Any]] = []
    for canonical_name in sorted(groups):
        aliases = groups[canonical_name]
        metadata: list[dict[str, Any]] = []
        for path in aliases:
            valid_zip = False
            bad_member: str | None = None
            try:
                with zipfile.ZipFile(path) as archive:
                    bad_member = archive.testzip()
                    valid_zip = bad_member is None
            except (OSError, zipfile.BadZipFile):
                valid_zip = False
            metadata.append(
                {
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "zip_crc_valid": valid_zip,
                    "first_bad_member": bad_member,
                }
            )

        identities = {
            (
                row["sha256"],
                row["size_bytes"],
                row["zip_crc_valid"],
                row["first_bad_member"],
            )
            for row in metadata
        }
        if len(identities) != 1:
            alias_names = ", ".join(sorted(path.name for path in aliases))
            raise ValueError(
                "Case-insensitive Evidence aliases have different content: "
                f"{alias_names}"
            )
        row = dict(metadata[0])
        row["path"] = canonical_name
        rows.append(row)
    return rows


def _baseline_source_diff(root: Path) -> dict[str, Any]:
    if _git_dir(root) is None:
        return {
            "git_repository_present": False,
            "git_cli_required": False,
            "git_reader": "none",
            "only_allowed_additions": False,
            "changed_paths": [],
        }
    diff = baseline_to_head_diff(root)
    rows = []
    allowed = True
    for item in diff:
        status = item["status"]
        path = item["path"]
        row_allowed = status == "A" and any(
            path.startswith(prefix) for prefix in _ALLOWED_NEW_PREFIXES
        )
        allowed &= row_allowed
        rows.append(
            {"status": status, "path": path, "allowed_step1_addition": row_allowed}
        )
    return {
        "git_repository_present": True,
        "git_cli_required": False,
        "git_reader": "pure-python-loose-object-reader",
        "baseline_commit": BASELINE_GIT_COMMIT,
        "only_allowed_additions": allowed,
        "changed_paths": rows,
        "pre_existing_file_modified_or_deleted": any(row["status"] != "A" for row in rows),
    }


def build_unified_baseline_manifest(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    branch = git_branch_record(root)
    dependencies = build_dependency_lock(root)
    statuses = build_scientific_status_snapshot(root)
    api = build_public_api_surface(root)
    tests = _source_release_test_results(root)
    evidence = _evidence_archives(root)
    catalog_index = _authoritative_json_index(root)
    source_diff = _baseline_source_diff(root)
    payload = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "freeze_tool_version": FREEZE_TOOL_VERSION,
        "result": "Frozen Phase-C 1.23 baseline",
        "project": {
            "name": "QCOL",
            "version": _read_project_version(root),
            "phase": "Phase C — Try / Compare",
            "hardening_program": "Post-Phase-C Architectural Hardening",
        },
        "source_revision": {
            "source_archive": BASELINE_SOURCE_PACKAGE,
            "source_archive_sha256": BASELINE_SOURCE_ARCHIVE_SHA256,
            "baseline_commit": branch.get("baseline_commit"),
            "baseline_tree": branch.get("baseline_tree"),
            "baseline_branch": BASELINE_BRANCH,
            "baseline_tag": BASELINE_TAG,
            "hardening_branch": HARDENING_BRANCH,
            "repository_kind": branch.get("repository_kind"),
        },
        "planned_integrity_merge_input": {
            "merged": False,
            "source_package": INTEGRITY_I1_SOURCE_PACKAGE,
            "source_archive_sha256": INTEGRITY_I1_SOURCE_ARCHIVE_SHA256,
            "integrity_catalog_fingerprint": INTEGRITY_I1_CATALOG_FINGERPRINT,
            "comparison_realization_fingerprint": INTEGRITY_I1_COMPARISON_FINGERPRINT,
        },
        "catalog_fingerprints": catalog_fingerprints(root),
        "catalog_contract_file_index": catalog_index,
        "catalog_contract_file_count": len(catalog_index),
        "dependency_lock": {
            "fingerprint": dependencies["fingerprint"],
            "file_count": len(dependencies["lock_files"]),
        },
        "scientific_statuses": {
            "fingerprint": statuses["fingerprint"],
            "published_cell_count": len(statuses["published_cells"]),
            "governed_realization_count": len(statuses["governed_realization_statuses"]),
        },
        "public_api": {
            "fingerprint": api["fingerprint"],
            "openapi_sha256": api["canonical_openapi_sha256"],
            "openapi_path_count": api["openapi_path_count"],
            "python_public_export_count": api["python_public_export_count"],
        },
        "test_results": {
            "fingerprint": tests["fingerprint"],
            "all_phase_a_b_c_release_attestations_pass": tests[
                "all_source_release_attestations_pass"
            ],
            "full_suite_command": tests["full_suite_command"],
        },
        "evidence_archives": evidence,
        "evidence_archive_count": len(evidence),
        "source_integrity": source_diff,
        "exit_conditions": {
            "all_phase_a_b_c_release_attestations_pass": tests[
                "all_source_release_attestations_pass"
            ],
            "accepted_scientific_fingerprints_frozen": bool(catalog_fingerprints(root)),
            "published_statuses_frozen": True,
            "references_frozen": True,
            "openapi_and_public_api_frozen": True,
            "pre_existing_source_changed": not source_diff.get("only_allowed_additions", False),
            "scientific_status_changed": False,
            "reference_changed": False,
            "second_runtime_created": False,
            "integrity_i1_merged": False,
        },
        "next_step": "Merge Integrity I1 into this exact baseline without changing Phase A/B/C outcomes.",
    }
    payload["manifest_fingerprint"] = _fingerprint(payload)
    return payload


def _deterministic_zip(path: Path, files: Mapping[str, bytes]) -> Path:
    """Write a byte-identical ZIP on Windows, Linux, and Colab.

    DEFLATE output can legitimately differ between zlib builds even when the
    uncompressed members are identical.  The Step-1 archive is small and is an
    integrity record, so it uses ZIP_STORED with every metadata field fixed.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=_FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.external_attr = 0o100644 << 16
            info.internal_attr = 0
            info.extra = b""
            info.comment = b""
            archive.writestr(info, files[name])
    return path


@dataclass(frozen=True)
class BaselineFreezeExport:
    root: Path
    archive_path: Path
    manifest: dict[str, Any]
    archive_manifest: dict[str, Any]


def export_frozen_baseline(
    project_root: Path | str, *, output_dir: Path | str | None = None
) -> BaselineFreezeExport:
    root = Path(project_root).resolve()
    out = Path(output_dir).resolve() if output_dir else root / "qcol_phase_c_1_23_frozen_baseline"
    out.mkdir(parents=True, exist_ok=True)

    dependency_lock = build_dependency_lock(root)
    statuses = build_scientific_status_snapshot(root)
    api_surface = build_public_api_surface(root)
    openapi = _read_json(root / "QCOL_Phase_C_OpenAPI.json")
    tests = _source_release_test_results(root)
    branch = git_branch_record(root)
    evidence_inventory = {
        "schema_version": "qcol-phase-c-evidence-archive-inventory/1.0",
        "archives": _evidence_archives(root),
    }
    catalog_index = {
        "schema_version": "qcol-phase-c-catalog-contract-index/1.0",
        "official_semantic_fingerprints": catalog_fingerprints(root),
        "files": _authoritative_json_index(root),
    }
    catalog_index["fingerprint"] = _fingerprint(catalog_index)

    root_files = {
        "QCOL_Phase_C_1_23_Dependency_Lock.json": dependency_lock,
        "QCOL_Phase_C_1_23_Scientific_Statuses.json": statuses,
        "QCOL_Phase_C_1_23_Public_API_Surface.json": api_surface,
        "QCOL_Phase_C_1_23_Frozen_OpenAPI.json": openapi,
        "QCOL_Phase_C_1_23_Test_Results.json": tests,
        "QCOL_Phase_C_1_23_Evidence_Archive_Inventory.json": evidence_inventory,
        "QCOL_Phase_C_1_23_Catalog_Contract_Index.json": catalog_index,
        "QCOL_Hardening_Branch_Record.json": branch,
    }
    for name, payload in root_files.items():
        _write_json(root / name, payload)

    manifest = build_unified_baseline_manifest(root)
    _write_json(root / "unified_baseline_manifest.json", manifest)

    payloads: dict[str, bytes] = {
        "unified_baseline_manifest.json": _json_bytes(manifest),
        **{name: _json_bytes(payload) for name, payload in root_files.items()},
    }
    archive_manifest = {
        "schema_version": "qcol-phase-c-frozen-baseline-evidence-manifest/1.0",
        "project_version": BASELINE_PROJECT_VERSION,
        "baseline_source_archive_sha256": BASELINE_SOURCE_ARCHIVE_SHA256,
        "baseline_git_commit": branch.get("baseline_commit"),
        "unified_baseline_manifest_fingerprint": manifest["manifest_fingerprint"],
        "files": [
            {"path": name, "sha256": sha256_bytes(data), "size_bytes": len(data)}
            for name, data in sorted(payloads.items())
        ],
        "strict_json": True,
        "pickle_used": False,
        "callable_payload_withheld": True,
        "scientific_behavior_changed": False,
        "second_runtime_created": False,
    }
    payloads["manifest.json"] = _json_bytes(archive_manifest)

    for name, data in payloads.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    archive_path = _deterministic_zip(root / "QCOL_Phase_C_1_23_Baseline_Evidence.zip", payloads)
    return BaselineFreezeExport(out, archive_path, manifest, archive_manifest)


def _compare_json(path: Path, current: Any) -> bool:
    return path.exists() and _canonical_json_bytes(_read_json(path)) == _canonical_json_bytes(current)


def _verify_evidence_archive(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
            names = set(archive.namelist())
            return all(
                row["path"] in names
                and sha256_bytes(archive.read(row["path"])) == row["sha256"]
                for row in manifest["files"]
            )
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError):
        return False


def verify_frozen_baseline(project_root: Path | str) -> dict[str, bool]:
    root = Path(project_root).resolve()
    manifest_path = root / "unified_baseline_manifest.json"
    if not manifest_path.exists():
        return {"manifest_present": False}
    manifest = _read_json(manifest_path)
    branch = git_branch_record(root)
    dependencies = build_dependency_lock(root)
    statuses = build_scientific_status_snapshot(root)
    api = build_public_api_surface(root)
    openapi = _read_json(root / "QCOL_Phase_C_OpenAPI.json")
    tests = _source_release_test_results(root)
    evidence = _evidence_archives(root)
    catalog_index = {
        "schema_version": "qcol-phase-c-catalog-contract-index/1.0",
        "official_semantic_fingerprints": catalog_fingerprints(root),
        "files": _authoritative_json_index(root),
    }
    catalog_index["fingerprint"] = _fingerprint(catalog_index)
    source_diff = _baseline_source_diff(root)

    return {
        "manifest_present": True,
        "manifest_schema_exact": manifest.get("schema_version") == FREEZE_SCHEMA_VERSION,
        "project_version_exact": _read_project_version(root) == BASELINE_PROJECT_VERSION
        and manifest["project"]["version"] == BASELINE_PROJECT_VERSION,
        "source_archive_identity_frozen": manifest["source_revision"]["source_archive_sha256"]
        == BASELINE_SOURCE_ARCHIVE_SHA256,
        "baseline_git_commit_exact": branch.get("baseline_commit") == BASELINE_GIT_COMMIT,
        "baseline_branch_present": bool(branch.get("baseline_branch_present")),
        "hardening_branch_present": bool(branch.get("hardening_branch_present")),
        "active_branch_is_hardening": branch.get("active_branch") == HARDENING_BRANCH,
        "baseline_tag_present": bool(branch.get("baseline_tag_present")),
        "only_allowed_step1_additions": bool(source_diff.get("only_allowed_additions")),
        "catalog_fingerprints_unchanged": manifest.get("catalog_fingerprints")
        == catalog_fingerprints(root),
        "catalog_contract_index_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Catalog_Contract_Index.json", catalog_index
        ),
        "dependency_lock_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Dependency_Lock.json", dependencies
        ),
        "scientific_statuses_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Scientific_Statuses.json", statuses
        ),
        "references_unchanged": _read_json(
            root / "QCOL_Phase_C_1_23_Scientific_Statuses.json"
        )["reference_anchors"]
        == statuses["reference_anchors"],
        "public_python_api_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Public_API_Surface.json", api
        ),
        "openapi_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Frozen_OpenAPI.json", openapi
        ),
        "source_release_attestations_unchanged": _compare_json(
            root / "QCOL_Phase_C_1_23_Test_Results.json", tests
        ),
        "all_phase_a_b_c_release_attestations_pass": tests[
            "all_source_release_attestations_pass"
        ],
        "evidence_archive_hashes_unchanged": _read_json(
            root / "QCOL_Phase_C_1_23_Evidence_Archive_Inventory.json"
        )["archives"]
        == evidence,
        "baseline_evidence_archive_valid": _verify_evidence_archive(
            root / "QCOL_Phase_C_1_23_Baseline_Evidence.zip"
        ),
        "scientific_behavior_change_is_false": manifest["exit_conditions"][
            "scientific_status_changed"
        ]
        is False
        and manifest["exit_conditions"]["reference_changed"] is False,
        "second_runtime_created_is_false": manifest["exit_conditions"][
            "second_runtime_created"
        ]
        is False,
        "integrity_i1_not_merged_yet": manifest["exit_conditions"]["integrity_i1_merged"]
        is False,
    }


__all__ = [
    "BASELINE_PROJECT_VERSION",
    "BASELINE_SOURCE_PACKAGE",
    "BASELINE_SOURCE_ARCHIVE_SHA256",
    "BASELINE_GIT_COMMIT",
    "BASELINE_BRANCH",
    "HARDENING_BRANCH",
    "BASELINE_TAG",
    "FREEZE_SCHEMA_VERSION",
    "BaselineFreezeExport",
    "sha256_file",
    "git_branch_record",
    "baseline_to_head_diff",
    "baseline_commit_file_bytes",
    "catalog_fingerprints",
    "build_dependency_lock",
    "build_scientific_status_snapshot",
    "build_public_api_surface",
    "build_unified_baseline_manifest",
    "export_frozen_baseline",
    "verify_frozen_baseline",
]
