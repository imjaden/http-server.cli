# -*- coding: utf-8 -*-
"""
HistoryStore 模块测试 — OpenSpec: history
"""

import json
import os

import pytest

from http_server_cli.history import HistoryStore
import http_server_cli.utils as hs_utils


def _history_path():
    return hs_utils.HISTORY_PATH


class TestHistoryStore:
    """HistoryStore 基本操作"""

    def test_empty(self):
        store = HistoryStore()
        store.clear()
        assert store.records() == []

    def test_add_record(self):
        store = HistoryStore()
        store.clear()
        store.add(port=8080, path='/tmp/foo', started_at='2026-06-20T10:00:00')
        records = store.records()
        assert len(records) == 1
        assert records[0]['port'] == 8080
        assert records[0]['path'] == '/tmp/foo'
        assert records[0]['started_at'] == '2026-06-20T10:00:00'

    def test_close_updates_ended_at(self):
        store = HistoryStore()
        store.clear()
        store.add(port=8080, path='/tmp/foo', started_at='2026-06-20T10:00:00')
        store.close(port=8080, path='/tmp/foo')
        records = store.records()
        assert records[0]['ended_at'] is not None
        assert records[0]['ended_at'] != ''

    def test_persist_to_disk(self):
        store = HistoryStore()
        store.clear()
        store.add(port=8080, path='/tmp/foo', started_at='2026-06-20T10:00:00')
        # 重新加载应读到同一数据
        store2 = HistoryStore()
        assert len(store2.records()) == 1
        assert store2.records()[0]['port'] == 8080

    def test_clear(self):
        store = HistoryStore()
        store.add(port=8080, path='/tmp/foo', started_at='2026-06-20T10:00:00')
        store.clear()
        assert store.records() == []

    def test_multiple_records(self):
        store = HistoryStore()
        store.clear()
        store.add(port=8081, path='/tmp/a', started_at='2026-06-20T10:00:00')
        store.add(port=8082, path='/tmp/b', started_at='2026-06-20T10:05:00')
        assert len(store.records()) == 2
