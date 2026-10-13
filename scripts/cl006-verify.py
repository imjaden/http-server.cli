#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL006 ops 核查 harness —— 转交单 AC A1–A4，可复跑。

用法：python3 scripts/cl006-verify.py
产物：stdout 逐条 PASS/FAIL；退出码 0=全 PASS，1=有 FAIL。

安全/隔离：
  · 全程 HS_DATA_DIR 指向 /tmp/hs-cl006-verify/data ⇒ 绝不触碰真实 ~/.http-server.cli
  · 只用本次启动的端口；结束时 kill 本次服务并删除沙箱目录

口径：
  · registry 数据源 = 沙箱 registry.json 原始文件（绕过选择逻辑）
  · pid 同一性 = 条目 pid 精确相等（非计数/子串）
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = '/tmp/hs-cl006-verify'
DATA = os.path.join(WORK, 'data')
LIVE_DIR = os.path.join(DATA, 'projects', 'macosx')      # 存活实例（projects 带 s）
STALE_DIR = os.path.join(DATA, 'project', 'macosx')      # 陈旧沉积（project 少 s）
STALE_PID = 1289
STALE_LAST_ACCESS = '2026-10-13T12:09:10'

RESULTS = []


def check(aid, ok, detail):
    RESULTS.append((aid, bool(ok), detail))
    print('[%s] %s  %s' % ('PASS' if ok else 'FAIL', aid, detail), flush=True)


def hs(*args, **kw):
    """在沙箱数据目录下运行 hs（子进程继承 HS_DATA_DIR）。"""
    env = dict(os.environ)
    env['HS_DATA_DIR'] = DATA
    env['PYTHONPATH'] = os.path.join(ROOT, 'src') + os.pathsep + env.get('PYTHONPATH', '')
    p = subprocess.run([sys.executable, '-m', 'http_server_cli', *args],
                       cwd=ROOT, env=env, capture_output=True, text=True, **kw)
    return p


def free_port(start=8200):
    for port in range(start, start + 400):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    raise RuntimeError('no free port')


def read_registry():
    with open(os.path.join(DATA, 'registry.json')) as f:
        return json.load(f)['servers']


def entries_for(port):
    return [e for e in read_registry() if e.get('port') == port]


def inject_stale(port, path):
    """把陈旧条插到 servers[] 首位（复现真实 registry.json 的沉积顺序）。"""
    p = os.path.join(DATA, 'registry.json')
    with open(p) as f:
        data = json.load(f)
    data['servers'].insert(0, {
        'port': port, 'path': path, 'pid': STALE_PID, 'domain': 'localhost',
        'daemon': False, 'foreground': False,
        'started_at': '2026-08-31T08:22:06',
        'last_access_at': STALE_LAST_ACCESS, 'index_page': 'index.html',
    })
    with open(p, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(LIVE_DIR)
    os.makedirs(STALE_DIR)

    # index 页由 hs 启动时读取，写入一个可访问的首页
    with open(os.path.join(LIVE_DIR, 'index.html'), 'w') as f:
        f.write('<h1>live</h1>')

    port = free_port()
    started = hs(LIVE_DIR, '-p', str(port), '--url')
    if started.returncode != 0:
        print('启动失败:', started.stdout, started.stderr)
        return 1
    url = started.stdout.strip().splitlines()[-1]
    print('START:', url)

    # 等就绪
    deadline = time.time() + 5
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('127.0.0.1', port)) == 0:
                break
        time.sleep(0.1)

    live_pid = [e['pid'] for e in entries_for(port)]
    check('setup', len(live_pid) == 1, '启动后单条登记 pid=%s' % live_pid)
    live_pid = live_pid[0]

    # 注入同端口陈旧沉积（首位）
    inject_stale(port, STALE_DIR)
    check('setup', len(entries_for(port)) == 2 and entries_for(port)[0]['pid'] == STALE_PID,
          '同端口 2 条，首条=陈旧 pid %d' % STALE_PID)

    try:
        # ── A1：hs status <port> 指向存活实例 ──
        st = hs('status', str(port))
        out = st.stdout
        check('A1', '✅' in out, 'status 报 running')
        check('A1', ('PID:   %d' % live_pid) in out, 'status PID = 存活 %d' % live_pid)
        check('A1', 'projects/macosx' in out and '/project/macosx' not in out.replace('/projects/macosx', ''),
              'status path = 存活实例（非陈旧 project/macosx）')

        stj = json.loads(hs('status', str(port), '--json').stdout)
        check('A1', stj['data']['pid'] == live_pid and stj['data']['record_status'] == 'live',
              'status --json pid=%s record_status=%s' % (stj['data']['pid'], stj['data']['record_status']))

        # ── 一致性：status 与 list 同端口结论一致 ──
        lj = json.loads(hs('list', '--json').stdout)['data']
        listed = [s['pid'] for s in lj['servers'] if s['port'] == port]
        check('CONSIST', listed == [live_pid] and stj['data']['pid'] == live_pid,
              'list pid=%s == status pid=%s' % (listed, stj['data']['pid']))
        check('CONSIST', lj.get('stale_count') == 1, 'list --json stale_count=1（新增字段）')

        # ── A2：访问一次页面 → last_access_at 落在存活实例 ──
        #  runner 首个 GET 触发 _touch_memory 即时刷盘（_last_flush_time 初值 0.0）；
        #  先跨过 1 秒边界，避免与登记时刻同秒导致秒级时间戳看不出差异。
        time.sleep(1.2)
        before = {e['pid']: e.get('last_access_at') for e in entries_for(port)}
        subprocess.run(['curl', '-s', '-o', '/dev/null', 'http://127.0.0.1:%d/index.html' % port],
                       timeout=5)
        after = dict(before)
        dl = time.time() + 5
        while time.time() < dl:
            after = {e['pid']: e.get('last_access_at') for e in entries_for(port)}
            if after.get(live_pid) != before[live_pid]:
                break
            time.sleep(0.2)
        check('A2', after.get(live_pid) != before[live_pid],
              '存活条 last_access_at 刷新 %s → %s' % (before[live_pid], after.get(live_pid)))
        check('A2', after.get(STALE_PID) == STALE_LAST_ACCESS,
              '陈旧条 last_access_at 未被污染 = %s' % after.get(STALE_PID))

        # ── A3/AC2：无存活实例的端口 → stopped + stale-record，无「in use」矛盾 ──
        p2 = free_port(port + 1)
        inject_stale(p2, STALE_DIR)   # 该端口无存活进程、端口空闲
        out2 = hs('status', str(p2)).stdout
        check('A3', '❌ stopped' in out2 and 'stale-record' in out2,
              'status 报 stopped + stale-record')
        check('A3', 'Port:  free' in out2 and 'in use' not in out2,
              'Port 行 = free，无「in use」矛盾组合')

        # ── A4：hs prune（dry-run 不动手；显式命令才删） ──
        n_before = len(read_registry())
        dry = hs('prune', '--dry-run').stdout
        check('A4', 'Would remove' in dry and len(read_registry()) == n_before,
              'prune --dry-run 预览且不改动 registry（%d 条）' % n_before)

        removed = hs('prune').stdout
        remaining = read_registry()
        check('A4', 'Removed' in removed and len(remaining) == 1 and remaining[0]['pid'] == live_pid,
              'prune 删除沉积、保留存活条 pid=%d' % live_pid)
        check('A4', all(e.get('pid') != STALE_PID for e in remaining),
              '陈旧 pid %d 已清除' % STALE_PID)

        # prune 后存活实例仍在（status 仍 running）
        out3 = hs('status', str(port)).stdout
        check('A4', '✅' in out3 and ('PID:   %d' % live_pid) in out3,
              'prune 后 status 仍指向存活实例')
    finally:
        hs('kill', str(port))
        shutil.rmtree(WORK, ignore_errors=True)

    fails = [r for r in RESULTS if not r[1]]
    print('\n%d/%d PASS' % (len(RESULTS) - len(fails), len(RESULTS)))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
