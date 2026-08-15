"""Public task-contract API."""
from .base import (
    TASK_CONTRACT_SCHEMA_VERSION,
    TASK_INSTANCE_SCHEMA_VERSION,
    TASK_EXECUTION_PLAN_SCHEMA_VERSION,
    MODEL_TASK_PLAN_SCHEMA_VERSION,
    TaskParameterSpec,
    TaskContract,
    TaskInstance,
    TaskExecutionPlan,
    ModelTaskCapabilityReport,
    ResolvedModelTaskPlan,
)

__all__ = [
    "TASK_CONTRACT_SCHEMA_VERSION",
    "TASK_INSTANCE_SCHEMA_VERSION",
    "TASK_EXECUTION_PLAN_SCHEMA_VERSION",
    "MODEL_TASK_PLAN_SCHEMA_VERSION",
    "TaskParameterSpec",
    "TaskContract",
    "TaskInstance",
    "TaskExecutionPlan",
    "ModelTaskCapabilityReport",
    "ResolvedModelTaskPlan",
]

from .mapping_analysis import MAPPING_ANALYSIS_TASK_CONTRACT
