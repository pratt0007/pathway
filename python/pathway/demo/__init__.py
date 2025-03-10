# Copyright © 2024 Pathway

"""Pathway demo module

Typical use:

>>> class InputSchema(pw.Schema):
...    name: str
...    age: int
>>> pw.demo.replay_csv("./input_stream.csv", schema=InputSchema)
<pathway.Table schema={'name': <class 'str'>, 'age': <class 'int'>}>
"""

from __future__ import annotations

import csv
import time
from datetime import datetime
from os import PathLike
from typing import Any

import pathway as pw


def generate_custom_stream(
    value_generators: dict[str, Any],
    *,
    schema: type[pw.Schema],
    nb_rows: int | None = None,
    autocommit_duration_ms: int = 1000,
    input_rate: float = 1.0,
    persistent_id: str | None = None,
) -> pw.Table:
    """Generates a data stream.

    The generator creates a table and periodically streams rows.
    If a ``nb_rows`` value is provided, there are ``nb_rows`` row generated in total,
    else the generator streams indefinitely.
    The rows are generated iteratively and have an associated index x, starting from 0.
    The values of each column are generated by their associated function in ``value_generators``.

    Args:
        value_generators: Dictionary mapping column names to functions that generate values for each column.
        schema: Schema of the resulting table.
        nb_rows: The number of rows to generate. Defaults to None. If set to None, the generator
          generates streams indefinitely.
        types: Dictionary containing the mapping between the columns and the data \
types (``pw.Type``) of the values of those columns. This parameter is optional, and if not \
provided the default type is ``pw.Type.ANY``.
        autocommit_duration_ms: the maximum time between two commits. Every
          autocommit_duration_ms milliseconds, the updates received by the connector are
          committed and pushed into Pathway's computation graph.
        input_rate: The rate at which rows are generated per second. Defaults to 1.0.

    Returns:
        Table: The generated table.

    Example:

    >>> value_functions = {
    ...     'number': lambda x: x + 1,
    ...     'name': lambda x: f'Person {x}',
    ...     'age': lambda x: 20 + x,
    ... }
    >>> class InputSchema(pw.Schema):
    ...      number: int
    ...      name: str
    ...      age: int
    >>> pw.demo.generate_custom_stream(value_functions, schema=InputSchema, nb_rows=10)
    <pathway.Table schema={'number': <class 'int'>, 'name': <class 'str'>, 'age': <class 'int'>}>

    In the above example, a data stream is generated with 10 rows, where each row has columns \
        'number', 'name', and 'age'.
    The 'number' column contains values incremented by 1 from 1 to 10, the 'name' column contains 'Person'
    followed by the respective row index, and the 'age' column contains values starting from 20 incremented by
    the row index.
    """

    if nb_rows is not None and nb_rows < 0:
        raise ValueError(
            "demo.generate_custom_stream error: nb_rows should be None or strictly positive."
        )

    class FileStreamSubject(pw.io.python.ConnectorSubject):
        def run(self):
            def _get_row(i):
                row = {}
                for name, fun in value_generators.items():
                    row[name] = fun(i)
                return row

            if nb_rows is None:
                row_index = 0
                while True:
                    self.next_json(_get_row(row_index))
                    row_index = row_index + 1
                    time.sleep(1.0 / input_rate)
            else:
                for row_index in range(nb_rows):
                    self.next_json(_get_row(row_index))
                    time.sleep(1.0 / input_rate)

    table = pw.io.python.read(
        FileStreamSubject(),
        schema=schema,
        format="json",
        autocommit_duration_ms=autocommit_duration_ms,
        persistent_id=persistent_id,
    )

    return table


def noisy_linear_stream(nb_rows: int = 10, input_rate: float = 1.0) -> pw.Table:
    """
    Generates an artificial data stream for the linear regression tutorial.

    Args:
        nb_rows (int, optional): The number of rows to generate in the data stream. Defaults to 10.
        input_rate (float, optional): The rate at which rows are generated per second. Defaults to 1.0.

    Returns:
        pw.Table: A table containing the generated data stream.

    Example:

    >>> table = pw.demo.noisy_linear_stream(nb_rows=100, input_rate=2.0)

    In the above example, an artificial data stream is generated with 100 rows. Each row has two columns, 'x' and 'y'.
    The 'x' values range from 0 to 99, and the 'y' values are equal to 'x' plus some random noise.
    """
    if nb_rows < 0:
        raise ValueError(
            "demo.noisy_linear_stream error: nb_rows should be strictly positive."
        )
    import random

    random.seed(0)

    def _get_value(i):
        return float(i + (2 * random.random() - 1) / 10)

    class InputSchema(pw.Schema):
        x: float = pw.column_definition(primary_key=True)
        y: float

    value_generators = {
        "x": (lambda x: float(x)),
        "y": _get_value,
    }
    autocommit_duration_ms = 1000
    return generate_custom_stream(
        value_generators=value_generators,
        schema=InputSchema,
        autocommit_duration_ms=autocommit_duration_ms,
        nb_rows=nb_rows,
        input_rate=input_rate,
    )


def range_stream(
    nb_rows: int = 30, offset: int = 0, input_rate: float = 1.0
) -> pw.Table:
    """
    Generates a simple artificial data stream, used to compute the sum in our examples.

    Args:
        nb_rows (int, optional): The number of rows to generate in the data stream. Defaults to 30.
        offset (int, optional): The offset value added to the generated 'value' column. Defaults to 0.
        input_rate (float, optional): The rate at which rows are generated per second. Defaults to 1.0.

    Returns:
        pw.Table: a table containing the generated data stream.

    Example:

    >>> table = pw.demo.range_stream(nb_rows=50, offset=10, input_rate=2.5)

    In the above example, an artificial data stream is generated with a single column 'value' and 50 rows.
    The 'value' column contains values ranging from 'offset' (10 in this case) to 'nb_rows' + 'offset' (60).
    """
    if nb_rows < 0:
        raise ValueError(
            "demo.range_stream error: nb_rows should be strictly positive."
        )

    class InputSchema(pw.Schema):
        value: float

    value_generators = {
        "value": (lambda x: float(x + offset)),
    }
    autocommit_duration_ms = 1000
    return generate_custom_stream(
        value_generators=value_generators,
        schema=InputSchema,
        autocommit_duration_ms=autocommit_duration_ms,
        nb_rows=nb_rows,
        input_rate=input_rate,
    )


def replay_csv(
    path: str | PathLike,
    *,
    schema: type[pw.Schema],
    input_rate: float = 1.0,
) -> pw.Table:
    """Replay a static CSV files as a data stream.

    Args:
        path: Path to the file to stream.
        schema: Schema of the resulting table.
        autocommit_duration_ms: the maximum time between two commits. Every
            autocommit_duration_ms milliseconds, the updates received by the connector are
            committed and pushed into Pathway's computation graph.
        input_rate (float, optional): The rate at which rows are read per second. Defaults to 1.0.

    Returns:
        Table: The table read.

    Note: the CSV files should follow a standard CSV settings. The separator is ',', the
    quotechar is '"', and there is no escape.

    """

    autocommit_ms = int(1000.0 / input_rate)

    columns = set(schema.column_names())

    class FileStreamSubject(pw.io.python.ConnectorSubject):
        def run(self):
            with open(path, newline="") as csvfile:
                csvreader = csv.DictReader(csvfile)
                for row in csvreader:
                    values = {key: row[key] for key in columns}
                    self.next_json(values)
                    time.sleep(1.0 / input_rate)

    return pw.io.python.read(
        FileStreamSubject(),
        schema=schema.update_types(**{name: str for name in schema.column_names()}),
        autocommit_duration_ms=autocommit_ms,
        format="json",
    ).cast_to_types(**schema.typehints())


def replay_csv_with_time(
    path: str,
    *,
    schema: type[pw.Schema],
    time_column: str,
    unit: str = "s",
    autocommit_ms: int = 100,
    speedup: float = 1,
) -> pw.Table:
    """
    Replay a static CSV files as a data stream while respecting the time between updated based on a timestamp columns.
    The timestamps in the file should be ordered positive integers.

    Args:
        path: Path to the file to stream.
        schema: Schema of the resulting table.
        time_column: Column containing the timestamps.
        unit: Unit of the timestamps. Only 's', 'ms', 'us', and 'ns' are supported. Defaults to 's'.
        autocommit_duration_ms: the maximum time between two commits. Every
          autocommit_duration_ms milliseconds, the updates received by the connector are
          committed and pushed into Pathway's computation graph.
        speedup: Produce stream `speedup` times faster than it would result from the time column.

    Returns:
        Table: The table read.

    Note: the CSV files should follow a standard CSV settings. The separator is ',', the
    quotechar is '"', and there is no escape.

    """

    time_column_type = schema.typehints().get(time_column, None)
    if time_column_type != int and time_column_type != float:
        raise ValueError("Invalid schema. Time columns must be int or float.")

    if unit not in ["s", "ms", "us", "ns"]:
        raise ValueError(
            "demo.replay_csv_with_time: unit should be either 's', 'ms, 'us', or 'ns'."
        )

    unit_factor = 1
    match unit:
        case "ms":
            unit_factor = 1000
        case "us":
            unit_factor = 1_000_000
        case "ns":
            unit_factor = 1_000_000_000
        case _:
            unit_factor = 1
    speedup *= unit_factor

    columns = set(schema.column_names())

    class FileStreamSubject(pw.io.python.ConnectorSubject):
        def run(self):
            with open(path, newline="") as csvfile:
                csvreader = csv.DictReader(csvfile)
                firstrow = next(iter(csvreader))
                values = {key: firstrow[key] for key in columns}
                first_time_value = float(values[time_column])
                real_start_time = datetime.now().timestamp()
                self.next_json(values)

                for row in csvreader:
                    values = {key: row[key] for key in columns}
                    current_value = float(values[time_column])
                    expected_time_from_start = current_value - first_time_value
                    expected_time_from_start /= speedup
                    real_time_from_start = datetime.now().timestamp() - real_start_time
                    tts = expected_time_from_start - real_time_from_start
                    if tts > 0:
                        time.sleep(tts)
                    self.next_json(values)

    return pw.io.python.read(
        FileStreamSubject(),
        schema=schema.update_types(**{name: str for name in schema.column_names()}),
        autocommit_duration_ms=autocommit_ms,
        format="json",
    ).cast_to_types(**schema.typehints())
