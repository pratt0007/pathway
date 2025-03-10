# Copyright © 2024 Pathway

import pytest

import pathway as pw
from pathway.tests.utils import T, assert_table_equality_wo_index


class ValueInstanceSchema(pw.Schema):
    value: int
    instance: int
    is_query: bool


def stream_data() -> tuple[pw.Table, pw.Table]:
    data = T(
        """
           | value | instance | __time__ | __diff__
         2 |   4   |    1     |     1    |     1
         2 |   4   |    1     |     4    |    -1
         5 |   5   |    1     |     5    |     1
         7 |   2   |    2     |     7    |     1
         7 |   2   |    2     |    11    |    -1
        11 |   3   |    2     |    12    |     1
         5 |   5   |    1     |    15    |    -1
        14 |   9   |    1     |    16    |     1
        """
    )
    queries = T(
        """
        value | instance | __time__
          1   |    1     |     0
          2   |    1     |     2
          3   |    1     |     3
          4   |    1     |     6
          5   |    2     |     8
          6   |    1     |     9
          7   |    2     |    10
          8   |    1     |    13
          9   |    2     |    14
        """
    )
    return data, queries


def test_update_old():
    data, queries = stream_data()
    result = queries.join(data, pw.left.instance == pw.right.instance).select(
        query=pw.left.value, ans=pw.right.value
    )
    expected = T(
        """
        query | ans
          1   |  9
          2   |  9
          3   |  9
          4   |  9
          5   |  3
          6   |  9
          7   |  3
          8   |  9
          9   |  3
        """
    )
    assert_table_equality_wo_index(result, expected)


@pytest.mark.parametrize("set_id", [True, False])
def test_asof_now_inner(set_id: bool):
    if set_id:
        id = pw.left.id
    else:
        id = None
    data, queries = stream_data()
    result = queries.asof_now_join(
        data, pw.left.instance == pw.right.instance, id=id
    ).select(query=pw.left.value, ans=pw.right.value)
    expected = T(
        """
        query | ans
          2   |  4
          3   |  4
          4   |  5
          5   |  2
          6   |  5
          7   |  2
          8   |  5
          9   |  3
        """
    )
    if set_id:
        assert result._universe.is_subset_of(queries._universe)
    assert_table_equality_wo_index(result, expected)


@pytest.mark.parametrize("set_id", [True, False])
def test_asof_now_left(set_id: bool):
    if set_id:
        id = pw.left.id
    else:
        id = None
    data, queries = stream_data()
    result = queries.asof_now_join_left(
        data, pw.left.instance == pw.right.instance, id=id
    ).select(query=pw.left.value, ans=pw.right.value)
    expected = T(
        """
        query | ans
          1   |
          2   |  4
          3   |  4
          4   |  5
          5   |  2
          6   |  5
          7   |  2
          8   |  5
          9   |  3
        """
    )
    if set_id:
        assert result._universe == queries._universe
    assert_table_equality_wo_index(result, expected)
