# Copyright © 2024 Pathway

import os
import pathlib
import threading
import time

import pytest
import requests

import pathway as pw
from pathway.tests.utils import (
    CsvLinesNumberChecker,
    expect_csv_checker,
    wait_result_with_checker,
)


def test_server(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10000
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        query: str
        user: str

    def logic(queries: pw.Table) -> pw.Table:
        return queries.select(
            query_id=queries.id, result=pw.apply(lambda x: x.upper(), pw.this.query)
        )

    def target():
        time.sleep(5)
        r = requests.post(
            f"http://127.0.0.1:{port}",
            json={"query": "one", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"ONE"', r.text
        r = requests.post(
            f"http://127.0.0.1:{port}",
            json={"query": "two", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"TWO"', r.text

    queries, response_writer = pw.io.http.rest_connector(
        host="127.0.0.1", port=port, schema=InputSchema, delete_completed_queries=True
    )
    responses = logic(queries)
    response_writer(responses)
    pw.io.csv.write(queries, output_path)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    wait_result_with_checker(CsvLinesNumberChecker(output_path, 4), 30)


def test_server_customization(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10001
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        query: str
        user: str

    def logic(queries: pw.Table) -> pw.Table:
        return queries.select(
            query_id=queries.id, result=pw.apply(lambda x: x.upper(), pw.this.query)
        )

    def target():
        time.sleep(5)
        requests.post(
            f"http://127.0.0.1:{port}/endpoint?user=sergey",
            json={"query": "one"},
        ).raise_for_status()
        requests.post(
            f"http://127.0.0.1:{port}/endpoint?user=sergey",
            json={"query": "two"},
        ).raise_for_status()

    queries, response_writer = pw.io.http.rest_connector(
        host="127.0.0.1",
        port=port,
        schema=InputSchema,
        route="/endpoint",
        delete_completed_queries=True,
    )
    responses = logic(queries)
    response_writer(responses)
    pw.io.csv.write(queries, output_path)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    wait_result_with_checker(CsvLinesNumberChecker(output_path, 4), 30)


def test_server_schema_customization(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10002
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        query: str
        user: str = pw.column_definition(default_value="manul")

    def logic(queries: pw.Table) -> pw.Table:
        return queries.select(
            query_id=queries.id, result=pw.apply(lambda x: x.upper(), pw.this.query)
        )

    def target():
        time.sleep(5)
        requests.post(
            f"http://127.0.0.1:{port}/",
            json={"query": "one"},
        ).raise_for_status()
        requests.post(
            f"http://127.0.0.1:{port}/",
            json={"query": "two"},
        ).raise_for_status()

    queries, response_writer = pw.io.http.rest_connector(
        host="127.0.0.1", port=port, schema=InputSchema, delete_completed_queries=True
    )
    responses = logic(queries)
    response_writer(responses)
    pw.io.csv.write(queries, output_path)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    wait_result_with_checker(CsvLinesNumberChecker(output_path, 4), 30)


def test_server_keep_queries(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10003
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        k: int
        v: int

    def target():
        time.sleep(5)
        requests.post(
            f"http://127.0.0.1:{port}/",
            json={"k": 1, "v": 1},
        ).raise_for_status()
        requests.post(
            f"http://127.0.0.1:{port}/",
            json={"k": 1, "v": 2},
        ).raise_for_status()

    queries, response_writer = pw.io.http.rest_connector(
        host="127.0.0.1", port=port, schema=InputSchema, delete_completed_queries=False
    )
    response_writer(queries.select(query_id=queries.id, result=pw.this.v))

    sum = queries.groupby(pw.this.k).reduce(
        key=pw.this.k, sum=pw.reducers.sum(pw.this.v)
    )

    pw.io.csv.write(sum, output_path)

    t = threading.Thread(target=target, daemon=True)
    t.start()

    wait_result_with_checker(
        expect_csv_checker(
            """
            key | sum    | diff
            1   | 1      | 1
            1   | 1      | -1
            1   | 3      | 1
            """,
            output_path,
            usecols=["sum", "diff"],
            index_col=["key"],
        ),
        10,
    )


def test_server_fail_on_duplicate_port(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10003
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        k: int
        v: int

    queries, response_writer = pw.io.http.rest_connector(
        host="127.0.0.1", port=port, schema=InputSchema, delete_completed_queries=False
    )
    response_writer(queries.select(query_id=queries.id, result=pw.this.v))

    queries_dup, response_writer_dup = pw.io.http.rest_connector(
        host="127.0.0.1", port=port, schema=InputSchema, delete_completed_queries=False
    )
    response_writer_dup(queries_dup.select(query_id=queries_dup.id, result=pw.this.v))

    sum = queries.groupby(pw.this.k).reduce(
        key=pw.this.k, sum=pw.reducers.sum(pw.this.v)
    )
    sum_dup = queries_dup.groupby(pw.this.k).reduce(
        key=pw.this.k, sum=pw.reducers.sum(pw.this.v)
    )

    pw.io.csv.write(sum, output_path)
    pw.io.csv.write(sum_dup, output_path)

    with pytest.raises(RuntimeError, match="error while attempting to bind on address"):
        pw.run()


def test_server_two_endpoints(tmp_path: pathlib.Path):
    port = int(os.environ.get("PATHWAY_MONITORING_HTTP_PORT", "20000")) + 10004
    output_path = tmp_path / "output.csv"

    class InputSchema(pw.Schema):
        query: str
        user: str

    def uppercase_logic(queries: pw.Table) -> pw.Table:
        return queries.select(
            query_id=queries.id, result=pw.apply(lambda x: x.upper(), pw.this.query)
        )

    def duplicate_logic(queries: pw.Table) -> pw.Table:
        return queries.select(
            query_id=queries.id, result=pw.apply(lambda x: x + x, pw.this.query)
        )

    def target():
        time.sleep(5)
        r = requests.post(
            f"http://127.0.0.1:{port}/duplicate",
            json={"query": "one", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"oneone"', r.text
        r = requests.post(
            f"http://127.0.0.1:{port}/duplicate",
            json={"query": "two", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"twotwo"', r.text
        r = requests.post(
            f"http://127.0.0.1:{port}/uppercase",
            json={"query": "one", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"ONE"', r.text
        r = requests.post(
            f"http://127.0.0.1:{port}/uppercase",
            json={"query": "two", "user": "sergey"},
        )
        r.raise_for_status()
        assert r.text == '"TWO"', r.text

    webserver = pw.io.http.PathwayWebserver(host="127.0.0.1", port=port)

    uppercase_queries, uppercase_response_writer = pw.io.http.rest_connector(
        webserver=webserver,
        schema=InputSchema,
        route="/uppercase",
        delete_completed_queries=True,
    )
    uppercase_responses = uppercase_logic(uppercase_queries)
    uppercase_response_writer(uppercase_responses)

    duplicate_queries, duplicate_response_writer = pw.io.http.rest_connector(
        webserver=webserver,
        schema=InputSchema,
        route="/duplicate",
        delete_completed_queries=True,
    )
    duplicate_responses = duplicate_logic(duplicate_queries)
    duplicate_response_writer(duplicate_responses)

    pw.universes.promise_are_pairwise_disjoint(uppercase_queries, duplicate_queries)
    all_queries = uppercase_queries.concat(duplicate_queries)

    pw.io.csv.write(all_queries, output_path)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    wait_result_with_checker(CsvLinesNumberChecker(output_path, 8), 30)
