# -*- coding: utf-8 -*-
"""
Config 模块测试 — OpenSpec: cfg-01 ~ cfg-04
"""

import json
import os

import pytest

from http_server_cli.config import Config, DEFAULT_CONFIG
# 不直接 import CONFIG_PATH（conftest 会 patch），而是通过模块属性访问
import http_server_cli.utils as hs_utils

def _config_path():
    """获取当前测试隔离的 CONFIG_PATH"""
    return hs_utils.CONFIG_PATH

pytestmark = pytest.mark.spec("configuration")

class TestConfigDefaults:
    """cfg-01: 默认配置"""

    def test_default_port(self, fresh_config):
        assert fresh_config.port == DEFAULT_CONFIG['port']

    def test_default_domain(self, fresh_config):
        assert fresh_config.domain == DEFAULT_CONFIG['domain']

    def test_to_dict_includes_all_keys(self, fresh_config):
        d = fresh_config.to_dict()
        assert 'port' in d
        assert 'domain' in d

class TestConfigPersistence:
    """cfg-02/03: 配置修改持久化"""

    def test_set_port_persists(self, fresh_config):
        """cfg-02: set port 应持久化"""
        fresh_config.set_port(3000)
        assert fresh_config.port == 3000
        with open(_config_path(), 'r') as f:
            on_disk = json.load(f)
        assert on_disk['port'] == 3000

    def test_set_domain_persists(self, fresh_config):
        """cfg-03: set domain 应持久化"""
        fresh_config.set_domain('0.0.0.0')
        assert fresh_config.domain == '0.0.0.0'
        with open(_config_path(), 'r') as f:
            on_disk = json.load(f)
        assert on_disk['domain'] == '0.0.0.0'

    def test_config_reload_from_disk(self, fresh_config):
        """新 Config 实例应读取已持久化的值"""
        fresh_config.set_port(7070)
        fresh_config.set_domain('127.0.0.1')
        new_config = Config()
        assert new_config.port == 7070
        assert new_config.domain == '127.0.0.1'

    def test_set_port_validates_range(self, fresh_config):
        fresh_config.set_port(3000)
        assert fresh_config.port == 3000
        fresh_config.set_port(65535)
        assert fresh_config.port == 65535

    def test_config_show_does_not_raise(self, fresh_config, capsys):
        fresh_config.show()
        captured = capsys.readouterr()
        assert 'port' in captured.out

    def test_config_show_json_output(self, fresh_config, capsys):
        fresh_config.show(json=True)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result['success'] is True
        assert result['command'] == 'config'
        assert result['data']['port'] == 8080
        assert result['data']['domain'] == 'localhost'
        assert 'data_dir' in result['data']
        assert result['error'] is None

class TestConfigCornerCases:
    """cfg-04: 损坏/丢失保护"""

    def test_missing_config_file(self, monkeypatch):
        """cfg-04: 配置文件不存在时 fallback 到默认值"""
        monkeypatch.setattr('http_server_cli.config.CONFIG_PATH', '/nonexistent/config.json')
        c = Config()
        assert c.port == 8080
        assert c.domain == 'localhost'

    def test_corrupted_config_file(self, fresh_config):
        """cfg-04: 损坏 JSON 不应崩溃"""
        with open(_config_path(), 'w') as f:
            f.write('{broken json!!!')
        c = Config()
        assert c.port == DEFAULT_CONFIG['port']
