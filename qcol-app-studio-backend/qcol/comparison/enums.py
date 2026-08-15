"""Phase C Try / Compare vocabulary."""
from enum import StrEnum


class ComparisonOutcome(StrEnum):
    ADOPT = "ADOPT"
    REJECT = "REJECT"
    INCONCLUSIVE = "INCONCLUSIVE"


class ComparisonKind(StrEnum):
    EXECUTABLE_VQE = "executable_vqe"
    MAPPING_ANALYSIS = "mapping_analysis"


class ComparisonStatus(StrEnum):
    WAITING_FOR_CANDIDATE = "waiting_for_candidate"
    COMPARING = "comparing"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricDirection(StrEnum):
    LOWER_IS_BETTER = "lower_is_better"
    HIGHER_IS_BETTER = "higher_is_better"
    EQUAL_REQUIRED = "equal_required"
    INFORMATION_ONLY = "information_only"


class MetricJudgment(StrEnum):
    IMPROVED = "improved"
    WORSENED = "worsened"
    EQUIVALENT = "equivalent"
    MIXED = "mixed"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


__all__ = [
    "ComparisonOutcome", "ComparisonKind", "ComparisonStatus",
    "MetricDirection", "MetricJudgment",
]
