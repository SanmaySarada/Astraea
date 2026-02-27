"""Dataset execution pipeline for transforming mapping specs into SDTM DataFrames.

Re-exports key classes for convenient imports:
    from astraea.execution import DatasetExecutor, CrossDomainContext, ExecutionError
"""

from astraea.execution.executor import CrossDomainContext, DatasetExecutor, ExecutionError

__all__ = [
    "CrossDomainContext",
    "DatasetExecutor",
    "ExecutionError",
]
