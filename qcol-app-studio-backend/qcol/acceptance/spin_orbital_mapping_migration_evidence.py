"""Evidence exporter for WP9/WP10 JW and BK policy migrations."""
from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from qcol import __version__


@dataclass(frozen=True)
class SpinOrbitalMappingMigrationEvidenceExport:
    output_dir: Path
    archive_path: Path
    manifest_path: Path
    scientific_checks_included: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "archive_path": str(self.archive_path),
            "manifest_path": str(self.manifest_path),
            "scientific_checks_included": self.scientific_checks_included,
        }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dependencies() -> dict[str, str | None]:
    names=("numpy","scipy","cirq-core","openfermion","pyqasm","ply","fastapi","gradio")
    out={}
    for name in names:
        try: out[name]=metadata.version(name)
        except metadata.PackageNotFoundError: out[name]=None
    return out


def _source_fingerprints(project_root: Path) -> dict[str,str]:
    paths=(
        "qcol/mapping_policies/profiles/spin_orbital_migrations.py",
        "qcol/mapping_policies/profiles/fermion_bindings.py",
        "qcol/mapping_policies/profiles/__init__.py",
        "qcol/mapping_policies/__init__.py",
        "qcol/mappings/jordan_wigner.py",
        "qcol/mappings/bravyi_kitaev.py",
        "qcol/mappings/registry.py",
        "qcol/acceptance/spin_orbital_mapping_migration_evidence.py",
        "qcol/api.py",
        "qcol/catalog.py",
        "qcol/__init__.py",
        "pyproject.toml",
        "requirements.txt",
    )
    return {r:_sha(project_root/r) for r in paths if (project_root/r).exists()}


def collect_spin_orbital_mapping_scientific_regressions() -> dict[str,Any]:
    """Run the verified analysis cell and representation-level code checks."""
    from qcol.orchestrator import run_pipeline
    from qcol.mappings import get_mapping_plugin
    from qcol.acceptance import evaluate_frozen_jw_negative_fixture

    request={
        "method":"general_spin_orbital","problem":"mapping_explorer","task_id":"mapping_analysis",
        "parameters":{
            "n_modes":2,"particle_species":"neutron","mode_labels":"neutron|a\nneutron|b",
            "one_body_terms":"0,0,0.0\n1,1,1.0\n0,1,0.2\n1,0,0.2","two_body_terms":"",
            "target_particle_number":1,"declared_symmetries":["particle_number"],
            "coefficient_convention":"explicit_operator_coefficient","energy_unit":"MeV",
        },
        "task_parameters":{"mapping_ids":["jordan_wigner.v1","bravyi_kitaev.v1"],"coefficient_threshold":1e-12,"equivalence_tolerance":1e-8},
        "requested_observables":["mapping_resources","mapping_equivalence"],
        "execution_mode":"analysis_only","target_backend":"none","run_mode":"mapping_analysis",
        "shots":0,"final_shots":0,"max_evaluations":1,"seed":0,
    }
    artifact,result=run_pipeline(request)
    round_trips={}
    samples=((0,0,0,0),(1,0,0,0),(1,1,0,0),(1,0,1,0),(1,1,1,1))
    for mapping_id in ("jordan_wigner.v1","bravyi_kitaev.v1"):
        plugin=get_mapping_plugin(mapping_id)
        round_trips[mapping_id]=all(plugin.decode_basis_bitstring(plugin.encode_occupation_state(x))==x for x in samples)
    negative=evaluate_frozen_jw_negative_fixture().to_dict()
    return {
        "schema_version":"qcol-wp9-wp10-scientific-regressions/1.0",
        "mapping_analysis":{"status":result.status,"task_id":result.task_id,"all_transforms_verified":bool(result.task_result["all_transforms_verified"]),"shots":result.shots_per_group,"hardware_submission_performed":result.hardware_submission_performed,"artifact_model_id":artifact.model_id},
        "basis_round_trips":round_trips,
        "jw_current_composition_negative_fixture":negative,
        "bk_raw_popcount_is_particle_number":False,
        "scientific_status_promoted":False,
        "scientific_behavior_change":False,
    }


def export_spin_orbital_mapping_migration_evidence(output: str|Path, *, include_scientific_checks: bool=False, project_root: str|Path|None=None) -> SpinOrbitalMappingMigrationEvidenceExport:
    from qcol.mapping_policies.profiles import (
        public_spin_orbital_mapping_migration_catalog,
        spin_orbital_mapping_migration_catalog_fingerprint,
        validate_spin_orbital_mapping_migration,
        public_a3_2b_exit_decision,
    )
    root=Path(project_root or Path(__file__).resolve().parents[2]).resolve()
    output_dir=Path(output).resolve()
    if output_dir.exists(): shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    catalog=public_spin_orbital_mapping_migration_catalog()
    checks=validate_spin_orbital_mapping_migration(catalog)
    if not all(checks.values()):
        raise AssertionError("WP9/WP10 validation failed: "+", ".join(k for k,v in checks.items() if not v))
    exit_decision=public_a3_2b_exit_decision()
    _write_json(output_dir/"jw_bk_policy_migration_catalog.json",catalog)
    _write_json(output_dir/"migration_validation.json",checks)
    _write_json(output_dir/"jordan_wigner_profile.json",catalog["jw"]["profile"])
    _write_json(output_dir/"bravyi_kitaev_profile.json",catalog["bk"]["profile"])
    _write_json(output_dir/"jordan_wigner_policy_contracts.json",catalog["jw"]["contracts"])
    _write_json(output_dir/"bravyi_kitaev_policy_contracts.json",catalog["bk"]["contracts"])
    _write_json(output_dir/"jordan_wigner_mapping_analysis_resolution.json",catalog["jw"]["resolutions"]["jw_mapping_analysis"])
    _write_json(output_dir/"jordan_wigner_current_ground_state_resolution.json",catalog["jw"]["resolutions"]["jw_ground_state_current"])
    _write_json(output_dir/"bravyi_kitaev_mapping_analysis_resolution.json",catalog["bk"]["resolutions"]["bk_mapping_analysis"])
    _write_json(output_dir/"bravyi_kitaev_ground_state_resolution.json",catalog["bk"]["resolutions"]["bk_ground_state"])
    _write_json(output_dir/"jordan_wigner_mapping_analysis_harness.json",catalog["jw"]["acceptance_harness"]["jw_mapping_analysis"])
    _write_json(output_dir/"jordan_wigner_current_ground_state_harness.json",catalog["jw"]["acceptance_harness"]["jw_ground_state_current"])
    _write_json(output_dir/"bravyi_kitaev_mapping_analysis_harness.json",catalog["bk"]["acceptance_harness"]["bk_mapping_analysis"])
    _write_json(output_dir/"bravyi_kitaev_ground_state_harness.json",catalog["bk"]["acceptance_harness"]["bk_ground_state"])
    _write_json(output_dir/"legacy_policy_migrations.json",catalog["legacy_policy_migrations"])
    _write_json(output_dir/"a3_2b_exit_decision.json",exit_decision)
    _write_json(output_dir/"foundation_fingerprints.json",catalog["foundation_fingerprints"])
    _write_json(output_dir/"dependency_versions.json",_dependencies())
    _write_json(output_dir/"source_fingerprints.json",_source_fingerprints(root))
    if include_scientific_checks:
        _write_json(output_dir/"scientific_regressions.json",collect_spin_orbital_mapping_scientific_regressions())
    files=sorted(x for x in output_dir.rglob("*") if x.is_file() and x.name!="manifest.json")
    manifest={
        "schema_version":"qcol-wp9-wp10-mapping-policy-migration-evidence/1.0",
        "phase":"Phase A.3.2b","work_packages":["WP9 — Jordan–Wigner","WP10 — Bravyi–Kitaev"],
        "project_version":__version__,"catalog_fingerprint":spin_orbital_mapping_migration_catalog_fingerprint(catalog),
        "jw_mapper":"verified","jw_mapping_analysis":"acceptance_verified","jw_current_composition":"rejected","jw_ground_state_cell":"not_verified",
        "bk_mapper":"verified","bk_mapping_analysis":"acceptance_verified","bk_ground_state_composition":"unresolved","bk_full_execution":"recognized_not_executable","bk_raw_popcount_is_particle_number":False,
        "a3_2b_exit_status":exit_decision["status"],"scientific_checks_included":include_scientific_checks,
        "scientific_status_promoted":False,"scientific_behavior_change":False,"second_runtime_created":False,
        "files":[{"name":str(x.relative_to(output_dir)).replace("\\","/"),"sha256":_sha(x),"size_bytes":x.stat().st_size} for x in files],
    }
    manifest_path=output_dir/"manifest.json"; _write_json(manifest_path,manifest)
    archive_path=Path(shutil.make_archive(str(output_dir),"zip",root_dir=output_dir))
    return SpinOrbitalMappingMigrationEvidenceExport(output_dir,archive_path,manifest_path,include_scientific_checks)


__all__=["SpinOrbitalMappingMigrationEvidenceExport","collect_spin_orbital_mapping_scientific_regressions","export_spin_orbital_mapping_migration_evidence"]
