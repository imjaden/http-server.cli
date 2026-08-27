# -*- coding: utf-8 -*-
"""
Web 服务注册持久化存储：ServiceStore。

与 BookmarkStore 的区别：bookmark 绑定静态目录路径（hs start 专用），
ServiceStore 绑定任意 CLI 启动命令（跨项目 web 服务，如 dk server start）。

用法:
    store = ServiceStore()
    store.add('daily.checker', cmd='dk server start --daemon --open',
              url='http://127.0.0.1:5001', open_mode='url')
    svc = store.get('daily.checker')
"""

import os
import re
from typing import Optional

from http_server_cli.utils import (
    SERVICES_PATH, read_json, write_json, timestamp,
)

MAX_SERVICE_NAME_LEN = 128
_SERVICE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*$')
VALID_OPEN_MODES = ('cmd', 'url', 'both', 'none')


class DataCorruptionError(RuntimeError):
    """服务注册文件损坏异常。"""
    pass


class ServiceStore:
    """Web 服务注册持久化存储。

    存储文件: ~/.http-server.cli/services.json
    名称唯一约束: 不同 name 不可重复。
    损坏检测: 非空文件 JSON 解析失败抛出 DataCorruptionError。
    """

    def __init__(self) -> None:
        self._path = SERVICES_PATH
        self._ensure_file()

    # ── 内部 I/O ──

    def _ensure_file(self) -> None:
        if not os.path.exists(self._path):
            write_json(self._path, {'services': []})

    def _read_all(self) -> list:
        """读取所有注册。损坏文件抛出 DataCorruptionError。

        损坏覆盖三类: ①非空文件 JSON 语法错; ②合法 JSON 但非 dict; ③services 字段非 list。
        """
        raw = read_json(self._path)
        if not raw and os.path.getsize(self._path) > 0:
            raise DataCorruptionError(
                f'{self._path} is corrupted. '
                f'Please check the file or restore from backup.'
            )
        if not raw:
            return []
        if not isinstance(raw, dict) or not isinstance(raw.get('services'), list):
            raise DataCorruptionError(
                f'{self._path} has invalid shape '
                f'(expected {{"services": [...]}}). '
                f'Please check the file or restore from backup.'
            )
        return raw.get('services', [])

    def _write_all(self, services: list) -> None:
        write_json(self._path, {'services': services})

    # ── 校验 ──

    @staticmethod
    def validate_name(name: str) -> Optional[str]:
        """校验服务名。返回错误消息或 None。

        >>> ServiceStore.validate_name('daily.checker')
        >>> ServiceStore.validate_name('')
        'service name cannot be empty'
        """
        if not name:
            return 'service name cannot be empty'
        if len(name) > MAX_SERVICE_NAME_LEN:
            return f'service name exceeds {MAX_SERVICE_NAME_LEN} characters'
        if not _SERVICE_NAME_RE.match(name):
            return 'service name must match [a-zA-Z0-9][a-zA-Z0-9._-]*'
        return None

    @staticmethod
    def validate_cmd(cmd: str) -> Optional[str]:
        """校验启动命令非空。返回错误消息或 None。"""
        if not cmd or not cmd.strip():
            return 'service cmd cannot be empty'
        return None

    @staticmethod
    def validate_open_mode(mode: str) -> Optional[str]:
        """校验 open 策略。返回错误消息或 None。"""
        if mode not in VALID_OPEN_MODES:
            return f"open mode must be one of: {', '.join(VALID_OPEN_MODES)}"
        return None

    @staticmethod
    def validate_url(url: Optional[str]) -> Optional[str]:
        """校验 url 格式（http/https 完整 URL）。返回错误消息或 None。"""
        if not url:
            return None
        if not re.match(r'^https?://', url):
            return 'url must start with http:// or https://'
        return None

    # ── CRUD ──

    def add(self, name: str, cmd: str, url: Optional[str] = None,
            open_mode: str = 'url', use_domain: bool = False,
            force: bool = False) -> None:
        """添加注册。

        force=True 时覆盖同名旧条目。
        url 归一化: '' 与 None 等价（动态端口服务不填）。
        use_domain=True 时执行注入 config.domain 到 cmd 末尾（--domain "<domain>"）。

        Raises:
            ValueError: name 已存在；或 cmd/open_mode 非法。
        """
        err = self.validate_name(name)
        if err:
            raise ValueError(err)
        err = self.validate_cmd(cmd)
        if err:
            raise ValueError(err)
        err = self.validate_open_mode(open_mode)
        if err:
            raise ValueError(err)
        err = self.validate_url(url)
        if err:
            raise ValueError(err)

        services = self._read_all()
        if any(s['name'] == name for s in services):
            if not force:
                raise ValueError(f"service '{name}' already exists")
            services = [s for s in services if s['name'] != name]
        services.append({
            'name': name,
            'cmd': cmd,
            'url': url or None,
            'open': open_mode,
            'use_domain': bool(use_domain),
            'created_at': timestamp(),
        })
        self._write_all(services)

    def remove(self, name: str) -> bool:
        """删除注册。返回 True 表示删除成功，False 表示未找到。"""
        services = self._read_all()
        new_list = [s for s in services if s['name'] != name]
        if len(new_list) == len(services):
            return False
        self._write_all(new_list)
        return True

    def update(self, name: str, cmd: Optional[str] = None,
               url: Optional[str] = None, open_mode: Optional[str] = None,
               use_domain: Optional[bool] = None) -> bool:
        """更新注册的 cmd / url / open / use_domain。返回 True 表示成功，False 表示未找到。

        - cmd=None: 保持原值
        - url=None: 保持原值。传空字符串 '' 清除 url。
        - open_mode=None: 保持原值。
        - use_domain=None: 保持原值。显式 True/False 设置。
        """
        services = self._read_all()
        for s in services:
            if s['name'] == name:
                if cmd is not None:
                    err = self.validate_cmd(cmd)
                    if err:
                        raise ValueError(err)
                    s['cmd'] = cmd
                if url is not None:
                    err = self.validate_url(url)
                    if err:
                        raise ValueError(err)
                    s['url'] = url or None
                if open_mode is not None:
                    err = self.validate_open_mode(open_mode)
                    if err:
                        raise ValueError(err)
                    s['open'] = open_mode
                if use_domain is not None:
                    s['use_domain'] = bool(use_domain)
                self._write_all(services)
                return True
        return False

    def get(self, name: str) -> Optional[dict]:
        """根据名称获取注册，未找到返回 None。"""
        for s in self._read_all():
            if s['name'] == name:
                return s
        return None

    def list_all(self) -> list[dict]:
        """列出所有注册，按 created_at 排序（缺字段排末尾）。"""
        return sorted(self._read_all(),
                      key=lambda x: x.get('created_at', '9999-12-31T23:59:59'))

    def names(self) -> set[str]:
        """返回所有注册名的集合。"""
        return {s['name'] for s in self._read_all()}
