"""Dataset execution pipeline for transforming mapping specs into SDTM DataFrames.

Re-exports key classes for convenient imports:
    from astraea.execution import DatasetExecutor, CrossDomainContext, ExecutionError
"""

from astraea.execution.executor import CrossDomainContext, DatasetExecutor, ExecutionError
from astraea.execution.preprocessing import align_multi_source_columns, filter_rows

__all__ = [
    "CrossDomainContext",
    "DatasetExecutor",
    "ExecutionError",
    "align_multi_source_columns",
    "filter_rows",
]
