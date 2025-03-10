# Copyright © 2024 Pathway

from __future__ import annotations

import collections
import multiprocessing
import os
import pathlib
import re
import sys
import time
from abc import abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import pytest

import pathway as pw
from pathway.debug import _markdown_to_pandas, table_from_markdown, table_from_pandas
from pathway.internals import api, datasource
from pathway.internals.graph_runner import GraphRunner
from pathway.internals.schema import is_subschema, schema_from_columns
from pathway.internals.table import Table

try:
    import numba  # noqa

    _numba_missing = False
except ImportError:
    _numba_missing = True

xfail_no_numba = pytest.mark.xfail(_numba_missing, reason="unable to import numba")

needs_multiprocessing_fork = pytest.mark.xfail(
    sys.platform != "linux",
    reason="multiprocessing needs to use fork() for pw.run() to work",
)

xfail_on_multiple_threads = pytest.mark.xfail(
    os.getenv("PATHWAY_THREADS", "1") != "1", reason="multiple threads"
)


def skip_on_multiple_workers() -> None:
    if os.environ.get("PATHWAY_THREADS", "1") != "1":
        pytest.skip()


@dataclass(order=True)
class DiffEntry:
    key: api.Pointer
    order: int
    insertion: bool
    row: dict[str, api.Value]

    @staticmethod
    def create(
        pk_table: pw.Table,
        pk_columns: dict[str, api.Value],
        order: int,
        insertion: bool,
        row: dict[str, api.Value],
    ) -> DiffEntry:
        key = api.ref_scalar(*pk_columns.values())
        return DiffEntry(key, order, insertion, row)

    def final_cleanup_entry(self):
        return DiffEntry(self.key, self.order + 1, False, self.row)

    @staticmethod
    def create_id_from(
        pk_table: pw.Table,
        pk_columns: dict[str, api.Value],
    ) -> api.Pointer:
        return api.ref_scalar(*pk_columns.values())


# This class is an abstract subclass of OnChangeCallback, which takes a list of entries
# representing a stream, groups them by key, and orders them by (order, insertion);
# Such organized representation of a stream is kept in `state`.
#
# Remarks: the orders associated with any fixed key may differ from the times in the stream
# (as it's difficult to impose precise times to be present in the engine);
# the requirement is that for a fixed key, the ordering (by order, insertion) of entries
# should be the same as the same as what we expect to see in the output
class CheckKeyEntriesInStreamCallback(pw.io._subscribe.OnChangeCallback):
    state: collections.defaultdict[api.Pointer, collections.deque[DiffEntry]]

    def __init__(self, state_list: Iterable[DiffEntry]):
        super().__init__()
        state_list = sorted(state_list)
        self.state = collections.defaultdict(lambda: collections.deque())
        for entry in state_list:
            self.state[entry.key].append(entry)

    @abstractmethod
    def __call__(
        self,
        key: api.Pointer,
        row: dict[str, api.Value],
        time: int,
        is_addition: bool,
    ) -> Any:
        pass


class CheckKeyConsistentInStreamCallback(CheckKeyEntriesInStreamCallback):
    def __call__(
        self,
        key: api.Pointer,
        row: dict[str, api.Value],
        time: int,
        is_addition: bool,
    ) -> Any:
        q = self.state.get(key)
        assert (
            q
        ), f"Got unexpected entry {key=} {row=} {time=} {is_addition=}, expected entries= {self.state!r}"

        while True:
            entry = q.popleft()
            if (is_addition, row) == (entry.insertion, entry.row):
                if not q:
                    self.state.pop(key)
                break
            else:
                assert (
                    q
                ), f"Skipping over entries emptied the set of expected entries for {key=} and state = {self.state!r}"

    def on_end(self):
        assert not self.state, f"Non empty final state = {self.state!r}"


# this callback does not verify the order of entries, only that all of them were present
class CheckStreamEntriesEqualityCallback(CheckKeyEntriesInStreamCallback):
    def __call__(
        self,
        key: api.Pointer,
        row: dict[str, api.Value],
        time: int,
        is_addition: bool,
    ) -> Any:
        q = self.state.get(key)
        assert (
            q
        ), f"Got unexpected entry {key=} {row=} {time=} {is_addition=}, expected entries= {self.state!r}"

        entry = q.popleft()
        assert (is_addition, row) == (
            entry.insertion,
            entry.row,
        ), f"Got unexpected entry {key=} {row=} {time=} {is_addition=}, expected entries= {self.state!r}"
        if not q:
            self.state.pop(key)

    def on_end(self):
        assert not self.state, f"Non empty final state = {self.state!r}"


# assert_key_entries_in_stream_consistent verifies for each key, whether:
# - a sequence of updates in the table is a subsequence
# of the sequence of updates defined in expected
# - the final entry for both stream and list is the same
def assert_key_entries_in_stream_consistent(expected: list[DiffEntry], table: pw.Table):
    callback = CheckKeyConsistentInStreamCallback(expected)
    pw.io.subscribe(table, callback, callback.on_end)


def assert_stream_equal(expected: list[DiffEntry], table: pw.Table):
    callback = CheckStreamEntriesEqualityCallback(expected)
    pw.io.subscribe(table, callback, callback.on_end)


def assert_equal_tables(t0: api.CapturedStream, t1: api.CapturedStream) -> None:
    assert api.squash_updates(t0) == api.squash_updates(t1)


def make_value_hashable(val: api.Value):
    if isinstance(val, np.ndarray):
        return (type(val), val.dtype, val.shape, str(val))
    else:
        return val


def make_row_hashable(row: tuple[api.Value, ...]):
    return tuple(make_value_hashable(val) for val in row)


def assert_equal_tables_wo_index(
    s0: api.CapturedStream, s1: api.CapturedStream
) -> None:
    t0 = api.squash_updates(s0)
    t1 = api.squash_updates(s1)
    assert collections.Counter(
        make_row_hashable(row) for row in t0.values()
    ) == collections.Counter(make_row_hashable(row) for row in t1.values())


def assert_equal_streams(t0: api.CapturedStream, t1: api.CapturedStream) -> None:
    def transform(row: api.DataRow):
        t = (row.key,) + tuple(row.values) + (row.time, row.diff)
        return make_row_hashable(t)

    assert collections.Counter(transform(row) for row in t0) == collections.Counter(
        transform(row) for row in t1
    )


def assert_equal_streams_wo_index(
    t0: api.CapturedStream, t1: api.CapturedStream
) -> None:
    def transform(row: api.DataRow):
        t = tuple(row.values) + (row.time, row.diff)
        return make_row_hashable(t)

    assert collections.Counter(transform(row) for row in t0) == collections.Counter(
        transform(row) for row in t1
    )


class CsvLinesNumberChecker:
    def __init__(self, path, n_lines):
        self.path = path
        self.n_lines = n_lines

    def __call__(self):
        try:
            result = pd.read_csv(self.path).sort_index()
        except Exception:
            return False
        print(
            f"Actual (expected) lines number: {len(result)} ({self.n_lines})",
            file=sys.stderr,
        )
        return len(result) == self.n_lines

    def provide_information_on_failure(self):
        if not self.path.exists():
            return f"{self.path} does not exist"
        with open(self.path, "r") as f:
            return f"Final output contents:\n{f.read()}"


class FileLinesNumberChecker:
    def __init__(self, path, n_lines):
        self.path = path
        self.n_lines = n_lines

    def __call__(self):
        if not self.path.exists():
            return False
        n_lines_actual = 0
        with open(self.path, "r") as f:
            for row in f:
                n_lines_actual += 1
        print(
            f"Actual (expected) lines number: {n_lines_actual} ({self.n_lines})",
            file=sys.stderr,
        )
        return n_lines_actual == self.n_lines

    def provide_information_on_failure(self):
        if not self.path.exists():
            return f"{self.path} does not exist"
        with open(self.path, "r") as f:
            return f"Final output contents:\n{f.read()}"


def expect_csv_checker(expected, output_path, usecols=("k", "v"), index_col=("k")):
    expected = (
        pw.debug._markdown_to_pandas(expected)
        .set_index(index_col, drop=False)
        .sort_index()
    )

    def checker():
        try:
            result = (
                pd.read_csv(output_path, usecols=[*usecols, *index_col])
                .convert_dtypes()
                .set_index(index_col, drop=False)
                .sort_index()
            )
        except Exception:
            return False
        return expected.equals(result)

    return checker


@dataclass(frozen=True)
class TestDataSource(datasource.DataSource):
    __test__ = False

    def is_bounded(self) -> bool:
        raise NotImplementedError()

    def is_append_only(self) -> bool:
        return False


def apply_defaults_for_run_kwargs(kwargs):
    kwargs.setdefault("debug", True)
    kwargs.setdefault("monitoring_level", pw.MonitoringLevel.NONE)


def run_graph_and_validate_result(verifier: Callable, assert_schemas=True):
    def inner(table: Table, expected: Table, **kwargs):
        table_schema_dict = table.schema.typehints()
        expected_schema_dict = expected.schema.typehints()
        columns_schema_dict = schema_from_columns(table._columns).typehints()
        if assert_schemas:
            if columns_schema_dict != table_schema_dict:
                raise RuntimeError(
                    f"Output schema validation error, columns {columns_schema_dict} vs table {table_schema_dict}"  # noqa
                )

            if not (
                is_subschema(table.schema, expected.schema)
                and is_subschema(expected.schema, table.schema)
            ):
                raise RuntimeError(
                    f"Output schema validation error, table {table_schema_dict} vs expected {expected_schema_dict}"  # noqa
                )
        else:
            assert columns_schema_dict != table_schema_dict or not (
                is_subschema(table.schema, expected.schema)
                and is_subschema(expected.schema, table.schema)
            ), "wo_types is not needed"

        if list(table.column_names()) != list(expected.column_names()):
            raise RuntimeError(
                f"Mismatched column names, {list(table.column_names())} vs {list(expected.column_names())}"
            )

        apply_defaults_for_run_kwargs(kwargs)
        print("We will do GraphRunner with the following kwargs: ", kwargs)

        [captured_table, captured_expected] = GraphRunner(
            table._source.graph, **kwargs
        ).run_tables(table, expected)
        return verifier(captured_table, captured_expected)

    return inner


def T(*args, format="markdown", **kwargs):
    if format == "pandas":
        return table_from_pandas(*args, **kwargs)
    assert format == "markdown"
    return table_from_markdown(*args, **kwargs)


def remove_ansi_escape_codes(msg: str) -> str:
    """Removes color codes from messages."""
    # taken from https://stackoverflow.com/a/14693789
    return re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])").sub("", msg)


assert_table_equality = run_graph_and_validate_result(assert_equal_tables)

assert_table_equality_wo_index = run_graph_and_validate_result(
    assert_equal_tables_wo_index
)

assert_table_equality_wo_types = run_graph_and_validate_result(
    assert_equal_tables, assert_schemas=False
)

assert_table_equality_wo_index_types = run_graph_and_validate_result(
    assert_equal_tables_wo_index, assert_schemas=False
)

assert_stream_equality = run_graph_and_validate_result(assert_equal_streams)

assert_stream_equality_wo_index = run_graph_and_validate_result(
    assert_equal_streams_wo_index
)

assert_stream_equality_wo_types = run_graph_and_validate_result(
    assert_equal_streams, assert_schemas=False
)

assert_stream_equality_wo_index_types = run_graph_and_validate_result(
    assert_equal_streams_wo_index, assert_schemas=False
)


def run(**kwargs):
    apply_defaults_for_run_kwargs(kwargs)
    pw.run(**kwargs)


def run_all(**kwargs):
    apply_defaults_for_run_kwargs(kwargs)
    pw.run_all(**kwargs)


def wait_result_with_checker(
    checker,
    timeout_sec,
    *,
    step=0.1,
    target=run,
    args=(),
    kwargs={},
):
    try:
        if target is not None:
            assert (
                multiprocessing.get_start_method() == "fork"
            ), "multiprocessing does not use fork(), pw.run() will not work"
            p = multiprocessing.Process(target=target, args=args, kwargs=kwargs)
            p.start()

        succeeded = False
        start_time = time.monotonic()
        while True:
            time.sleep(step)

            elapsed = time.monotonic() - start_time
            if elapsed >= timeout_sec:
                break

            succeeded = checker()
            if succeeded:
                print(
                    f"Correct result obtained after {elapsed:.1f} seconds",
                    file=sys.stderr,
                )
                break

        if not succeeded:
            details = checker.provide_information_on_failure()
            print(f"Checker failed: {details}", file=sys.stderr)
            raise AssertionError(details)
    finally:
        if target is not None:
            if "persistence_config" in kwargs:
                time.sleep(5.0)  # allow a little gap to persist state

            p.terminate()
            p.join()


def write_csv(path: str | pathlib.Path, table_def: str, **kwargs):
    df = _markdown_to_pandas(table_def)
    df.to_csv(path, encoding="utf-8", **kwargs)


def write_lines(path: str | pathlib.Path, data: str | list[str]):
    if isinstance(data, str):
        data = [data]
    data = [row + "\n" for row in data]
    with open(path, "w+") as f:
        f.writelines(data)


def get_aws_s3_settings():
    return pw.io.s3.AwsS3Settings(
        bucket_name="aws-integrationtest",
        access_key=os.environ["AWS_S3_ACCESS_KEY"],
        secret_access_key=os.environ["AWS_S3_SECRET_ACCESS_KEY"],
        region="eu-central-1",
    )


# Callback class for checking whether number of distinct timestamps of
# rows is equal to expected
class CountDifferentTimestampsCallback(pw.io.OnChangeCallback):
    timestamps: set[int]

    def __init__(self, expected: int | None = None):
        self.timestamps = set()
        self.expected = expected

    def __call__(self, key, row, time: int, is_addition):
        self.timestamps.add(time)

    def on_end(self):
        if self.expected is not None:
            assert len(self.timestamps) == self.expected
