#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTTP-SERVER-CL007 ops 核查 harness —— 参数面加固 AC A1–A4，可复跑。

用法：python3 scripts/cl007-verify.py
产物：stdout 逐条 PASS/FAIL；退出码 0=全 PASS，1=有 FAIL。

安全/隔离：
  · 全程 HS_DATA_DIR 指向 /tmp/hs-cl007-verify/data ⇒ 绝不触碰真实 ~/.http-server.cli
  · 仅使用沙箱内登记条目；结束时 kill 本次服务并删除沙箱目录
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = '/tmp/hs-cl007-verify'
DATA = os.path.join(WORK, 'data')
LIVE_DIR = os.path.join(DATA, 'projects', 'live')
EMPTY_DIR = os.path.join(DATA, 'projects', 'empty')
STALE_PID = 4242
RESULTS = []


def check(aid, ok, detail):
    RESULTS.append((aid, bool(ok), detail))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', aid, detail), flush=True)


def hs(*args, cwd=None):
    """在沙箱数据目录下运行 hs（子进程继承 HS_DATA_DIR）。"""
    env = dict(os.environ)
    env['HS_DATA_DIR'] = DATA
    env['PYTHONPATH'] = os.path.join(ROOT, 'src') + os.pathsep + env.get('PYTHONPATH', '')
    return subprocess.run([sys.executable, '-m', 'http_server_cli', *args],
                          cwd=cwd or ROOT, env=env, capture_output=True, text=True)


def free_port(start=8300):
    for port in range(start, start + 400):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError('no free port')


def read_registry():
    p = os.path.join(DATA, 'registry.json')
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return json.load(f).get('servers', [])


def inject_stale(port):
    """写入一条 pid 必死的沉积登记（供 prune 判定）。"""
    p = os.path.join(DATA, 'registry.json')
    with open(p) as f:
        data = json.load(f)
    data['servers'].insert(0, {
        'port': port, 'path': '/tmp/hs-cl007-stale', 'pid': STALE_PID,
        'domain': 'localhost', 'daemon': False, 'foreground': False,
        'started_at': '2026-08-01T00:00:00', 'last_access_at': '2026-08-01T00:00:00',
        'index_page': 'index.html'})
    with open(p, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def wait_port(port, timeout=5.0):
    dl = time.time() + timeout
    while time.time() < dl:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.1)
    return False


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(LIVE_DIR)
    os.makedirs(EMPTY_DIR)
    with open(os.path.join(LIVE_DIR, 'index.html'), 'w') as f:
        f.write('<h1>live</h1>')

    port = free_port()
    started = hs(LIVE_DIR, '-p', str(port), '--url')
    if started.returncode != 0:
        print('启动失败:', started.stdout, started.stderr)
        return 1
    print('START:', started.stdout.strip().splitlines()[-1])
    wait_port(port)

    try:
        # ── A1：写 / 破坏性命令遇未知 flag → fail-closed（无副作用） ──
        inject_stale(port + 111)
        n0 = len(read_registry())

        h = hs('prune', '--help')
        check('A1', h.returncode == 0 and '用法:' in h.stdout and len(read_registry()) == n0,
              '`hs prune --help` rc=%s（打印用法，未删条）' % h.returncode)

        b = hs('prune', '--bogus')
        check('A1', b.returncode == 2 and '未识别参数' in b.stderr and len(read_registry()) == n0,
              '`hs prune --bogus` rc=%s 未删条 err=%r' % (
                  b.returncode, b.stderr.strip().splitlines()[0][:60]))

        k = hs('kill', str(port), '--bogus')
        still = wait_port(port)
        check('A1', k.returncode == 2 and '未识别参数' in k.stderr and still,
              '`hs kill %d --bogus` rc=%s 服务仍在=%s' % (port, k.returncode, still))

        l = hs('list', '--prot')
        check('A1', l.returncode == 0 and '未识别参数' in l.stderr and '未识别参数' not in l.stdout,
              '`hs list --prot`（只读）rc=%s 仅 stderr 告警' % l.returncode)

        # ── A2：裸 hs 不静默起服务 ──
        before = len(read_registry())
        bare = hs(cwd=EMPTY_DIR)
        check('A2', bare.returncode == 2 and '用法:' in bare.stdout and len(read_registry()) == before,
              '裸 `hs` rc=%s 打印用法且未新增登记（%d 条）' % (bare.returncode, len(read_registry())))

        p_explicit = free_port(port + 500)
        explicit = hs(EMPTY_DIR, '-p', str(p_explicit), '--url')
        check('A2', explicit.returncode == 0,
              '`hs <dir> -p %d --url`（显式）rc=%s url=%r' % (
                  p_explicit, explicit.returncode, explicit.stdout.strip()))
        hs('kill', str(p_explicit))

        # ── A3：prune 汇总（已删/保留）+ -n 预览差异 ──
        n_before = len(read_registry())
        dry = hs('prune', '-n')
        check('A3', 'Would remove' in dry.stdout and 'Kept' in dry.stdout
              and len(read_registry()) == n_before,
              '`hs prune -n` 预览且不改动（%d 条）：%r' % (
                  len(read_registry()), dry.stdout.strip().replace('\n', ' | ')[:90]))

        applied = hs('prune')
        check('A3', 'Removed' in applied.stdout and 'Kept' in applied.stdout
              and len(read_registry()) < n_before,
              '`hs prune` 执行并给出 已删/保留 汇总（%d → %d）：%r' % (
                  n_before, len(read_registry()),
                  applied.stdout.strip().replace('\n', ' | ')[:90]))

        # ── A4：JSON 契约（字段不变 + 错误信封） ──
        lj = json.loads(hs('list', '--json').stdout)['data']
        check('A4', all(k in lj for k in ('count', 'stale_count', 'servers', 'managed')),
              'list --json 既有字段完整: %s' % sorted(lj.keys()))

        pj = hs('prune', '--bogus', '--json')
        env = json.loads(pj.stdout)
        check('A4', pj.returncode == 2 and env['success'] is False and env['command'] == 'prune',
              '`prune --bogus --json` rc=%s 错误信封 command=%s error=%r' % (
                  pj.returncode, env.get('command'), env.get('error')))
    finally:
        hs('kill', str(port))
        for e in read_registry():
            hs('kill', str(e.get('port')))
        shutil.rmtree(WORK, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    print('\n%d/%d PASS' % (len(RESULTS) - len(fails), len(RESULTS)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
