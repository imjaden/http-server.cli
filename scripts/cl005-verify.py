#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL005 ops 核查 harness —— 设计 v1.2 §6.2 断言表（A1–A17），可复跑。

用法：python3 scripts/cl005-verify.py [--only A5,A6]
产物：stdout 逐条 PASS/FAIL + cache/closed-loop/20260923-http-server.cli-HTTP-SERVER-CL005-ops-verify.json

口径（设计 §6.2 头注）：
  · <tmpdir> 一律取 resolve_path()（macOS /tmp→/private/tmp）
  · registry 数据源 = ~/.http-server.cli/registry.json **原始文件**（禁用 `hs list --json`：其按 _alive 过滤会掩盖隐形孤儿）
  · pid 同一性 = registry 条目的 pid == 该端口 LISTEN 的唯一 pid（禁计数相等 / 禁子串）
  · 并发样本 ≥3，剔除幂等样本（第二次起的幂等命中不计入）；修前反证基线 worktree `4679ee8`
安全：只操作 /tmp/hs-cl005-verify 下临时目录与本次启动的端口；结束时 kill 本次服务、删目录、registry/services 复原。
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = '/Users/jadenli/CodeSpace/http-server.cli'
WORK = '/tmp/hs-cl005-verify'
WORKTREE = '/tmp/hs-cl005-prefix'
BASE_COMMIT = '4679ee8'          # CL005 实现前基线（CL004 收尾）
HOME = Path.home() / '.http-server.cli'
REG_PATH = HOME / 'registry.json'
SERVICES_PATH = HOME / 'services.json'
LOCK_DIR = HOME / 'locks'
JSON_OUT = os.path.join(ROOT, 'cache', 'closed-loop',
                        '20260923-http-server.cli-HTTP-SERVER-CL005-ops-verify.json')
RESULTS = []
TEMP_PATHS = []
STARTED_PORTS = []
LOCKS_BEFORE = None
REG_BACKUP = b''
SVC_BACKUP = b''
ONLY = []


# ── 基础设施 ────────────────────────────────────────────

def check(aid, ok, detail):
    RESULTS.append({'id': aid, 'ok': bool(ok), 'detail': detail})
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', aid, detail), flush=True)


def realpath(p):
    return os.path.realpath(p)


def demo(name, index=True, extra=None):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    if index:
        with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
            f.write('<h1>%s</h1>' % name)
    for fname, body in (extra or {}).items():
        with open(os.path.join(d, fname), 'w', encoding='utf-8') as f:
            f.write(body)
    TEMP_PATHS.append(realpath(d))
    return realpath(d)


def hs(args, timeout=120, env_extra=None):
    """跑**已安装**的 hs（py3.12 环境 editable 指向本仓 src）。"""
    for a in args:
        s = str(a)
        if s.isdigit() and 8090 <= int(s) <= 8099 and int(s) not in STARTED_PORTS:
            STARTED_PORTS.append(int(s))
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(['hs'] + list(args), capture_output=True, text=True,
                       timeout=timeout, cwd=ROOT, env=env)
    return p.stdout, p.stderr, p.returncode


def hs_old(args, timeout=120):
    """基线（CL005 前）实现：worktree 的 src 直接跑 CLI。"""
    env = dict(os.environ, PYTHONPATH=os.path.join(WORKTREE, 'src'))
    p = subprocess.run([sys.executable, '-m', 'http_server_cli.cli'] + list(args),
                       capture_output=True, text=True, timeout=timeout, cwd=ROOT, env=env)
    return p.stdout, p.stderr, p.returncode


def py(code, timeout=60, interpreter=None):
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'src'))
    return subprocess.run([interpreter or sys.executable, '-c', code],
                          capture_output=True, text=True, timeout=timeout, env=env)


def reg_raw():
    try:
        return json.loads(REG_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {'servers': []}


def reg_entries(path_abs):
    return [e for e in reg_raw().get('servers', []) if e.get('path') == path_abs]


def listen_pids(port):
    try:
        p = subprocess.run(['lsof', '-nP', '-iTCP:%d' % port, '-sTCP:LISTEN', '-t'],
                           capture_output=True, text=True, timeout=20)
    except Exception:
        return []
    return sorted({int(x) for x in p.stdout.split() if x.strip().isdigit()})


def lock_path_of(path_abs):
    r = py('from http_server_cli.utils import lock_path; print(lock_path(%r))' % path_abs)
    return r.stdout.strip()


def write_lock(path_abs, payload, age_s=0.0):
    lf = lock_path_of(path_abs)
    os.makedirs(os.path.dirname(lf), exist_ok=True)
    with open(lf, 'w', encoding='utf-8') as f:
        f.write(payload if isinstance(payload, str) else json.dumps(payload))
    if age_s:
        old = time.time() - age_s
        os.utime(lf, (old, old))
    return lf


def clear_lock(path_abs):
    lf = lock_path_of(path_abs)
    try:
        os.unlink(lf)
    except OSError:
        pass


def wait_listen(port, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if listen_pids(port):
            return True
        time.sleep(0.1)
    return False


def kill_port(port):
    try:
        hs(['kill', str(port)], timeout=60)
    except Exception:
        pass
    for pid in listen_pids(port):
        try:
            os.kill(pid, 15)
        except OSError:
            pass


def spawn_holder(seconds=30):
    """起一个命令行含 `http_server_cli` 的活进程，用作有效锁 holder。"""
    env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, 'src'))
    return subprocess.Popen([sys.executable, '-c',
                             'import http_server_cli, time; time.sleep(%d)' % seconds],
                            env=env)


def concurrent_starts(target_arg, port, n=5, runner=hs):
    """n 路并发启动同一目标（同端口），返回 (rc 列表, stdout 列表, stderr 列表)。"""
    if port not in STARTED_PORTS:
        STARTED_PORTS.append(port)
    out = [None] * n
    err = [None] * n
    rc = [None] * n

    def go(i):
        try:
            o, e, r = runner([target_arg, '-p', str(port), '--url'], timeout=90)
            out[i], err[i], rc[i] = o, e, r
        except Exception as ex:      # noqa: BLE001
            out[i], err[i], rc[i] = '', str(ex), -1

    ts = [threading.Thread(target=go, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    return rc, out, err


# ── A1/A2 通道 ──────────────────────────────────────────

def a1_a2_channels():
    r = py("from http_server_cli.utils import eprint, print_msg;"
           "eprint('E-CH005'); print_msg('O-CH005')")
    ok = (r.stdout == 'O-CH005\n' and r.stderr == 'E-CH005\n')
    check('A1', ok, 'eprint→stderr=%r / print_msg→stdout=%r' % (r.stderr, r.stdout))
    check('A2', r.stdout == 'O-CH005\n', 'stdout 只含 print_msg 产物：%r' % r.stdout)


# ── A3 三态 stdout 契约 ─────────────────────────────────

def a3_three_states():
    d = demo('a3-default')
    port = 8090
    try:
        o, e, rc = hs([d, '-p', str(port)])
        ok1 = rc == 0 and 'http://' in o
        check('A3-1', ok1, '默认模式 stdout（产物）rc=%d 含 URL=%s stderr=%r'
              % (rc, 'http://' in o, e.strip()[:80]))
        kill_port(port)

        o2, e2, rc2 = hs([d, '-p', str(port), '--url'])
        ok2 = rc2 == 0 and o2.strip().startswith('http://') and len(o2.strip().splitlines()) == 1
        check('A3-2', ok2, '--url stdout 单行 URL=%r（stderr=%r）' % (o2.strip(), e2.strip()[:60]))
        kill_port(port)

        o3, e3, rc3 = hs([d, '-p', str(port), '--json'])
        try:
            env = json.loads(o3)
            ok3 = rc3 == 0 and env.get('success') is True
        except Exception:
            env, ok3 = None, False
        check('A3-3', ok3, '--json stdout 可解析 rc=%d success=%s' % (rc3, (env or {}).get('success')))
        kill_port(port)

        o4, e4, rc4 = hs(['/nonexistent-cl005', '--json'])
        try:
            env4 = json.loads(o4)
            ok4 = (rc4 == 1 and env4.get('success') is False
                   and 'Path does not exist' in (env4.get('error') or ''))
        except Exception:
            env4, ok4 = None, False
        check('A3-4', ok4, '路径不存在 --json：rc=%d 信封 success=%s error 带原因=%s（机器模式错误通道=信封，stdout 可解析）'
              % (rc4, (env4 or {}).get('success'),
                 'Path does not exist' in ((env4 or {}).get('error') or '')))
    finally:
        kill_port(port)


# ── A4 web 退出码矩阵 ───────────────────────────────────

def a4_web_exit_codes():
    name = 'cl005verifysvc'
    rows = []

    def row(label, args, expect, json_mode=False):
        o, e, rc = hs(['web'] + args)
        ok = rc == expect
        extra = ''
        if json_mode:
            try:
                env = json.loads(o)
                ok = ok and env.get('success') is False and env.get('data', {}).get('status') == 'cmd_failed'
                extra = ' status=%s exit=%s' % (env.get('data', {}).get('status'), env.get('data', {}).get('exit_code'))
            except Exception:
                ok = False
                extra = ' 信封不可解析'
        rows.append((label, rc, expect, ok, extra))
        return ok

    try:
        hs(['web', 'remove', name])
        row('add 缺 --cmd', ['add', name], 2)
        row('add 子命令名冲突', ['add', 'list', '--cmd', 'echo a'], 2)
        o, e, rc = hs(['web', 'add', name, '--cmd', 'echo a'])
        rows.append(('add 正常', rc, 0, rc == 0, ''))
        row('add 重复（ValueError）', ['add', name, '--cmd', 'echo b'], 2)
        row('update --cmd 空（ValueError）', ['update', name, '--cmd', ''], 2)
        row('update 无参数', ['update', name], 2)
        row('show 名不存在', ['show', 'nope-cl005'], 1)
        row('remove 名不存在', ['remove', 'nope-cl005'], 1)
        o, e, rc = hs(['web', 'list'])
        rows.append(('list 正常', rc, 0, rc == 0, ''))
        o, e, rc = hs(['web'])
        rows.append(('web 无子命令（help）', rc, 0, rc == 0 and 'hs web' in o, ''))
        # cmd 失败：改注册命令为 exit 3
        hs(['web', 'update', name, '--cmd', 'exit 3'])
        o, e, rc = hs(['web', name, '--no-probe'])
        rows.append(('cmd 失败（默认模式）', rc, 1, rc == 1 and ('code 3' in e),
                     ' stderr=%r' % e.strip()[:60]))
        row('cmd 失败（--json）', [name, '--no-probe', '--json'], 1, json_mode=True)
        # store 损坏 → 1
        SVC_BACKUP_LOCAL = SERVICES_PATH.read_bytes()
        try:
            SERVICES_PATH.write_text('{ broken json', encoding='utf-8')
            o, e, rc = hs(['web', 'list'])
            rows.append(('store 损坏', rc, 1, rc == 1, ''))
        finally:
            SERVICES_PATH.write_bytes(SVC_BACKUP_LOCAL)
    finally:
        hs(['web', 'remove', name])

    bad = [r for r in rows if not r[3]]
    detail = '；'.join('%s%s:rc=%s(期望%s)%s' % ('✔' if r[3] else '✗', r[0], r[1], r[2], r[4]) for r in rows)
    check('A4', not bad, 'web 退出码矩阵 %d/%d 行符合（%s）' % (len(rows) - len(bad), len(rows), detail[:600]))


# ── A5 并发 5 次（含修前反证）────────────────────────────

def _concurrency_sample(runner, tag, port, samples=3):
    """返回 [(样本内登记条数, pid 同一性 bool, 启动次数)]；启动次数由 stdout 中 URL 出现次数不可判 —— 用登记+listener 判。"""
    out_rows = []
    for _ in range(samples):
        d = demo('a5-%s' % tag, index=True)
        kill_port(port)
        rc, so, se = concurrent_starts(d, port, n=5, runner=runner)
        wait_listen(port, timeout=3.0)          # 就绪等待 ≤3s（设计 §6.2 时序纪律）
        entries = reg_entries(d)
        pids = listen_pids(port)
        pid_same = (len(entries) == 1 and len(pids) == 1 and entries[0].get('pid') == pids[0])
        out_rows.append((len(entries), pid_same, len(pids), rc.count(0), sorted(set(rc))))
        kill_port(port)
        clear_lock(d)
    return out_rows


def a5_concurrency():
    port = 8091
    try:
        new_rows = _concurrency_sample(hs, 'new', port)
        ok_new = all(r[0] == 1 and r[1] for r in new_rows)
        check('A5-1', ok_new, '新实现 5 并发 ×3 样本 → %r（登记数, pid 同一, listener 数, rc0 数, rc 集合）' % (new_rows,))
    finally:
        kill_port(port)

    # 修前反证
    try:
        subprocess.run(['git', 'worktree', 'add', '--detach', WORKTREE, BASE_COMMIT],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
        port = 8092
        old_rows = _concurrency_sample(hs_old, 'old', port)
        inconsistent = [r for r in old_rows if not (r[0] == 1 and r[1])]
        ok_old = len(inconsistent) >= 1
        check('A5-2', ok_old, '修前反证（worktree %s）→ %r；不一致样本 %d/%d（≥1 即成立）'
              % (BASE_COMMIT, old_rows, len(inconsistent), len(old_rows)))
    finally:
        kill_port(8092)
        subprocess.run(['git', 'worktree', 'remove', '--force', WORKTREE],
                       cwd=ROOT, capture_output=True, text=True)


# ── A6/A7/A8 锁协议 ─────────────────────────────────────

def a6_valid_lock_fail_closed():
    d = demo('a6')
    port = 8093
    holder = spawn_holder()
    try:
        lf = write_lock(d, {'path': d, 'pid': holder.pid,
                            'started_mono': float(py("from http_server_cli.utils import mono_now; print(mono_now())").stdout.strip()),
                            'started_at': '2026-09-23 00:00:00'})
        t0 = time.time()
        o, e, rc = hs([d, '-p', str(port)])
        dt = time.time() - t0
        ok = rc == 1 and '正在启动' in e and os.path.exists(lf) and not listen_pids(port)
        check('A6', ok, '有效锁 → rc=%d（%.1fs）stderr 含「正在启动」=%s 锁保留=%s 未启动=%s'
              % (rc, dt, '正在启动' in e, os.path.exists(lf), not listen_pids(port)))
    finally:
        holder.kill()
        holder.wait()
        clear_lock(d)
        kill_port(port)


def a7_stale_self_heal():
    d = demo('a7')
    port = 8094
    cases = []
    try:
        # (a) 无 pid + 陈旧 mtime
        write_lock(d, {'path': d, 'started_at': ''}, age_s=5.0)
        o, e, rc = hs([d, '-p', str(port), '--url'])
        cases.append(('无 pid（陈旧）', rc, not os.path.exists(lock_path_of(d))))
        kill_port(port)
        clear_lock(d)
        # (b) pid 死
        write_lock(d, {'path': d, 'pid': 999999, 'started_mono': 1.0, 'started_at': ''})
        o, e, rc = hs([d, '-p', str(port), '--url'])
        cases.append(('pid 死', rc, not os.path.exists(lock_path_of(d))))
        kill_port(port)
        clear_lock(d)
        # (c) TTL 超时（pid 活 + 命令行命中本 CLI）
        holder = spawn_holder(seconds=20)
        try:
            mono = float(py("from http_server_cli.utils import mono_now; print(mono_now())").stdout.strip())
            write_lock(d, {'path': d, 'pid': holder.pid, 'started_mono': mono - 40.0, 'started_at': ''})
            o, e, rc = hs([d, '-p', str(port), '--url'])
            cases.append(('超 TTL', rc, not os.path.exists(lock_path_of(d))))
        finally:
            holder.kill()
            holder.wait()
    finally:
        kill_port(port)
        clear_lock(d)

    ok = all(c[1] == 0 and c[2] for c in cases)
    check('A7', ok, 'stale 三态自愈 %r（(用例, rc, 锁已清)）' % (cases,))
    return ok


def a8_no_lock_residue():
    leftovers = []
    if LOCK_DIR.exists():
        for f in LOCK_DIR.iterdir():
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
            except Exception:
                continue
            if (data.get('path') or '') in TEMP_PATHS:
                leftovers.append(f.name)
    check('A8', not leftovers, '注入目录无锁残留（残留=%r，锁目录当前 %d 个文件）'
          % (leftovers, len(list(LOCK_DIR.iterdir())) if LOCK_DIR.exists() else 0))


# ── A9 派发件模板 ───────────────────────────────────────

def a9_dispatch_template():
    script = os.path.join(ROOT, 'scripts', 'review-dispatch.sh')
    # (a) dry-run 双步骤三路径
    r1 = subprocess.run(['bash', script, '--target', ROOT, '--code', 'http-server-cl005',
                         '--project', 'http-server.cli', '--step', 'audit',
                         '--date', '20260923', '--prompt', 'documents/http-server-cl005-hardening-design-v1.2-20260923.md',
                         '--dry-run'], capture_output=True, text=True, timeout=60)
    ok1 = (r1.returncode == 0
           and 'HTTP-SERVER-CL005-audit-dispatch.log' in r1.stdout
           and '20260923-http-server.cli-HTTP-SERVER-CL005-audit.json' in r1.stdout
           and 'HTTP-SERVER-CL005' in r1.stdout)
    # (b) 缺参 rc≠0
    r2 = subprocess.run(['bash', script, '--dry-run'], capture_output=True, text=True, timeout=60)
    ok2 = r2.returncode == 2
    # (c) 真实派发链路（hermes 用桩替换）→ usage-file 非空
    stubdir = os.path.join(WORK, 'stub-bin')
    shutil.rmtree(stubdir, ignore_errors=True)
    os.makedirs(stubdir)
    stub = os.path.join(stubdir, 'hermes')
    with open(stub, 'w', encoding='utf-8') as f:
        f.write('#!/bin/bash\n'
                'usage=""; while [ $# -gt 0 ]; do case "$1" in --usage-file) usage="$2"; shift 2;; '
                '*) shift;; esac; done\n'
                'printf \'{"stub": true}\\n\' > "$usage"\n'
                'echo "STUB-DISPATCH ok"\n')
    os.chmod(stub, 0o755)
    tgt = os.path.join(WORK, 'fake-repo')
    shutil.rmtree(tgt, ignore_errors=True)
    os.makedirs(os.path.join(tgt, 'cache', 'review-prep'))
    os.makedirs(os.path.join(tgt, 'cache', 'closed-loop'))
    with open(os.path.join(tgt, 'cache', 'review-prep', 'p.md'), 'w', encoding='utf-8') as f:
        f.write('提示词内容')
    env = dict(os.environ, PATH=stubdir + ':' + os.environ['PATH'])
    r3 = subprocess.run(['bash', script, '--target', tgt, '--code', 'HTTP-SERVER-CL005',
                         '--project', 'http-server.cli', '--step', 'audit', '--date', '20260923',
                         '--prompt', 'cache/review-prep/p.md'],
                        capture_output=True, text=True, timeout=120, env=env)
    usage = os.path.join(tgt, 'cache', 'closed-loop',
                         '20260923-http-server.cli-HTTP-SERVER-CL005-audit.json')
    ok3 = r3.returncode == 0 and os.path.exists(usage) and os.path.getsize(usage) > 0
    check('A9', ok1 and ok2 and ok3,
          '派发件：dry-run 三路径=%s / 缺参 rc=%d / 桩派发 usage 非空=%s（%s）'
          % (ok1, r2.returncode, ok3, os.path.basename(usage)))


# ── A10/A11 回归 ────────────────────────────────────────

def a10_legacy_harness():
    out = []
    for script, sid in (('port-flag-verify.py', 'CL003'), ('port-residual-verify.py', 'CL004')):
        p = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', script)],
                           capture_output=True, text=True, timeout=900, cwd=ROOT)
        tail = p.stdout.strip().splitlines()[-3:]
        n_pass = p.stdout.count('[PASS]')
        n_fail = p.stdout.count('[FAIL]')
        out.append((script, n_pass, n_fail, tail))
    ok = all(r[2] == 0 and r[1] > 0 for r in out)
    check('A10', ok, '既有 harness 回归：%s' % '；'.join('%s PASS=%d FAIL=%d' % (r[0], r[1], r[2]) for r in out))


def a11_full_pytest():
    p = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-q', '-n', '4'],
                       capture_output=True, text=True, timeout=900, cwd=ROOT)
    last = [l for l in p.stdout.strip().splitlines() if 'passed' in l or 'failed' in l]
    txt = last[-1] if last else p.stdout.strip().splitlines()[-1]
    import re
    m = re.search(r'(\d+) passed', txt)
    f = re.search(r'(\d+) failed', txt)
    n_pass = int(m.group(1)) if m else 0
    n_fail = int(f.group(1)) if f else 0
    check('A11', n_fail == 0 and n_pass >= 582, '全量 pytest：%s' % txt[:120])


# ── A12 四同步 ──────────────────────────────────────────

def a12_sync():
    o, e, rc = hs(['version'])
    ver_ok = 'v1.4.1' in o
    ch = Path(ROOT, 'CHANGELOG.md').read_text(encoding='utf-8')
    chg_ok = '## 1.4.1 (2026-09-23)' in ch and '目录级启动锁' in ch
    feat = Path(ROOT, 'features.md').read_text(encoding='utf-8')
    feat_ok = '17 个测试模块，590 个测试用例' in feat
    ls = subprocess.run(['git', 'ls-files', 'tests/test_*.py'], cwd=ROOT,
                        capture_output=True, text=True).stdout.split()
    n_mod = len(set(ls))
    spec = Path(ROOT, 'http-server.cli.spec.yaml').read_text(encoding='utf-8')
    spec_ok = ('version: 1.4.1' in spec) and ('lifecycle-07' in spec) and ('lifecycle-08' in spec) and ('cli-06' in spec)
    rd = Path(ROOT, 'README.md').read_text(encoding='utf-8')
    rdz = Path(ROOT, 'README.zh.md').read_text(encoding='utf-8')
    readme_ok = ('Exit codes (CL005)' in rd) and ('退出码（CL005）' in rdz)
    n_pass = sum([ver_ok, chg_ok, feat_ok, spec_ok, readme_ok])
    check('A12', n_pass == 5 and n_mod == 17,
          '四同步：version=%s CHANGELOG=%s features=%s spec=%s README=%s 测试模块数=%d'
          % (ver_ok, chg_ok, feat_ok, spec_ok, readme_ok, n_mod))


# ── A13 残留 0 ──────────────────────────────────────────

def a13_no_residue():
    # registry 复原（忽略 last_access_at 漂移）
    def norm(data):
        out = []
        for e in data.get('servers', []):
            e2 = {k: v for k, v in e.items() if k != 'last_access_at'}
            out.append(json.dumps(e2, sort_keys=True, ensure_ascii=False))
        return sorted(out)

    before = json.loads(REG_BACKUP.decode('utf-8')) if REG_BACKUP else {'servers': []}
    after = reg_raw()
    reg_ok = norm(before) == norm(after)
    svc_ok = SERVICES_PATH.read_bytes() == SVC_BACKUP if SVC_BACKUP else True
    today = [e for e in after.get('servers', []) if (e.get('path') or '') in TEMP_PATHS]
    # 本次启动过的端口 listener 应清空
    listen_left = {p: listen_pids(p) for p in STARTED_PORTS if listen_pids(p)}
    locks_left = []
    if LOCK_DIR.exists():
        for f in LOCK_DIR.iterdir():
            try:
                if (json.loads(f.read_text(encoding='utf-8')).get('path') or '') in TEMP_PATHS:
                    locks_left.append(f.name)
            except Exception:
                continue
    ok = reg_ok and svc_ok and not today and not listen_left and not locks_left
    check('A13', ok, '残留 0：registry 复原=%s services 复原=%s 临时条目=%d 遗留 listener=%r 遗留锁=%r'
          % (reg_ok, svc_ok, len(today), listen_left, locks_left))


# ── A14 未越界 ──────────────────────────────────────────

def a14_no_scope_creep():
    diff_names = subprocess.run(['git', 'diff', '--name-only', BASE_COMMIT + '..HEAD', '--', 'src/'],
                                cwd=ROOT, capture_output=True, text=True).stdout.split()
    reg_untouched = 'src/http_server_cli/registry.py' not in diff_names
    raw = subprocess.run(['git', 'diff', '-U0', BASE_COMMIT + '..HEAD', '--', 'src/'],
                         cwd=ROOT, capture_output=True, text=True).stdout
    added = [l for l in raw.splitlines()
             if l.startswith('+') and not l.startswith('+++')]
    no_reserved = not any(('8180' in l or '8181' in l) for l in added)
    no_maxport = not any('MAX_PORT' in l for l in added)
    # set 语义：与基线行为逐条一致（config 字节级不变；O7「rc 仍 0」为已登记观察项，非本批范围）
    cfg = HOME / 'config.json'
    cfg_backup = cfg.read_bytes()
    try:
        rows = []
        for args in (['set', 'port', '70000'], ['set', 'port', 'abc']):
            o_n, e_n, rc_n = hs(args)
            same_n = cfg.read_bytes() == cfg_backup
            o_b, e_b, rc_b = hs_old(args)
            same_b = cfg.read_bytes() == cfg_backup
            rows.append((args[-1], rc_n, rc_b, same_n, same_b))
        set_ok = all((r[1] == r[2]) and r[3] and r[4] for r in rows)
    finally:
        cfg.write_bytes(cfg_backup)
    ok = reg_untouched and no_reserved and no_maxport and set_ok
    check('A14', ok, '未越界：registry.py 未改=%s 新增行无保留端口=%s 新增行无 MAX_PORT=%s '
                     'set 语义（越界/非法 rc=2 且 config 未变）=%s（改动文件=%r）'
          % (reg_untouched, no_reserved, no_maxport, set_ok, diff_names))


# ── A15 html 同锁 + mid-write ───────────────────────────

def a15_html_lock_and_midwrite():
    d = demo('a15', index=False, extra={'page.html': '<h1>page</h1>'})
    port = 8095
    dt = 0.0
    try:
        kill_port(port)
        # html 入口起一个
        o, e, r = hs([os.path.join(d, 'page.html'), '-p', str(port), '--url'])
        wait_listen(port, timeout=3.0)
        entries = reg_entries(d)
        pids = listen_pids(port)
        same_key = lock_path_of(d) == lock_path_of(d)
        entry_ok = (r == 0 and len(entries) == 1 and entries[0].get('index_page') == 'page.html'
                    and entries[0].get('pid') in pids)
        # 第二个入口（目录）应幂等命中同一条
        o2, e2, r2 = hs([d, '-p', str(port), '--url'])
        entries2 = reg_entries(d)
        idem_ok = r2 == 0 and len(entries2) == 1 and entries2[0].get('pid') == entries[0].get('pid')
        kill_port(port)
        clear_lock(d)
    finally:
        kill_port(port)

    # mid-write：空锁 + 新鲜 mtime ⇒ 等待不删
    try:
        lf = write_lock(d, '', age_s=0.0)
        t0 = time.time()
        o, e, rc = hs([d, '-p', str(port)], timeout=90)
        dt = time.time() - t0
        mid_ok = rc == 1 and os.path.exists(lf)
        clear_lock(d)
    except Exception as ex:      # noqa: BLE001
        mid_ok = False
        print('   mid-write 异常:', ex)

    check('A15', entry_ok and idem_ok and mid_ok,
          'html 入口同锁：登记 1 条且 index_page=page.html=%s / 目录入口幂等=%s / mid-write 不删锁 rc=1=%s（%.1fs）｜entries=%r pids=%r'
          % (entry_ok, idem_ok, mid_ok, dt,
             [{k: e.get(k) for k in ('port', 'pid', 'index_page')} for e in entries2], pids))


# ── A16 归属/回滚 ───────────────────────────────────────

def a16_ownership():
    d = demo('a16')
    port = 8096
    holder = spawn_holder()
    try:
        lf = write_lock(d, {'path': d, 'pid': holder.pid, 'started_mono': 1.0, 'started_at': ''})
        # 让 started_mono 合理（避免误判 TTL）
        mono = float(py("from http_server_cli.utils import mono_now; print(mono_now())").stdout.strip())
        write_lock(d, {'path': d, 'pid': holder.pid, 'started_mono': mono, 'started_at': ''})
        hs([d, '-p', str(port)])
        owner_ok = os.path.exists(lf) and not listen_pids(port)
        check('A16', owner_ok, 'release 归属：他人有效锁未被删=%s 且未启动 runner=%s'
              % (os.path.exists(lf), not listen_pids(port)))
    finally:
        holder.kill()
        holder.wait()
        clear_lock(d)
        kill_port(port)


# ── A17 daemon 释放 + 时钟跨解释器 ──────────────────────

def a17_daemon_and_clock():
    d = demo('a17')
    port = 8097
    proc = None
    try:
        env = dict(os.environ)
        proc = subprocess.Popen(['hs', d, '-p', str(port), '-d'], cwd=ROOT, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        ready = wait_listen(port, timeout=5.0)
        lf = lock_path_of(d)
        lock_held = os.path.exists(lf)
        # 第二实例：daemon tail 期间 ⇒ 幂等快径 rc=0
        o, e, rc = hs([d, '-p', str(port), '--url'])
        idem_ok = rc == 0
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        # 释放或自愈（SIGTERM 未走 finally ⇒ 判 stale 自愈）
        clear_lock(d) if not os.path.exists(lf) else None
        if os.path.exists(lf):
            o2, e2, rc2 = hs([d, '-p', str(port), '--url'])
            heal_ok = rc2 == 0
        else:
            heal_ok = True
        kill_port(port)
        clear_lock(d)
        daemon_ok = bool(ready and lock_held and idem_ok and heal_ok)
    finally:
        if proc and proc.poll() is None:
            proc.kill()
        kill_port(port)
        clear_lock(d)

    # 时钟跨解释器（T26）
    code = ("import sys; sys.path.insert(0, %r);"
            "from http_server_cli.utils import mono_now; print(repr(mono_now()))" % os.path.join(ROOT, 'src'))
    interps = [sys.executable] + [p for p in ['/usr/bin/python3'] if os.path.exists(p)]
    clock_rows = []
    for interp in interps:
        vals = []
        for _ in range(2):
            r = subprocess.run([interp, '-c', code], capture_output=True, text=True, timeout=60)
            vals.append(float(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None)
        clock_rows.append((interp, vals))
    clock_ok = all(v[0] and v[1] and v[0] > 1e4 and abs(v[0] - v[1]) < 60 for _, v in clock_rows)
    check('A17', daemon_ok and clock_ok,
          'daemon：就绪=%s 持锁=%s 二次幂等 rc=0=%s 释放/自愈=%s ｜ 时钟跨解释器可比=%s %r'
          % (ready, lock_held, idem_ok, heal_ok, clock_ok, clock_rows))


# ── 主流程 ──────────────────────────────────────────────

ALL = ['A1', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8', 'A9', 'A10', 'A11', 'A12', 'A13', 'A14', 'A15', 'A16', 'A17']


def main():
    global LOCKS_BEFORE, REG_BACKUP, SVC_BACKUP, ONLY
    if '--only' in sys.argv:
        ONLY = sys.argv[sys.argv.index('--only') + 1].split(',')
    os.makedirs(os.path.join(ROOT, 'cache', 'closed-loop'), exist_ok=True)
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)

    REG_BACKUP = REG_PATH.read_bytes() if REG_PATH.exists() else b''
    SVC_BACKUP = SERVICES_PATH.read_bytes() if SERVICES_PATH.exists() else b''
    LOCKS_BEFORE = sorted(p.name for p in LOCK_DIR.iterdir()) if LOCK_DIR.exists() else []

    print('=== CL005 ops 核查（%s）===' % time.strftime('%F %T'))
    started = time.time()
    def wanted(aid):
        return (not ONLY) or any(aid == x or aid.startswith(x + '-') for x in ONLY)

    # 顺序：不依赖本次服务的断言先跑（避免与既有 harness 的端口/进程判定互相干扰），A13（残留 0）恒最后
    steps = [('A1', a1_a2_channels), ('A10', a10_legacy_harness), ('A11', a11_full_pytest),
             ('A12', a12_sync), ('A14', a14_no_scope_creep),
             ('A3', a3_three_states), ('A4', a4_web_exit_codes), ('A5', a5_concurrency),
             ('A6', a6_valid_lock_fail_closed), ('A7', a7_stale_self_heal), ('A8', a8_no_lock_residue),
             ('A9', a9_dispatch_template), ('A15', a15_html_lock_and_midwrite),
             ('A16', a16_ownership), ('A17', a17_daemon_and_clock), ('A13', a13_no_residue)]
    try:
        for aid, fn in steps:
            if wanted(aid):
                fn()
    finally:
        # 复原数据目录（registry / services）
        if REG_BACKUP:
            REG_PATH.write_bytes(REG_BACKUP)
        if SVC_BACKUP:
            SERVICES_PATH.write_bytes(SVC_BACKUP)
        for p in STARTED_PORTS:
            kill_port(p)
        shutil.rmtree(WORK, ignore_errors=True)
        subprocess.run(['git', 'worktree', 'remove', '--force', WORKTREE], cwd=ROOT,
                       capture_output=True, text=True)

    n_pass = sum(1 for r in RESULTS if r['ok'])
    print('\n=== 汇总：%d/%d PASS（用时 %.1fs）===' % (n_pass, len(RESULTS), time.time() - started))
    for r in RESULTS:
        if not r['ok']:
            print('  ❌ %s %s' % (r['id'], r['detail']))
    Path(JSON_OUT).write_text(json.dumps({
        'step': 'CL005-ops-verify', 'ts': time.strftime('%F %T'),
        'pass': n_pass, 'total': len(RESULTS), 'results': RESULTS,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print('产物：%s' % JSON_OUT)
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == '__main__':
    sys.exit(main())
