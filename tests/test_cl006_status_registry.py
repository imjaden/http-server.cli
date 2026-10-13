# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL006 — registry 沉积（同端口多记录）口径测试

覆盖转交单 AC A1–A4：
- A1 口径一致：hs status <port> / hs list 对同端口给出存活优先的一致结论
- A2 记账正确：last_access_at 写入存活实例记录，而非同端口首条
- A3 输出不误导：live / stale-record 显式区分，Port 行具名占用者
- A4 沉积治理：hs prune（显式命令）+ 展示层「存活优先 + 最近 started_at」

复现场景（本机 registry.json 实测）：
    同端口 8080 两条记录 —— 陈旧那条 path 少一个 s（.../project/macosx, pid 死），
    存活那条为 .../projects/macosx（pid 活）。旧实现按端口取首条 ⇒ status 报 stopped 误导。
"""

import json
import os

import pytest

from http_server_cli.registry import Registry
import http_server_cli.registry as reg_mod
from http_server_cli.server import ServerManager

pytestmark = pytest.mark.spec("registry")

STALE_PID = 1289           # 已退出进程
LIVE_PID = 1016            # 存活进程
STALE_PATH = '/Users/x/project/macosx'      # 少一个 s 的历史沉积
LIVE_PATH = '/Users/x/projects/macosx'


def _patch_alive(monkeypatch, alive_pids):
    """把 is_process_alive 接到固定存活集合上（server + registry 两处按值导入）。"""
    alive = set(alive_pids)
    fn = lambda pid: pid in alive
    monkeypatch.setattr('http_server_cli.registry.is_process_alive', fn)
    monkeypatch.setattr('http_server_cli.server.is_process_alive', fn)
    return fn


def _patch_port_in_use(monkeypatch, in_use=True):
    fn = lambda p: in_use
    monkeypatch.setattr('http_server_cli.registry.is_port_in_use', fn)
    monkeypatch.setattr('http_server_cli.server.is_port_in_use', fn)
    return fn


def _seed_dupe(reg, port=8080, stale_first=True):
    """同端口两条记录：陈旧（死 pid，早 started_at）+ 存活（活 pid，晚 started_at）。"""
    stale = dict(port=port, path=STALE_PATH, pid=STALE_PID,
                 started_at='2026-08-31T08:22:06')
    live = dict(port=port, path=LIVE_PATH, pid=LIVE_PID,
                started_at='2026-10-13T10:31:35', index_page='macosx-manager.html')
    for spec in ((stale, live) if stale_first else (live, stale)):
        reg.add(**spec)


def _raw(port=8080):
    """直接读盘上的 registry.json（绕过选择逻辑）。"""
    from http_server_cli.utils import REGISTRY_PATH
    with open(REGISTRY_PATH, 'r') as f:
        return [e for e in json.load(f)['servers'] if e.get('port') == port]


# ── A1：选择口径（存活优先 + 最近 started_at） ──────────────

class TestSelectPreferAlive:

    def test_find_port_prefers_alive_over_stale_first(self, monkeypatch, fresh_registry):
        """陈旧条在前、存活条在后 ⇒ find 仍返回存活条（复现正例）。"""
        _seed_dupe(fresh_registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        entry = fresh_registry.find(port=8080)
        assert entry['pid'] == LIVE_PID
        assert entry['path'] == LIVE_PATH

    def test_find_port_prefers_alive_when_alive_first(self, monkeypatch, fresh_registry):
        """存活条在前时结果不变（幂等）。"""
        _seed_dupe(fresh_registry, stale_first=False)
        _patch_alive(monkeypatch, {LIVE_PID})
        assert fresh_registry.find(port=8080)['pid'] == LIVE_PID

    def test_find_port_all_dead_picks_latest_started_at(self, monkeypatch, fresh_registry):
        """无存活 ⇒ 退回最近 started_at（附注口径；状态仍判 stopped）。"""
        _seed_dupe(fresh_registry, stale_first=True)
        _patch_alive(monkeypatch, set())
        assert fresh_registry.find(port=8080)['pid'] == LIVE_PID  # 10-13 晚于 08-31

    def test_find_prefer_alive_false_keeps_legacy_first_match(self, monkeypatch, fresh_registry):
        """prefer_alive=False 保留旧「首个命中」语义（向后兼容逃生口）。"""
        _seed_dupe(fresh_registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        assert fresh_registry.find(port=8080, prefer_alive=False)['pid'] == STALE_PID

    def test_find_single_entry_unchanged(self, monkeypatch, fresh_registry):
        """单条记录行为不变。"""
        fresh_registry.add(port=9000, path='/tmp/only', pid=STALE_PID)
        _patch_alive(monkeypatch, set())
        assert fresh_registry.find(port=9000)['path'] == '/tmp/only'

    def test_find_missing_still_none(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, {LIVE_PID})
        assert fresh_registry.find(port=9999) is None


# ── A2：访问记账目标 ────────────────────────────────────

class TestAccessBookkeepingTargetsLive:

    def test_touch_writes_to_live_entry(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, {LIVE_PID})
        before = {e['pid']: e.get('last_access_at') for e in _raw()}

        fresh_registry.touch(8080)

        after = {e['pid']: e.get('last_access_at') for e in _raw()}
        assert after[STALE_PID] == before[STALE_PID]      # 陈旧条不被刷新
        assert after[LIVE_PID] != before[LIVE_PID]        # 存活条被刷新

    def test_flush_access_cache_writes_to_live_entry(self, monkeypatch, fresh_registry):
        import time
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, {LIVE_PID})
        reg_mod._last_access_cache.clear()
        reg_mod._last_flush_time = time.time()
        before = {e['pid']: e.get('last_access_at') for e in _raw()}

        reg_mod._last_access_cache[8080] = time.time()
        reg_mod._flush_access_cache()

        after = {e['pid']: e.get('last_access_at') for e in _raw()}
        assert after[STALE_PID] == before[STALE_PID]      # 陈旧条不被赋值
        assert after[LIVE_PID] != before[LIVE_PID]        # 存活条被赋值


# ── A4：hs prune（显式清理，仅动 registry） ────────────────

class TestPruneStale:

    def test_prune_removes_only_dead_pids(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry)
        fresh_registry.add(port=8081, path='/tmp/live2', pid=2222)
        _patch_alive(monkeypatch, {LIVE_PID, 2222})
        removed = fresh_registry.prune_stale()
        assert [e['pid'] for e in removed] == [STALE_PID]
        assert {e['pid'] for e in fresh_registry.all()} == {LIVE_PID, 2222}

    def test_prune_returns_copies_not_references(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry, stale_first=False)   # live 1016 在前 + stale 1289
        _patch_alive(monkeypatch, {LIVE_PID})
        removed = fresh_registry.prune_stale()
        assert [e['pid'] for e in removed] == [STALE_PID]
        # 返回副本：改写不影响 registry
        removed[0]['path'] = '/tmp/mutated'
        assert [e['pid'] for e in fresh_registry.all()] == [LIVE_PID]
        assert fresh_registry.count() == 1

    def test_prune_noop_when_all_alive(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, {LIVE_PID, STALE_PID})
        assert fresh_registry.prune_stale() == []
        assert fresh_registry.count() == 2

    def test_stale_entries_preview(self, monkeypatch, fresh_registry):
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, {LIVE_PID})
        stale = fresh_registry.stale_entries()
        assert [e['pid'] for e in stale] == [STALE_PID]

    def test_prune_does_not_touch_history(self, monkeypatch, fresh_registry):
        from http_server_cli.history import HistoryStore
        _seed_dupe(fresh_registry)
        _patch_alive(monkeypatch, set())
        hist = HistoryStore()
        hist.add(port=8080, path=STALE_PATH, started_at='2026-08-31T08:22:06')

        fresh_registry.prune_stale()

        hist2 = HistoryStore()
        # registry 清空，但 history 记录仍在（独立文件，语义不受影响）
        assert fresh_registry.count() == 0
        assert any(r.get('path') == STALE_PATH for r in hist2.records())


# ── A1/A3：hs status <port> 输出口径 ──────────────────────

class TestStatusSelection:

    def test_status_port_shows_live_entry(self, monkeypatch, capsys):
        """复现正例：同端口陈旧条在前，status 应指向存活实例（✅ running）。"""
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        _patch_port_in_use(monkeypatch, True)

        mgr.status('8080')
        out = capsys.readouterr().out
        assert '✅' in out
        assert f'PID:   {LIVE_PID}' in out
        assert 'projects/macosx' in out

    def test_status_stale_only_names_occupant(self, monkeypatch, capsys):
        """无存活实例但端口被他人占用 ⇒ 明确 stale-record + 具名占用者，不误导。"""
        mgr = ServerManager()
        mgr.registry.add(port=8080, path=STALE_PATH, pid=STALE_PID,
                         started_at='2026-08-31T08:22:06')
        _patch_alive(monkeypatch, set())
        _patch_port_in_use(monkeypatch, True)
        monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [LIVE_PID])

        mgr.status('8080')
        out = capsys.readouterr().out
        assert '❌ stopped' in out
        assert 'stale-record' in out
        assert f'PID {LIVE_PID}' in out          # Port 行具名占用者

    def test_status_stale_free_port(self, monkeypatch, capsys):
        """无存活实例且端口空闲 ⇒ stopped + stale-record，Port: free。"""
        mgr = ServerManager()
        mgr.registry.add(port=8080, path=STALE_PATH, pid=STALE_PID)
        _patch_alive(monkeypatch, set())
        _patch_port_in_use(monkeypatch, False)

        mgr.status('8080')
        out = capsys.readouterr().out
        assert '❌ stopped' in out
        assert 'stale-record' in out
        assert 'Port:  free' in out

    def test_status_json_record_status_live(self, monkeypatch, capsys):
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        _patch_port_in_use(monkeypatch, True)

        mgr.status(arg='8080', json=True)
        data = json.loads(capsys.readouterr().out)['data']
        assert data['pid'] == LIVE_PID
        assert data['alive'] is True
        assert data['record_status'] == 'live'

    def test_status_json_record_status_stale(self, monkeypatch, capsys):
        mgr = ServerManager()
        mgr.registry.add(port=8080, path=STALE_PATH, pid=STALE_PID)
        _patch_alive(monkeypatch, set())
        _patch_port_in_use(monkeypatch, True)
        monkeypatch.setattr('http_server_cli.utils.get_pid_by_lsof', lambda p: [LIVE_PID])

        mgr.status(arg='8080', json=True)
        data = json.loads(capsys.readouterr().out)['data']
        assert data['record_status'] == 'stale-record'
        assert data['occupants'] == [LIVE_PID]
        # 既有字段保留（契约）
        for key in ('found', 'url', 'port', 'path', 'pid', 'domain',
                    'alive', 'port_active', 'mode', 'started_at',
                    'index_page', 'stats', 'duration'):
            assert key in data


# ── A1/A4：hs list 与 status 一致性 + stale 标注 ───────────

class TestListConsistency:

    def test_list_dedupes_same_port_prefers_alive(self, monkeypatch, capsys):
        from http_server_cli.cli import _list_servers
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        _patch_port_in_use(monkeypatch, True)

        _list_servers(mgr, json=True)
        data = json.loads(capsys.readouterr().out)['data']
        assert data['count'] == 1
        assert data['servers'][0]['pid'] == LIVE_PID
        assert data['stale_count'] == 1

    def test_list_nonjson_notes_stale(self, monkeypatch, capsys):
        from http_server_cli.cli import _list_servers
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        _patch_port_in_use(monkeypatch, True)

        _list_servers(mgr)
        out = capsys.readouterr().out
        assert 'Total 1 HTTP services' in out
        assert 'stale' in out.lower()

    def test_list_status_consistent_same_port(self, monkeypatch, capsys):
        """同一端口：list 展示的 pid 与 status 指向的 pid 一致（可脚本比对）。"""
        from http_server_cli.cli import _list_servers
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})
        _patch_port_in_use(monkeypatch, True)

        _list_servers(mgr, json=True)
        listed = json.loads(capsys.readouterr().out)['data']['servers'][0]['pid']
        mgr.status(arg='8080', json=True)
        status_pid = json.loads(capsys.readouterr().out)['data']['pid']
        assert listed == status_pid == LIVE_PID


# ── A4：hs prune CLI 入口 ───────────────────────────────

class TestPruneCli:

    def test_cmd_prune_removes_stale(self, monkeypatch, capsys):
        from http_server_cli.cli import _cmd_prune
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})

        _cmd_prune(mgr, [])
        out = capsys.readouterr().out
        assert 'Removed 1 stale registry record' in out
        assert mgr.registry.count() == 1
        assert mgr.registry.find(port=8080, prefer_alive=False)['pid'] == LIVE_PID

    def test_cmd_prune_dry_run_keeps(self, monkeypatch, capsys):
        from http_server_cli.cli import _cmd_prune
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})

        _cmd_prune(mgr, ['--dry-run'])
        out = capsys.readouterr().out
        assert 'Would remove 1 stale registry record' in out
        assert mgr.registry.count() == 2  # 未动手删

    def test_cmd_prune_json_envelope(self, monkeypatch, capsys):
        from http_server_cli.cli import _cmd_prune
        mgr = ServerManager()
        _seed_dupe(mgr.registry, stale_first=True)
        _patch_alive(monkeypatch, {LIVE_PID})

        _cmd_prune(mgr, ['--json'])
        result = json.loads(capsys.readouterr().out)
        assert result['success'] is True
        assert result['command'] == 'prune'
        assert result['data']['removed'] == 1
        assert result['data']['dry_run'] is False
        assert result['data']['entries'][0]['pid'] == STALE_PID

    def test_prune_registered_as_command(self):
        from http_server_cli.cli import _COMMANDS
        assert 'prune' in _COMMANDS
