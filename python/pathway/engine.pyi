# Copyright © 2024 Pathway

"""Variant of API with immediate evaluation in Python."""

from __future__ import annotations

import asyncio
import dataclasses
from collections.abc import Callable, Iterable
from enum import Enum
from typing import Any, Generic, TypeVar, Union, final

from pathway.internals.api import CapturedStream, CombineMany, S, Value
from pathway.internals.column_path import ColumnPath
from pathway.internals.dtype import DType
from pathway.internals.monitoring import StatsMonitor

_T = TypeVar("_T")

@final
class Pointer(Generic[_T]):
    pass

def ref_scalar(*args, optional=False) -> Pointer: ...

class PathwayType(Enum):
    ANY: PathwayType
    STRING: PathwayType
    INT: PathwayType
    BOOL: PathwayType
    FLOAT: PathwayType
    POINTER: PathwayType
    DATE_TIME_NAIVE: PathwayType
    DATE_TIME_UTC: PathwayType
    DURATION: PathwayType
    ARRAY: PathwayType
    JSON: PathwayType
    TUPLE: PathwayType
    BYTES: PathwayType

class ConnectorMode(Enum):
    STATIC: ConnectorMode
    STREAMING: ConnectorMode

class ReadMethod(Enum):
    BY_LINE: ReadMethod
    FULL: ReadMethod

class DebeziumDBType(Enum):
    POSTGRES: DebeziumDBType
    MONGO_DB: DebeziumDBType

class Universe:
    pass

@dataclasses.dataclass(frozen=True)
class Trace:
    file_name: str
    line_number: int
    line: str
    function: str

@dataclasses.dataclass(frozen=True)
class ColumnProperties:
    dtype: PathwayType | None = None
    trace: Trace | None = None
    append_only: bool = False

class TableProperties:
    @staticmethod
    def column(column_prroperties: ColumnProperties) -> TableProperties: ...
    @staticmethod
    def from_column_properties(
        column_properties: Iterable[tuple[ColumnPath, ColumnProperties]]
    ) -> TableProperties: ...

@dataclasses.dataclass(frozen=True)
class ConnectorProperties:
    commit_duration_ms: int | None = None
    unsafe_trusted_ids: bool | None = False
    column_properties: list[ColumnProperties] = []

class Column:
    """A Column holds data and conceptually is a Dict[Universe elems, dt]

    Columns should not be constructed directly, but using methods of the scope.
    All fields are private.
    """

    @property
    def universe(self) -> Universe: ...

class LegacyTable:
    """A `LegacyTable` is a thin wrapper over a list of Columns.

    universe and columns are public fields - tables can be constructed
    """

    def __init__(self, universe: Universe, columns: list[Column]): ...
    @property
    def universe(self) -> Universe: ...
    @property
    def columns(self) -> list[Column]: ...

class Table:
    """Table with tuples containing values from multiple columns."""

class DataRow:
    """Row of data for static_table"""

    key: Pointer
    values: list[Value]
    time: int
    diff: int
    shard: int | None

    def __init__(
        self,
        key: Pointer,
        values: list[Value],
        time: int = 0,
        diff: int = 1,
        shard: int | None = None,
    ) -> None: ...

class MissingValueError(BaseException):
    "Marker class to indicate missing attributes"

class EngineError(Exception):
    "Marker class to indicate engine error"

class EngineErrorWithTrace(Exception):
    "Marker class to indicate engine error with trace"
    args: tuple[Exception, Trace | None]

class Reducer:
    ARG_MIN: Reducer
    MIN: Reducer
    ARG_MAX: Reducer
    MAX: Reducer
    FLOAT_SUM: Reducer
    ARRAY_SUM: Reducer
    INT_SUM: Reducer
    @staticmethod
    def sorted_tuple(skip_nones: bool) -> Reducer: ...
    @staticmethod
    def tuple(skip_nones: bool) -> Reducer: ...
    UNIQUE: Reducer
    ANY: Reducer
    COUNT: Reducer
    @staticmethod
    def stateful_many(combine_many: CombineMany[S]) -> Reducer: ...

class UnaryOperator:
    INV: UnaryOperator
    NEG: UnaryOperator

class BinaryOperator:
    AND: BinaryOperator
    OR: BinaryOperator
    XOR: BinaryOperator
    EQ: BinaryOperator
    NE: BinaryOperator
    LT: BinaryOperator
    LE: BinaryOperator
    GT: BinaryOperator
    GE: BinaryOperator
    ADD: BinaryOperator
    SUB: BinaryOperator
    MUL: BinaryOperator
    FLOOR_DIV: BinaryOperator
    TRUE_DIV: BinaryOperator
    MOD: BinaryOperator
    POW: BinaryOperator
    LSHIFT: BinaryOperator
    RSHIFT: BinaryOperator
    MATMUL: BinaryOperator

class Expression:
    @staticmethod
    def const(value: Value) -> Expression: ...
    @staticmethod
    def argument(index: int) -> Expression: ...
    @staticmethod
    def apply(fun: Callable, /, *args: Expression) -> Expression: ...
    @staticmethod
    def unsafe_numba_apply(fun: Callable, /, *args: Expression) -> Expression: ...
    @staticmethod
    def is_none(expr: Expression) -> Expression: ...
    @staticmethod
    def unary_expression(
        expr: Expression, operator: UnaryOperator, expr_dtype: PathwayType
    ) -> Expression | None: ...
    @staticmethod
    def binary_expression(
        lhs: Expression,
        rhs: Expression,
        operator: BinaryOperator,
        left_dtype: PathwayType,
        right_dtype: PathwayType,
    ) -> Expression | None: ...
    @staticmethod
    def eq(lhs: Expression, rhs: Expression) -> Expression: ...
    @staticmethod
    def ne(lhs: Expression, rhs: Expression) -> Expression: ...
    @staticmethod
    def int_abs(lhs: Expression, rhs: Expression) -> Expression: ...
    @staticmethod
    def float_abs(lhs: Expression, rhs: Expression) -> Expression: ...
    @staticmethod
    def cast(
        expr: Expression, source_type: PathwayType, target_type: PathwayType
    ) -> Expression | None: ...
    @staticmethod
    def cast_optional(
        expr: Expression, source_type: PathwayType, target_type: PathwayType
    ) -> Expression | None: ...
    def convert_optional(
        expr: Expression, source_type: PathwayType, target_type: PathwayType
    ) -> Expression | None: ...
    @staticmethod
    def if_else(if_: Expression, then: Expression, else_: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_nanosecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_microsecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_millisecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_second(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_minute(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_hour(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_day(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_month(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_year(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_timestamp_ns(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_timestamp(expr: Expression, unit: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_weekday(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_strptime(expr: Expression, fmt: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_strftime(expr: Expression, fmt: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_from_timestamp(
        expr: Expression, unit: Expression
    ) -> Expression: ...
    @staticmethod
    def date_time_naive_from_float_timestamp(
        expr: Expression, unit: Expression
    ) -> Expression: ...
    @staticmethod
    def date_time_naive_to_utc(
        expr: Expression, from_timezone: Expression
    ) -> Expression: ...
    @staticmethod
    def date_time_naive_round(expr: Expression, duration: Expression) -> Expression: ...
    @staticmethod
    def date_time_naive_floor(expr: Expression, duration: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_nanosecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_microsecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_millisecond(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_second(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_minute(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_hour(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_day(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_month(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_year(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_timestamp_ns(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_timestamp(expr: Expression, unit: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_weekday(expr: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_strptime(expr: Expression, fmt: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_strftime(expr: Expression, fmt: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_to_naive(
        expr: Expression, to_timezone: Expression
    ) -> Expression: ...
    @staticmethod
    def date_time_utc_round(expr: Expression, duration: Expression) -> Expression: ...
    @staticmethod
    def date_time_utc_floor(expr: Expression, duration: Expression) -> Expression: ...
    @staticmethod
    def duration_nanoseconds(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_microseconds(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_milliseconds(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_seconds(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_minutes(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_hours(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_days(expr: Expression) -> Expression: ...
    @staticmethod
    def duration_weeks(expr: Expression) -> Expression: ...
    @staticmethod
    def parse_int(expr: Expression, optional: bool) -> Expression: ...
    @staticmethod
    def parse_float(expr: Expression, optional: bool) -> Expression: ...
    @staticmethod
    def parse_bool(
        expr: Expression, true_list: list[str], false_list: list[str], optional: bool
    ) -> Expression: ...
    @staticmethod
    def pointer_from(*args: Expression, optional: bool) -> Expression: ...
    @staticmethod
    def make_tuple(*args: Expression) -> Expression: ...
    @staticmethod
    def sequence_get_item_checked(
        expr: Expression, index: Expression, default: Expression
    ) -> Expression: ...
    @staticmethod
    def sequence_get_item_unchecked(
        expr: Expression, index: Expression
    ) -> Expression: ...
    @staticmethod
    def json_get_item_checked(
        expr: Expression, index: Expression, default: Expression
    ) -> Expression: ...
    @staticmethod
    def json_get_item_unchecked(expr: Expression, index: Expression) -> Expression: ...
    @staticmethod
    def unwrap(expr: Expression) -> Expression: ...
    @staticmethod
    def to_string(expr: Expression) -> Expression: ...

class MonitoringLevel(Enum):
    NONE = 0
    IN_OUT = 1
    ALL = 2

class Context:
    # "Location" of the current attribute in the transformer computation
    this_row: Pointer
    data: tuple[Value, Pointer]

    def raising_get(self, column: int, row: Pointer, *args: Value) -> Value: ...

class Computer:
    @classmethod
    def from_raising_fun(
        cls,
        fun: Callable[[Context], Value],
        *,
        dtype: DType,
        is_output: bool,
        is_method: bool,
        universe: Universe,
        data: Value = None,
        data_column: Column | None = None,
    ) -> Computer: ...

ComplexColumn = Union[Column, Computer]

class Scope:
    @property
    def parent(self) -> Scope | None: ...
    def empty_table(self, properties: ConnectorProperties) -> Table: ...
    def iterate(
        self,
        iterated: list[LegacyTable],
        iterated_with_universe: list[LegacyTable],
        extra: list[LegacyTable],
        logic: Callable[
            [Scope, list[LegacyTable], list[LegacyTable], list[LegacyTable]],
            tuple[list[LegacyTable], list[LegacyTable]],
        ],
        *,
        limit: int | None = None,
    ) -> tuple[list[LegacyTable], list[LegacyTable]]:
        """Fixed-point iteration

        logic is called with a new scope, clones of tables from iterated,
        clones of tables from extra.
        logic should not use any other outside tables.
        logic must return a list of tables corresponding to iterated:
        result[i] is the result of single iteration on iterated[i]
        """
        ...
    # Evaluators for expressions

    def static_universe(self, keys: Iterable[Pointer]) -> Universe: ...
    def static_column(
        self, universe: Universe, rows: Iterable[tuple[Pointer, Any]], dt: DType
    ) -> Column: ...
    def static_table(
        self,
        universe: Universe,
        rows: Iterable[DataRow],
        dt: DType,
    ) -> Table: ...
    def map_column(
        self,
        table: LegacyTable,
        function: Callable[[tuple[Value, ...]], Value],
        properties: ColumnProperties,
    ) -> Column: ...
    def expression_table(
        self,
        table: Table,
        column_paths: list[ColumnPath],
        expressions: list[tuple[Expression, TableProperties]],
    ) -> Table: ...
    def table_properties(self, table: Table) -> TableProperties: ...
    def columns_to_table(self, universe: Universe, columns: list[Column]) -> Table: ...
    def table_column(
        self, universe: Universe, table: Table, column_path: ColumnPath
    ) -> Column: ...
    def table_universe(self, table: Table) -> Universe: ...
    def flatten_table_storage(
        self, table: Table, column_paths: list[ColumnPath]
    ) -> Table: ...
    def async_apply_table(
        self,
        table: Table,
        column_paths: list[ColumnPath],
        function: Callable[..., Value],
        properties: TableProperties,
    ) -> Table: ...
    def gradual_broadcast(
        self,
        input_table_storage: Table,
        threshold_table_storage: Table,
        lower_column: ColumnPath,
        value_column: ColumnPath,
        upper_column: ColumnPath,
        table_properties: TableProperties,
    ) -> Table: ...
    def filter_table(
        self, table: Table, path: ColumnPath, table_properties: TableProperties
    ) -> Table: ...
    def forget(
        self,
        table: Table,
        threshold_time_path: ColumnPath,
        current_time_path: ColumnPath,
        mark_forgetting_records: bool,
        table_properties: TableProperties,
    ) -> Table: ...
    def forget_immediately(
        self,
        table: Table,
        table_properties: TableProperties,
    ) -> Table: ...
    def filter_out_results_of_forgetting(
        self,
        table: Table,
        table_properties: TableProperties,
    ) -> Table: ...
    def freeze(
        self,
        table: Table,
        threshold_time_path: ColumnPath,
        current_time_path: ColumnPath,
        table_properties: TableProperties,
    ) -> Table: ...
    def buffer(
        self,
        table: Table,
        threshold_time_path: ColumnPath,
        current_time_path: ColumnPath,
        table_properties: TableProperties,
    ) -> Table: ...
    def intersect_tables(
        self, table: Table, tables: Iterable[Table], table_properties: TableProperties
    ) -> Table: ...
    def subtract_table(
        self, left_table: Table, right_table: Table, table_properties: TableProperties
    ) -> Table: ...
    def restrict_column(
        self,
        universe: Universe,
        column: Column,
    ) -> Column: ...
    def restrict_table(
        self, orig_table: Table, new_table: Table, table_properties: TableProperties
    ) -> Table: ...
    def override_table_universe(
        self, orig_table: Table, new_table: Table, table_properties: TableProperties
    ) -> Table: ...
    def reindex_table(
        self,
        table: Table,
        reindexing_column_path: ColumnPath,
        table_properties: TableProperties,
    ) -> Table: ...
    def connector_table(
        self,
        data_source: DataStorage,
        data_format: DataFormat,
        properties: ConnectorProperties,
    ) -> Table: ...
    @staticmethod
    def table(universe: Universe, columns: list[Column]) -> LegacyTable: ...

    # Grouping and joins

    def group_by_table(
        self,
        table: Table,
        grouping_columns: list[ColumnPath],
        reducers: list[tuple[Reducer, list[ColumnPath]]],
        by_id: bool,
        table_properties: TableProperties,
    ) -> Table: ...
    def ix_table(
        self,
        to_ix_table: Table,
        key_table: Table,
        key_column_path: ColumnPath,
        optional: bool,
        strict: bool,
        table_properties: TableProperties,
    ) -> Table: ...
    def join_tables(
        self,
        left_storage: Table,
        right_storage: Table,
        left_paths: list[ColumnPath],
        right_paths: list[ColumnPath],
        table_properties: TableProperties,
        assign_id: bool = False,
        left_ear: bool = False,
        right_ear: bool = False,
    ) -> Table: ...

    # Transformers

    def complex_columns(self, inputs: list[ComplexColumn]) -> list[Column]: ...

    # Updates

    def update_rows_table(
        self, table: Table, update: Table, table_properties: TableProperties
    ) -> Table: ...
    def update_cells_table(
        self,
        table: Table,
        update: Table,
        table_columns: list[ColumnPath],
        update_columns: list[ColumnPath],
        table_properties: TableProperties,
    ) -> Table: ...
    def debug_universe(self, name: str, table: Table): ...
    def debug_column(self, name: str, table: Table, column_path: ColumnPath): ...
    def concat_tables(
        self, tables: Iterable[Table], table_properties: TableProperties
    ) -> Table: ...
    def flatten_table(
        self, table: Table, path: ColumnPath, table_properties: TableProperties
    ) -> Table: ...
    def sort_table(
        self,
        table: Table,
        key_column_path: ColumnPath,
        instance_column_path: ColumnPath,
        table_properties: TableProperties,
    ) -> Table: ...
    def probe_table(self, table: Table, operator_id: int): ...
    def subscribe_table(
        self,
        table: Table,
        column_paths: Iterable[ColumnPath],
        skip_persisted_batch: bool,
        on_change: Callable,
        on_time_end: Callable,
        on_end: Callable,
    ): ...
    def output_table(
        self,
        table: Table,
        column_paths: Iterable[ColumnPath],
        data_sink: DataStorage,
        data_format: DataFormat,
    ): ...

def run_with_new_graph(
    logic: Callable[[Scope], Iterable[tuple[Table, list[ColumnPath]]]],
    event_loop: asyncio.AbstractEventLoop,
    stats_monitor: StatsMonitor | None = None,
    *,
    ignore_asserts: bool = False,
    monitoring_level: MonitoringLevel = MonitoringLevel.NONE,
    with_http_server: bool = False,
    persistence_config: PersistenceConfig | None = None,
) -> list[CapturedStream]: ...
def unsafe_make_pointer(arg) -> Pointer: ...

class DataFormat:
    value_fields: Any

    def __init__(self, *args, **kwargs): ...

class DataStorage:
    storage_type: str
    path: str | None
    rdkafka_settings: dict[str, str] | None
    topic: str | None
    connection_string: str | None
    csv_parser_settings: CsvParserSettings | None
    mode: ConnectorMode
    read_method: ReadMethod
    aws_s3_settings: AwsS3Settings | None
    elasticsearch_params: ElasticSearchParams | None
    parallel_readers: int | None
    python_subject: PythonSubject | None
    persistent_id: str | None
    max_batch_size: int | None
    object_pattern: str
    mock_events: dict[tuple[str, int], list[SnapshotEvent]] | None
    table_name: str | None
    column_names: list[str] | None
    def __init__(self, *args, **kwargs): ...

class CsvParserSettings:
    def __init__(self, *args, **kwargs): ...

class AwsS3Settings:
    def __init__(self, *args, **kwargs): ...

class ValueField:
    name: str
    def __init__(self, *args, **kwargs): ...
    def set_default(self, *args, **kwargs): ...

class PythonSubject:
    def __init__(self, *args, **kwargs): ...

class ElasticSearchAuth:
    def __init__(self, *args, **kwargs): ...

class ElasticSearchParams:
    def __init__(self, *args, **kwargs): ...

class PersistenceConfig:
    def __init__(self, *args, **kwargs): ...

class PersistenceMode(Enum):
    BATCH: PersistenceMode
    SPEEDRUN_REPLAY: PersistenceMode
    REALTIME_REPLAY: PersistenceMode
    PERSISTING: PersistenceMode
    UDF_CACHING: PersistenceMode

class SnapshotAccess(Enum):
    RECORD: SnapshotAccess
    REPLAY: SnapshotAccess
    FULL: SnapshotAccess

class DataEventType(Enum):
    INSERT: DataEventType
    DELETE: DataEventType
    UPSERT: DataEventType

class SessionType(Enum):
    NATIVE: SessionType
    UPSERT: SessionType

class SnapshotEvent:
    @staticmethod
    def insert(key: Pointer, values: list[Value]) -> SnapshotEvent: ...
    @staticmethod
    def delete(key: Pointer, values: list[Value]) -> SnapshotEvent: ...
    @staticmethod
    def advance_time(timestamp: int) -> SnapshotEvent: ...
    FINISHED: SnapshotEvent

class LocalBinarySnapshotWriter:
    def __init__(self, path: str, persistent_id: str, worker_id: int): ...
    def write(self, events: list[SnapshotEvent]): ...
