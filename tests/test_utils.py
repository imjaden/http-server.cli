# -*- coding: utf-8 -*-
"""
Utils 模块测试 — OpenSpec: cfg-01(ensure_storage), res-03(format_duration)
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from http_server_cli.utils import (
    format_path,
    get_process_info,
    json_output,
    read_json,
    write_json,
    resolve_path,
    timestamp,
    ensure_storage,
    format_duration,
    get_process_stats,
)
import http_server_cli.utils as hs_utils

def _data_dir():
    return hs_utils.DATA_DIR

def _config_path():
    return hs_utils.CONFIG_PATH

def _registry_path():
    return hs_utils.REGISTRY_PATH

def _log_dir():
    return hs_utils.LOG_DIR

class TestFormatPath:
    """路径格式化"""

    def test_expands_home(self):
        path = os.path.expanduser('~') + '/CodeSpace/foo'
        result = format_path(path)
        assert result.startswith('~')

    def test_relative_path(self):
        assert format_path('/tmp/foo') == '/tmp/foo'

    def test_none_path(self):
        assert format_path(None) == 'None'

class TestJsonIO:
    """JSON 安全读写"""

    def test_write_and_read(self):
        path = os.path.join(_data_dir(), 'test.json')
        data = {'key': 'value', 'num': 42}
        write_json(path, data)
        loaded = read_json(path)
        assert loaded == data

    def test_read_missing_file(self):
        loaded = read_json('/nonexistent/path.json')
        assert loaded == {}

    def test_read_corrupted_json(self):
        path = os.path.join(_data_dir(), 'broken.json')
        with open(path, 'w') as f:
            f.write('NOT JSON {{{')
        loaded = read_json(path)
        assert loaded == {}

    def test_write_creates_directory(self):
        deep = os.path.join(_data_dir(), 'a', 'b', 'c', 'deep.json')
        write_json(deep, {'ok': True})
        assert os.path.exists(deep)
        loaded = read_json(deep)
        assert loaded == {'ok': True}

class TestResolvePath:
    """路径解析"""

    def test_resolve_relative(self):
        abs_path = resolve_path('.')
        assert os.path.isabs(abs_path)

    def test_resolve_absolute(self):
        resolved = resolve_path('/tmp')
        assert resolved == os.path.realpath('/tmp')

    def test_resolve_home(self):
        resolved = resolve_path('~')
        assert resolved == os.path.expanduser('~')

class TestTimestamp:
    def test_format(self):
        ts = timestamp()
        assert len(ts) == 19
        assert 'T' in ts

class TestEnsureStorage:
    """数据目录初始化"""

    def test_creates_dirs_and_files(self):
        import shutil
        shutil.rmtree(_data_dir(), ignore_errors=True)
        assert not os.path.exists(_data_dir())

        ensure_storage()

        assert os.path.isdir(_log_dir())
        assert os.path.isfile(_config_path())
        assert os.path.isfile(_registry_path())

    def test_creates_valid_default_config(self):
        import shutil
        shutil.rmtree(_data_dir(), ignore_errors=True)
        ensure_storage()

        config = read_json(_config_path())
        assert config['port'] == 8080
        assert config['domain'] == 'localhost'

    def test_creates_empty_registry(self):
        import shutil
        shutil.rmtree(_data_dir(), ignore_errors=True)
        ensure_storage()

        reg = read_json(_registry_path())
        assert reg == {'servers': []}


class TestFormatDuration:
    """时长格式化 — OpenSpec: res-03"""

    def test_minutes(self):
        from datetime import datetime, timedelta
        # 5分钟前的时间戳
        start_time = datetime.now() - timedelta(minutes=5)
        started_at = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        assert format_duration(started_at) == '5分钟'

    def test_hours(self):
        from datetime import datetime, timedelta
        # 2小时前的时间戳
        start_time = datetime.now() - timedelta(hours=2)
        started_at = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        assert format_duration(started_at) == '2小时'

    def test_days(self):
        from datetime import datetime, timedelta
        # 1天前的时间戳
        start_time = datetime.now() - timedelta(days=1)
        started_at = start_time.strftime('%Y-%m-%dT%H:%M:%S')
        assert format_duration(started_at) == '24小时'

    def test_empty_string(self):
        assert format_duration('') == '-'

    def test_dash(self):
        assert format_duration('-') == '-'


class TestGetProcessStats:
    """进程资源监控 — OpenSpec: res-01, res-02"""

    def test_returns_dict(self):
        info = get_process_stats(os.getpid())
        assert isinstance(info, dict)
        assert 'cpu' in info
        assert 'memory' in info

    def test_invalid_pid_returns_dash(self):
        info = get_process_stats(999999)
        assert info['cpu'] == '-'
        assert info['memory'] == '-'


class TestGetProcessInfo:
    """进程信息查询（用于非本工具服务诊断）"""

    def test_returns_info_for_self(self):
        """查询当前进程应返回 user 和 command"""
        info = get_process_info(os.getpid())
        assert info is not None
        assert 'user' in info
        assert 'command' in info
        # 当前进程的 command 应包含 pytest 或 python
        assert any(x in info['command'] for x in ('pytest', 'python'))

    def test_returns_none_for_dead_pid(self):
        """无效 PID 应返回 None"""
        info = get_process_info(9999999)
        assert info is None

    def test_returns_none_for_none(self):
        """None PID 应返回 None"""
        info = get_process_info(0)
        assert info is None


class TestJsonOutput:
    """json_output 统一信封输出"""

    def test_success_with_data(self, capsys):
        json_output(True, 'test-cmd', data={'key': 'value', 'num': 42})
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'test-cmd'
        assert result['data'] == {'key': 'value', 'num': 42}
        assert result['error'] is None

    def test_error_without_data(self, capsys):
        json_output(False, 'test-cmd', error='something went wrong')
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is False
        assert result['command'] == 'test-cmd'
        assert result['data'] is None
        assert result['error'] == 'something went wrong'

    def test_success_none_data(self, capsys):
        json_output(True, 'test-cmd')
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['data'] is None
        assert result['error'] is None

    def test_output_is_valid_json(self, capsys):
        json_output(True, 'cmd', data={'nested': {'a': [1, 2]}})
        captured = capsys.readouterr()
        # 应能被 json.loads 成功解析
        result = json.loads(captured.out)
        assert result['data']['nested']['a'] == [1, 2]

    def test_ensure_ascii_false(self, capsys):
        """中文内容不应被转义"""
        json_output(True, 'test', data={'msg': '路径不存在'})
        captured = capsys.readouterr()
        assert '\\u' not in captured.out
        assert '路径不存在' in captured.out
