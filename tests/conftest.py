# -*- coding: utf-8 -*-
"""
pytest 全局夹具

关键设计：由于各模块通过 `from http_server_cli.utils import XXX` 按值导入
常量/函数，monkeypatch 必须同时打在 **源模块** 和 **每个消费者模块** 上。
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pytest

def _patch_consumer(monkeypatch, target, attr, value):
    """
    在目标模块上打补丁。由于 `from X import Y` 按值绑定，
    需要同时 patch 源模块和所有消费模块。
    """
    monkeypatch.setattr(f'http_server_cli.{target}', value)

@pytest.fixture(autouse=True)
def _isolate_data_dir(monkeypatch):
    """
    自动为每个测试创建隔离的临时数据目录，
    同时 patch 所有可能导入 CONFIG_PATH / REGISTRY_PATH / LOG_DIR / DATA_DIR 的模块。
    """
    tmp = tempfile.mkdtemp(prefix='hs_test_')
    cfg_path = os.path.join(tmp, 'config.json')
    reg_path = os.path.join(tmp, 'registry.json')
    log_dir = os.path.join(tmp, 'logs')

    # utils 模块（定义源）
    monkeypatch.setattr('http_server_cli.utils.DATA_DIR', tmp)
    monkeypatch.setattr('http_server_cli.utils.CONFIG_PATH', cfg_path)
    monkeypatch.setattr('http_server_cli.utils.REGISTRY_PATH', reg_path)
    monkeypatch.setattr('http_server_cli.utils.LOG_DIR', log_dir)

    # config 模块（from utils import CONFIG_PATH）
    monkeypatch.setattr('http_server_cli.config.CONFIG_PATH', cfg_path)

    # registry 模块（from utils import REGISTRY_PATH）
    monkeypatch.setattr('http_server_cli.registry.REGISTRY_PATH', reg_path)

    # server 模块（from utils import LOG_DIR）
    monkeypatch.setattr('http_server_cli.server.LOG_DIR', log_dir)

    # bookmark 模块（from utils import BOOKMARKS_PATH）
    monkeypatch.setattr('http_server_cli.bookmark.BOOKMARKS_PATH',
                        os.path.join(tmp, 'bookmarks.json'))

    os.makedirs(log_dir, exist_ok=True)
    yield
    shutil.rmtree(tmp, ignore_errors=True)

@pytest.fixture
def fresh_config():
    """返回一个干净的 Config 实例（自动写入默认值）"""
    from http_server_cli.config import Config
    return Config()

@pytest.fixture
def fresh_registry():
    """返回一个空的 Registry 实例"""
    from http_server_cli.registry import Registry
    return Registry()

@pytest.fixture
def pre_filled_registry():
    """预填充 2 条记录的 Registry"""
    from http_server_cli.registry import Registry
    reg = Registry()
    reg.add(port=8081, path='/tmp/project-alpha', pid=10001, domain='localhost')
    reg.add(port=8082, path='/tmp/project-beta', pid=10002, domain='0.0.0.0')
    return reg

@pytest.fixture
def temp_project():
    """创建一个临时项目目录，内含 index.html"""
    tmp = tempfile.mkdtemp(prefix='hs_project_')
    Path(tmp, 'index.html').write_text('<h1>Hello</h1>')
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)
