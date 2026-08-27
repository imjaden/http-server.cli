# -*- coding: utf-8 -*-
"""
配置管理：默认端口、绑定域名。
持久化至 ~/.http-server.cli/config.json。
"""

import os
import re
from http_server_cli.utils import CONFIG_PATH, read_json, write_json

# SEC-023-1: 域名/绑定地址字符集——拒绝空格/引号/`$`/反引号/`;`/`&` 等 shell 元字符
_DOMAIN_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$')

DEFAULT_CONFIG = {
    'port': 8080,
    'domain': 'localhost',
}

# 可写字段白名单
_SETTABLE_KEYS = frozenset({'port', 'domain'})

class Config:
    """配置读写，字段变更即时持久化。"""

    def __init__(self) -> None:
        self._data = dict(DEFAULT_CONFIG)
        self._merge_file()

    def _merge_file(self) -> None:
        """合并磁盘配置，不覆盖缺失字段"""
        on_disk = read_json(CONFIG_PATH)
        if isinstance(on_disk, dict):
            for k in _SETTABLE_KEYS:
                if k in on_disk:
                    self._data[k] = on_disk[k]

    # ── 属性读取 ──

    @property
    def port(self) -> int:
        """默认起始端口"""
        return self._data['port']

    @property
    def domain(self) -> str:
        """绑定域名"""
        return self._data['domain']

    # ── 属性写入（自动保存） ──

    def set_port(self, value: int) -> None:
        """设置默认端口（1024-65535），持久化"""
        self._data['port'] = value
        self._save()

    def set_domain(self, value: str) -> None:
        """设置绑定域名，持久化。非法值（含 shell 元字符）抛 ValueError。

        字符集 [a-zA-Z0-9][a-zA-Z0-9.-]* 拒绝空格/引号/`$`/反引号/`;`/`&` 等
        shell 元字符——hs web --domain 注入该值到 shell 命令（SEC-023-1
        defense-in-depth；用户仍可直接手改 config.json，信任用户自行为）。
        """
        if not isinstance(value, str) or not _DOMAIN_RE.match(value):
            raise ValueError(
                'domain must match [a-zA-Z0-9][a-zA-Z0-9.-]* '
                '(no spaces, quotes or shell metacharacters)'
            )
        self._data['domain'] = value
        self._save()

    def _save(self) -> None:
        write_json(CONFIG_PATH, self._data)

    # ── 序列化 ──

    def to_dict(self) -> dict:
        return dict(self._data)

    def show(self, json: bool = False) -> None:
        """打印配置，或返回 JSON 格式"""
        if json:
            from http_server_cli.utils import json_output
            data = {
                'port': self.port,
                'domain': self.domain,
                'data_dir': CONFIG_PATH,
            }
            json_output(success=True, command='config', data=data)
            return
        print('📋 http-server configuration')
        print(f'  port:   {self.port}')
        print(f'  domain: {self.domain}')
        print(f'  data dir: {CONFIG_PATH.replace(os.path.expanduser("~"), "~")}')
        print()
        print('💡 Change configuration:')
        print(f'  hs set port {self.port}    Change default port')
        print(f'  hs set domain {self.domain}  Change binding domain')
