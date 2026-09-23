#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL004 ops 核查 harness —— 设计 v1.4 §8 A 段断言表（A1–A11），可复跑。

用法：python3 scripts/port-residual-verify.py
产物：stdout 逐条 PASS/FAIL + cache/closed-loop/20260922-http-server.cli-HTTP-SERVER-CL004-ops-verify.json

口径（设计 §8 头注）：
  · <tmpdir> 一律指 resolve_path(<tmpdir>)（macOS /var→/private/var、/tmp→/private/tmp）
  · registry 数据源 = ~/.http-server.cli/registry.json **原始文件**（不得用 hs list --json —— 其按 _alive 过滤会掩盖隐形孤儿）
  · 我方 runner 归属规则 = 命令行按空白切分后，存在 token 其 basename == 'runner.py' 且存在 token 与 abs_path 完全相等

安全：只操作 /tmp/hs-cl004-verify 下的临时目录与本次启动的端口；结束时清理服务、目录、worktree 与 registry 复原。
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = '/Users/jadenli/CodeSpace/http-server.cli'
WORK = '/tmp/hs-cl004-verify'
WORKTREE = '/tmp/hs-cl004-prefix'
BASE_COMMIT = 'ef125b3'          # CL004 实现前基线（origin/main：CL003 实现 + 设计/审计）
REG_PATH = Path.home() / '.http-server.cli' / 'registry.json'
SERVICES_PATH = Path.home() / '.http-server.cli' / 'services.json'
JSON_OUT = os.path.join(ROOT, 'cache', 'closed-loop',
                        '20260922-http-server.cli-HTTP-SERVER-CL004-ops-verify.json')
RESULTS = []
STARTED_PORTS = []
TEMP_PATHS = []
REG_BACKUP = None


# ── 基础设施 ────────────────────────────────────────────

def check(aid, ok, detail):
    RESULTS.append({'id': aid, 'ok': bool(ok), 'detail': detail})
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', aid, detail), flush=True)


def realpath(p):
    return os.path.realpath(p)


def demo(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<h1>%s</h1>' % name)
    TEMP_PATHS.append(realpath(d))
    return realpath(d)


def hs(args, timeout=120, cwd=None):
    p = subprocess.run(['hs'] + args, capture_output=True, text=True,
                       timeout=timeout, cwd=cwd or ROOT)
    return p.stdout, p.stderr, p.returncode


def hs_old(args, timeout=120, cwd=None):
    """基线（CL004 前）实现：用 worktree 的 src 直接跑 CLI。"""
    env = dict(os.environ, PYTHONPATH=os.path.join(WORKTREE, 'src'))
    p = subprocess.run([sys.executable, '-m', 'http_server_cli.cli'] + args,
                       capture_output=True, text=True, timeout=timeout,
                       cwd=cwd or ROOT, env=env)
    return p.stdout, p.stderr, p.returncode


def py_new(code):
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'src'))
    return subprocess.run([sys.executable, '-c', code], capture_output=True,
                          text=True, timeout=60, env=env)


def py_old(code):
    env = dict(os.environ, PYTHONPATH=os.path.join(WORKTREE, 'src'))
    return subprocess.run([sys.executable, '-c', code], capture_output=True,
                          text=True, timeout=60, env=env)


def free_port(lo=9500, hi=9599):
    for p in range(lo, hi + 1):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('', p))
            s.close()
            return p
        except OSError:
            s.close()
    raise RuntimeError('no free port in range')


_fresh_cursor = [9600]


def free_port_fresh(hi=9699):
    """给「修前反证」用的干净端口（独立段 + 不重复）：
    基线实现的 is_port_in_use 为裸 bind，会把自己刚释放的 TIME_WAIT 端口判成占用，
    复用端口会让基线 run 直接 fail-closed（采样作废）。"""
    while _fresh_cursor[0] <= hi:
        p = _fresh_cursor[0]
        _fresh_cursor[0] += 1
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('', p))
            s.close()
            return p
        except OSError:
            s.close()
    raise RuntimeError('no fresh port left')


def pytest_python():
    """挑一个真正装 pytest 的解释器（后台/不同 shell 上下文 python3 可能不通用）。"""
    cands = [sys.executable]
    for c in ('/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python3.12',
              shutil.which('python3'), shutil.which('python')):
        if c and c not in cands:
            cands.append(c)
    for c in cands:
        try:
            p = subprocess.run([c, '-c', 'import pytest'], capture_output=True, timeout=60)
            if p.returncode == 0:
                return c
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def residual_port(port):
    """服务端先 close（先发 FIN）⇒ 该端口进入 TIME_WAIT。"""
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('', port))
    srv.listen(1)
    holder = {}

    def _acc():
        c, _ = srv.accept()
        holder['c'] = c

    t = threading.Thread(target=_acc)
    t.start()
    cli_sock = socket.socket()
    cli_sock.connect(('127.0.0.1', port))
    time.sleep(0.3)
    holder['c'].close()
    time.sleep(0.2)
    cli_sock.close()
    srv.close()
    t.join(timeout=2)


def registry_raw():
    try:
        data = json.loads(REG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return []
    return data.get('servers', []) if isinstance(data, dict) else []


def listen_pids(path=None):
    """全部 LISTEN pid；给 path 时按归属规则过滤（token 精确匹配）。"""
    out = subprocess.run(['lsof', '-nP', '-iTCP', '-sTCP:LISTEN', '-F', 'p'],
                         capture_output=True, text=True).stdout
    pids = []
    for line in out.split('\n'):
        if line.startswith('p'):
            try:
                pids.append(int(line[1:]))
            except ValueError:
                pass
    if path is None:
        return set(pids)
    ours = set()
    for pid in pids:
        argv = subprocess.run(['ps', '-p', str(pid), '-o', 'args='],
                              capture_output=True, text=True).stdout.split()
        if any(os.path.basename(tok) == 'runner.py' for tok in argv) and path in argv:
            ours.add(pid)
    return ours


def wait_ready(path, timeout=3.0):
    deadline = time.time() + timeout
    last = set()
    while time.time() < deadline:
        cur = listen_pids(path)
        if cur and cur == last:
            return cur
        last = cur
        time.sleep(0.2)
    return last


def kill_path(path):
    for _ in range(3):
        hs(['kill', path])
        time.sleep(0.2)
    for pid in listen_pids(path):
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    time.sleep(0.3)


def setup_worktree():
    subprocess.run(['git', 'worktree', 'remove', '--force', WORKTREE],
                   cwd=ROOT, capture_output=True)
    shutil.rmtree(WORKTREE, ignore_errors=True)
    p = subprocess.run(['git', 'worktree', 'add', WORKTREE, BASE_COMMIT],
                       cwd=ROOT, capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


# ── A 段断言 ────────────────────────────────────────────

def a1_residual_probe():
    port = free_port()
    residual_port(port)
    code = ('from http_server_cli.utils import is_port_in_use;'
            'print(is_port_in_use(%d))' % port)
    new = py_new(code).stdout.strip()
    old = py_old(code).stdout.strip()
    check('A1', new == 'False' and old == 'True',
          '残留态端口 %d：修后 is_port_in_use=%s；修前(基线 %s)=%s（修前反证需 True）'
          % (port, new, BASE_COMMIT, old))


def a2_real_listener_probe():
    port = free_port()
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('', port))
    srv.listen(1)
    port2 = free_port()
    srv2 = socket.socket()
    srv2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv2.bind(('127.0.0.1', port2))
    srv2.listen(1)
    code = ('from http_server_cli.utils import is_port_in_use;'
            'print(is_port_in_use(%d), is_port_in_use(%d))' % (port, port2))
    out = py_new(code).stdout.strip()
    srv.close()
    srv2.close()
    check('A2', out == 'True True',
          '真监听 wildcard=%d / 仅 127.0.0.1=%d → is_port_in_use=%s（均须 True）' % (port, port2, out))


def a3_residual_pinned_port():
    port = free_port()
    d = demo('a3')
    kill_path(d)
    residual_port(port)
    out, err, rc = hs([d, '-p', str(port), '-d', '--url'])
    STARTED_PORTS.append(port)
    ok = rc == 0 and ('%d' % port) in out
    check('A3', ok, '残留态端口 %d + -p：rc=%d out=%r err=%r' % (port, rc, out.strip(), err.strip()[:60]))
    hs(['kill', str(port)])


def a4_double_start():
    d = demo('a4')
    kill_path(d)
    p = subprocess.Popen(['hs', d, '-d', '--url'], stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, text=True, cwd=ROOT)
    time.sleep(0.05)
    out2, err2, rc2 = hs([d, '-d', '--url'])
    p.communicate(timeout=60)
    STARTED_PORTS.append(None)
    ours = wait_ready(d)
    entries = [e for e in registry_raw() if e.get('path') == d]
    reg_pids = {e.get('pid') for e in entries}
    ok = len(entries) == 1 and ours == reg_pids and len(ours) > 0
    check('A4-修后', ok, '双击后 registry 条目=%d listener_pids=%s registry_pids=%s（须 1 条且同一性相等）'
          % (len(entries), sorted(ours), sorted(reg_pids)))
    # 修前反证（基线：≥3 次有效样本）
    repro, samples = 0, 0
    for i in range(5):
        d2 = demo('a4old%d' % i)
        kill_path(d2)
        p = subprocess.Popen([sys.executable, '-m', 'http_server_cli.cli', d2, '-d', '--url'],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             cwd=ROOT, env=dict(os.environ, PYTHONPATH=os.path.join(WORKTREE, 'src')))
        time.sleep(0.05)
        hs_old([d2, '-d', '--url'])
        p.communicate(timeout=60)
        time.sleep(0.5)
        e2 = [e for e in registry_raw() if e.get('path') == d2]
        o2 = listen_pids(d2)
        r2 = {e.get('pid') for e in e2}
        samples += 1
        if o2 != r2:
            repro += 1
        kill_path(d2)
        shutil.rmtree(os.path.join(WORK, 'a4old%d' % i), ignore_errors=True)
    check('A4-修前反证', repro >= 3,
          '基线双击 %d 次样本中 %d 次出现 listener 集合 != registry 集合（须 ≥3）' % (samples, repro))
    kill_path(d)
    hs(['kill', d])


def a5_index_value_reorg():
    target = demo('a5target')
    cwd = os.path.join(WORK, 'a5cwd')
    shutil.rmtree(cwd, ignore_errors=True)
    os.makedirs(cwd)
    with open(os.path.join(cwd, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<h1>cwd</h1>')
    kill_path(target)
    port = free_port()
    p = subprocess.run(['hs', '-i', 'index.html', '-p', str(port), '-d', '--url', target],
                       capture_output=True, text=True, cwd=cwd)
    out, err, rc = p.stdout, p.stderr, p.returncode
    STARTED_PORTS.append(port)
    time.sleep(0.6)
    e = [x for x in registry_raw() if x.get('path') == target]
    ok = rc == 0 and len(e) == 1 and str(port) in out
    check('A5-修后', ok, '顶层 -i（CWD 存在同名文件）：rc=%d out=%r registry=%s'
          % (rc, out.strip(), [(x.get('port'), x.get('index_page')) for x in e]))
    # 修前反证：基线落 CWD（用干净端口；基线裸 bind 会把 TIME_WAIT 端口误判为占用 ⇒ 采样作废重试）
    cwd_rp = realpath(cwd)
    kill_path(target)
    kill_path(cwd_rp)
    ok_old, detail_old = False, ''
    for attempt in range(3):
        port_old = free_port_fresh()
        p_old = subprocess.run([sys.executable, '-m', 'http_server_cli.cli', '-i', 'index.html',
                                '-p', str(port_old), '-d', '--url', target],
                               capture_output=True, text=True, cwd=cwd,
                               env=dict(os.environ, PYTHONPATH=os.path.join(WORKTREE, 'src')))
        time.sleep(0.6)
        e_old_target = [x for x in registry_raw() if x.get('path') == target]
        e_old_cwd = [x for x in registry_raw() if x.get('path') == cwd_rp]
        detail_old = ('第 %d 次（端口 %d）：rc=%d out=%r err=%r｜目标目录条目=%d｜CWD 条目=%d'
                      % (attempt + 1, port_old, p_old.returncode, p_old.stdout.strip(),
                         p_old.stderr.strip()[:60], len(e_old_target), len(e_old_cwd)))
        for x in e_old_cwd:
            hs(['kill', str(x.get('port'))])
        kill_path(cwd_rp)
        kill_path(target)
        if p_old.returncode == 0 and len(e_old_target) == 0 and len(e_old_cwd) >= 1:
            ok_old = True
            break
    check('A5-修前反证', ok_old, detail_old)
    hs(['kill', target])


def a6_web_exit_codes():
    name1, name2 = 'cl004v-a6a', 'cl004v-a6b'
    for n in (name1, name2):
        hs(['web', 'remove', n])
    _, err1, rc1 = hs(['web', 'add', name1, '--cmd', 'true', '--port', '99'])
    _, err2, rc2 = hs(['web', 'add', name2, '--cmd', 'true', '--port', '9001', '--no-port'])
    created = False
    try:
        data = json.loads(SERVICES_PATH.read_text(encoding='utf-8'))
        names = [s.get('name') for s in data.get('services', [])]
        created = name1 in names or name2 in names
    except Exception:
        pass
    check('A6', rc1 == 2 and rc2 == 2 and not created,
          '越界 rc=%d（%s）｜互斥 rc=%d（%s）｜是否误建条目=%s'
          % (rc1, err1.strip()[:40], rc2, err2.strip()[:40], created))


def a7_cl003_regression():
    p = subprocess.run([sys.executable, 'scripts/port-flag-verify.py'], cwd=ROOT,
                       capture_output=True, text=True, timeout=900)
    tail = [l for l in p.stdout.strip().split('\n') if 'PASS=' in l or '结论' in l]
    ok = p.returncode == 0 and '31/31' in p.stdout
    check('A7', ok, 'CL003 harness rc=%d；%s' % (p.returncode, tail[-1] if tail else p.stdout[-120:]))


def a8_full_pytest():
    py = pytest_python()
    if not py:
        check('A8', False, '未找到装有 pytest 的解释器（候选均 import pytest 失败）')
        return
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'src'))
    p = subprocess.run([py, '-m', 'pytest', 'tests/', '-q'], cwd=ROOT,
                       capture_output=True, text=True, timeout=1800, env=env)
    last = (p.stdout.strip().split('\n') or [''])[-1]
    ok = p.returncode == 0 and ' passed' in last
    check('A8', ok, '全量 pytest（%s）rc=%d：%s' % (py, p.returncode, last[:110]))


def a9_sync_greps():
    out, _, _ = hs(['version'])
    ver_ok = ('v1.4.0' in out or 'v1.4.1' in out)   # CL005：版本上移 1.4.0 → 1.4.1（CL004 保持可复跑）
    changelog = Path(ROOT, 'CHANGELOG.md').read_text(encoding='utf-8')
    fixed_ok = '### Fixed' in changelog
    stale_ok = '另批处理' not in changelog
    spec = Path(ROOT, 'http-server.cli.spec.yaml').read_text(encoding='utf-8')
    spec_ok = ('\nversion: 1.4.0' in ('\n' + spec)) or ('\nversion: 1.4.1' in ('\n' + spec))
    check('A9', ver_ok and fixed_ok and stale_ok and spec_ok,
          'hs version=%r｜CHANGELOG ### Fixed=%s｜旧「另批处理」残留=%s｜spec 1.4.0=%s'
          % (out.strip(), fixed_ok, not stale_ok, spec_ok))


def a10_residue():
    rows = registry_raw()
    temps = [r for r in rows if any(r.get('path', '').startswith(p) for p in
                                   [realpath(WORK), realpath('/tmp/hs-cl003-verify')])]
    # 我方 runner listener 必须无主（每条都能对上 registry 条目 pid）
    reg_pids = {r.get('pid') for r in rows}
    orphans = []
    out = subprocess.run(['lsof', '-nP', '-iTCP', '-sTCP:LISTEN', '-F', 'p'],
                         capture_output=True, text=True).stdout
    for line in out.split('\n'):
        if not line.startswith('p'):
            continue
        pid = int(line[1:])
        argv = subprocess.run(['ps', '-p', str(pid), '-o', 'args='],
                              capture_output=True, text=True).stdout.split()
        if any(os.path.basename(t) == 'runner.py' for t in argv) and pid not in reg_pids:
            orphans.append((pid, ' '.join(argv[4:6])))
    check('A10', not temps and not orphans,
          '临时目录残留条目=%d｜无主 runner listener=%s' % (len(temps), orphans))


def a11_json_channel():
    d = demo('a11')
    kill_path(d)
    port = free_port()
    raw = json.loads(REG_PATH.read_text(encoding='utf-8'))
    raw.setdefault('servers', []).append({
        'port': port, 'path': d, 'pid': 999999, 'domain': 'localhost',
        'started_at': '2026-09-22 20:00:00', 'daemon': True, 'foreground': False,
        'index_page': 'index.html'})
    REG_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    out, err, rc = hs([d, '--json'])
    parsed = False
    payload = None
    try:
        payload = json.loads(out)
        parsed = True
    except Exception:
        pass
    ok = parsed and 'Found stale registry entry' in err
    check('A11', ok, '--json 触发 stale：stdout 首字符=%r 可解析=%s｜stderr 含 stale=%s｜rc=%d'
          % (out.lstrip()[:1], parsed, 'Found stale registry entry' in err, rc))
    if payload and isinstance(payload.get('data'), dict) and payload['data'].get('port'):
        hs(['kill', str(payload['data']['port'])])
    time.sleep(0.4)
    # 清理：移除本次注入/新建条目
    cur = json.loads(REG_PATH.read_text(encoding='utf-8'))
    cur['servers'] = [s for s in cur.get('servers', []) if s.get('path') != d]
    REG_PATH.write_text(json.dumps(cur, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    kill_path(d)


def cleanup():
    for port in STARTED_PORTS:
        if port:
            hs(['kill', str(port)])
    for path in TEMP_PATHS:
        kill_path(path)
    shutil.rmtree(WORK, ignore_errors=True)
    for n in ('cl004v-a6a', 'cl004v-a6b'):
        hs(['web', 'remove', n])
    subprocess.run(['git', 'worktree', 'remove', '--force', WORKTREE], cwd=ROOT,
                   capture_output=True)
    shutil.rmtree(WORKTREE, ignore_errors=True)
    if REG_BACKUP is not None:
        REG_PATH.write_text(REG_BACKUP, encoding='utf-8')


def main():
    global REG_BACKUP
    print('== HTTP-SERVER-CL004 ops 核查（A1–A11）==', flush=True)
    os.makedirs(WORK, exist_ok=True)
    REG_BACKUP = REG_PATH.read_text(encoding='utf-8') if REG_PATH.exists() else None
    ok_wt, msg = setup_worktree()
    if not ok_wt:
        check('A0', False, 'worktree 建立失败（修前反证不可用）：%s' % msg)
    else:
        print('   worktree: %s @ %s' % (WORKTREE, BASE_COMMIT), flush=True)
    try:
        a1_residual_probe()
        a2_real_listener_probe()
        a3_residual_pinned_port()
        a4_double_start()
        a5_index_value_reorg()
        a6_web_exit_codes()
        a7_cl003_regression()
        a8_full_pytest()
        a9_sync_greps()
        a10_residue()
        a11_json_channel()
    finally:
        cleanup()
    n_ok = sum(1 for r in RESULTS if r['ok'])
    print('\n=== 结论：%d/%d PASS ===' % (n_ok, len(RESULTS)), flush=True)
    for r in RESULTS:
        if not r['ok']:
            print('  FAIL %s %s' % (r['id'], r['detail']))
    try:
        os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
        with open(JSON_OUT, 'w', encoding='utf-8') as f:
            json.dump({'harness': 'port-residual-verify', 'base_commit': BASE_COMMIT,
                       'total': len(RESULTS), 'passed': n_ok, 'results': RESULTS},
                      f, ensure_ascii=False, indent=2)
        print('JSON: %s' % JSON_OUT)
    except OSError as e:
        print('JSON 落盘失败：%s' % e)
    return 0 if n_ok == len(RESULTS) and RESULTS else 1


if __name__ == '__main__':
    sys.exit(main())
