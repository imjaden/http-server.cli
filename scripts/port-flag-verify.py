#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTTP-SERVER-CL003 ops 核查 harness —— 设计 v1.1 §8 A 段断言表（A1–A17），可复跑。

用法：python3 scripts/port-flag-verify.py
产物：stdout 逐条 PASS/FAIL + cache/closed-loop/20260922-http-server.cli-HTTP-SERVER-CL003-ops-verify.json

注意（设计 §13.3）：
  · fail-closed 类用例**每条用不同目录**（同一路径第二次调用命中幂等分支，会掩盖断言）
  · registry 的 path 为 realpath（macOS /tmp → /private/tmp）
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = '/Users/jadenli/CodeSpace/http-server.cli'
WORK = '/tmp/hs-cl003-verify'
PREFIX_WORKTREE = '/tmp/hs-cl003-prefix'
BASE_COMMIT = '076d30b'          # Step 3 之前（设计 v1.1 勘误）⇒ 修前反证基线
RESULTS = []
PORTS_TO_KILL = []
JSON_OUT = os.path.join(ROOT, 'cache', 'closed-loop',
                        '20260922-http-server.cli-HTTP-SERVER-CL003-ops-verify.json')


def run(args, env=None, timeout=120):
    p = subprocess.run(['hs'] + args, capture_output=True, text=True,
                       timeout=timeout, env=env, cwd=ROOT)
    return p.stdout, p.stderr, p.returncode


def check(aid, ok, detail):
    RESULTS.append({'id': aid, 'ok': bool(ok), 'detail': detail})
    print('[%s] %s %s' % ('PASS' if ok else 'FAIL', aid, detail), flush=True)


def demo(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f:
        f.write('<h1>%s</h1>' % name)
    return d


def realpath(p):
    return os.path.realpath(p)


def port_of(text):
    m = re.search(r':(\d{2,5})', text or '')
    return int(m.group(1)) if m else None


def list_json():
    out, _, _ = run(['list', '--json'])
    try:
        d = json.loads(out)
    except Exception:
        return []
    data = d.get('data')
    return data if isinstance(data, list) else (data or {}).get('servers', [])


def entry_for(path, tries=8, delay=0.4):
    """registry 条目查询（带重试：start 返回后 registry/list 存在数十~数百 ms 写入延迟）。"""
    rp = realpath(path)
    for _ in range(tries):
        for e in list_json():
            if realpath(str(e.get('path', ''))) == rp:
                return e
        time.sleep(delay)
    return None


def kill_all_tracked():
    for p in PORTS_TO_KILL:
        run(['kill', str(p)])
    for d in (WORK,):
        shutil.rmtree(d, ignore_errors=True)


# ── A1 / A2 ────────────────────────────────────────────────
def a1_a2():
    d = demo('a1')
    out, err, rc = run([d, '-p', '8099', '-d', '--url'])
    port = port_of(out)
    PORTS_TO_KILL.append(8099)
    check('A1', rc == 0 and port == 8099 and 'unknown command' not in out.lower(),
          '`hs <dir> -p 8099 -d --url` → rc=%s url=%s err=%r' % (rc, out.strip()[:90], err.strip()[:60]))
    e = entry_for(d)
    check('A1-b', e is not None and e.get('port') == 8099,
          'hs list --json 该条 port=%s（path=%s）' % (e and e.get('port'), e and e.get('path')))
    # A2 修前反证：临时 worktree 载入修前源码，同命令必须**得不到** 8099
    subprocess.run(['git', 'worktree', 'remove', '--force', PREFIX_WORKTREE],
                   cwd=ROOT, capture_output=True)
    subprocess.run(['git', 'worktree', 'add', '--detach', PREFIX_WORKTREE, BASE_COMMIT],
                   cwd=ROOT, capture_output=True)
    env = dict(os.environ, PYTHONPATH=os.path.join(PREFIX_WORKTREE, 'src'))
    probe = subprocess.run([sys.executable, '-c', 'import http_server_cli;print(http_server_cli.__file__)'],
                           capture_output=True, text=True, env=env)
    d2 = demo('a2')
    out2, err2, rc2 = run([d2, '-p', '8099', '-d', '--url'], env=env)
    port2 = port_of(out2)
    if port2:
        PORTS_TO_KILL.append(port2)
    check('A2', 'prefix' in probe.stdout and port2 != 8099,
          '修前源码(%s)同命令 → rc=%s port=%s（非 8099 ⇒ 判据非恒真）' % (
              probe.stdout.strip().split('/src/')[-1][:12], rc2, port2))
    return d


def a3(d):
    out, err, rc = run([d, '-p', '8080'])
    ok = rc == 1 and '已被占用' in err and 'PID' in err
    check('A3', ok, '`hs <dir> -p 8080`（8080 在跑）→ rc=%s stderr=%r' % (rc, err.strip().replace('\n', ' | ')[:130]))


def a4(d):
    for port in (8180, 8181):
        out, err, rc = run([demo('a4-%s' % port), '-p', str(port)])
        ok = rc == 1 and '保留端口' in err and 'hs dashboard -p' in err
        check('A4-%s' % port, ok, '空闲态 → rc=%s stderr=%r' % (rc, err.strip().replace('\n', ' | ')[:130]))


def a5(d):
    for arg, label in (('99', '区间'), ('abc', '非法值')):
        out, err, rc = run([demo('a5-%s' % label), '-p', arg])
        ok = rc == 2 and ('1024-65535' in err + out if label == '区间' else 'invalid int value' in err + out)
        check('A5-%s' % label, ok, '`-p %s` → rc=%s out/err=%r' % (label and arg, rc, (out + err).strip().replace('\n', ' | ')[:110]))


def a6(a1dir):
    out, err, rc = run([a1dir, '--prot', '8080'])
    ok = rc == 0 and '未识别参数' in err and '--prot' in err and '未识别参数' not in out
    check('A6', ok, '`hs <a1dir> --prot 8080` → rc=%s stderr=%r stdout_has_warn=%s' % (
        rc, err.strip().replace('\n', ' | ')[:120], '未识别参数' in out))
    out2, err2, rc2 = run(['list', '--prot'])
    check('A6-b', rc2 == 0 and '未识别参数' in err2 and '未识别参数' not in out2,
          '`hs list --prot`（不启动服务路径）→ rc=%s stderr=%r' % (rc2, err2.strip().replace('\n', ' | ')[:110]))


def a7():
    d = demo('a7')
    out, err, rc = run([d, '-p', '8097', '-d', '--json'])
    PORTS_TO_KILL.append(8097)
    try:
        payload = json.loads(out)
        port = payload['data']['port']
    except Exception as exc:
        payload, port = {'parse_error': str(exc)}, None
    check('A7', rc == 0 and port == 8097, '`-p 8097 --json` → data.port=%s rc=%s' % (port, rc))


def a8():
    d = demo('a8a')
    out, err, rc = run(['-p', '8096', '-d', '--url', d])
    PORTS_TO_KILL.append(8096)
    check('A8-1', rc == 0 and port_of(out) == 8096 and 'unknown command' not in out.lower(),
          '`hs -p 8096 -d --url <dir>` → rc=%s out=%r' % (rc, out.strip()[:80]))
    d2 = demo('a8b')
    out2, err2, rc2 = run(['-i', 'index.html', '-p', '8095', '-d', '--url', d2])
    PORTS_TO_KILL.append(8095)
    check('A8-2', rc2 == 0 and port_of(out2) == 8095 and 'unknown command' not in out2.lower(),
          '`hs -i index.html -p 8095 -d --url <dir>` → rc=%s out=%r' % (rc2, out2.strip()[:80]))


def a9(a1dir):
    out, err, rc = run([a1dir, '-p', '8500', '-d', '--url'])
    ok = rc == 0 and port_of(out) == 8099 and '已运行在 8099' in err and '8500' in err
    check('A9', ok, '同目录再启动 + `-p 8500` → rc=%s url_port=%s stderr=%r' % (
        rc, port_of(out), err.strip().replace('\n', ' | ')[:120]))
    hits = [e for e in list_json() if realpath(str(e.get('path', ''))) == realpath(a1dir)]
    check('A9-b', len(hits) == 1 and hits[0].get('port') == 8099,
          'registry 该路径仅 1 条且 port=8099（实际 %s 条）' % len(hits))


def a10():
    run(['dashboard', 'stop'])
    out, err, rc = run(['dashboard', '-p', '8280', '-d'])
    time.sleep(1.5)
    o1, _, _ = run(['dashboard', 'status', '--json'])
    p1 = None
    try:
        p1 = json.loads(o1)['data'].get('port')
    except Exception:
        pass
    check('A10-1', p1 == 8280, '`hs dashboard -p 8280 -d` → status port=%s' % p1)
    out2, err2, rc2 = run(['dashboard', 'restart', '--port', '8290'])
    time.sleep(1.8)
    o2, _, _ = run(['dashboard', 'status', '--json'])
    p2 = None
    try:
        p2 = json.loads(o2)['data'].get('port')
    except Exception:
        pass
    check('A10-2', p2 == 8290, '`restart --port 8290` → status port=%s（rc=%s）' % (p2, rc2))
    run(['dashboard', 'restart'])
    time.sleep(1.8)
    o3, _, _ = run(['dashboard', 'status', '--json'])
    p3 = None
    try:
        p3 = json.loads(o3)['data'].get('port')
    except Exception:
        pass
    check('A10-3', p3 == 8290, '`restart`（无 --port）→ 沿用 entry 端口 → status port=%s' % p3)
    run(['dashboard', 'stop'])
    PORTS_TO_KILL.extend([8280, 8290])


def a11():
    run(['web', 'remove', 'cl003-demo'])
    out, err, rc = run(['web', 'add', 'cl003-demo', '--cmd', 'true', '--port', '9001'])
    out2, err2, rc2 = run(['web', 'cl003-demo', '--no-probe', '--json'])
    eff = ''
    try:
        eff = json.loads(out2)['data'].get('cmd_effective', '')
    except Exception:
        eff = out2[:80]
    check('A11', '--port 9001' in eff, '`web cl003-demo --json` cmd_effective=%r' % eff)
    o3, _, _ = run(['web', 'show', 'cl003-demo', '--json'])
    ok3 = '9001' in o3
    check('A11-b', ok3, '`web show --json` 含端口 9001=%s' % ok3)
    run(['web', 'remove', 'cl003-demo'])
    o4, _, _ = run(['web', 'list', '--json'])
    check('A11-c', 'cl003-demo' not in o4, '清理：web remove 后列表无 cl003-demo')


def a12():
    r = subprocess.run(['grep', '-rn', '不占用终端', 'src/', 'skills/', 'README.md', 'README.zh.md'],
                       cwd=ROOT, capture_output=True, text=True)
    check('A12', r.returncode == 1 and not r.stdout.strip(),
          'grep「不占用终端」src/skills/README×2 → 命中 %d 行' % len(r.stdout.strip().splitlines()))


def _pytest_candidates():
    """pytest 解释器候选：后台/无 conda 环境上下文里 sys.executable 可能不含 pytest（见 skill pitfall #6）。"""
    py312 = '/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python3.12'
    out = []
    if os.environ.get('HS_VERIFY_PY'):
        out.append((os.environ['HS_VERIFY_PY'], [os.environ['HS_VERIFY_PY'], '-m', 'pytest']))
    if os.path.exists(py312):
        out.append((py312, [py312, '-m', 'pytest']))
    out.append((sys.executable, [sys.executable, '-m', 'pytest']))
    return out


def a13():
    env = dict(os.environ, PYTHONPATH='src')
    last = ''
    for label, base in _pytest_candidates():
        p = subprocess.run(base + ['tests/', '-q'], cwd=ROOT,
                           capture_output=True, text=True, env=env, timeout=600)
        tail = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ''
        n = re.search(r'(\d+) passed', tail)
        if p.returncode == 0 and n and int(n.group(1)) >= 490:
            check('A13', True, 'pytest(%s) → %s' % (os.path.basename(label), tail))
            return
        last = '(%s) rc=%s out=%r err=%r' % (os.path.basename(label), p.returncode, tail,
                                             p.stderr.strip()[-180:])
    check('A13', False, 'pytest 全部解释器候选失败 → %s' % last)


def a14():
    out, _, _ = run(['version'])
    ok = 'v1.4.0' in out
    check('A14-1', ok, '`hs version` → %r' % out.strip())
    g1 = subprocess.run(['grep', '-n', "__version__ = '1.4.0'", 'src/http_server_cli/__init__.py'],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    g2 = subprocess.run(['grep', '-n', '^## 1.4.0', 'CHANGELOG.md'],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    g3 = subprocess.run(['grep', '-n', '^version: 1.4.0', 'http-server.cli.spec.yaml'],
                        cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check('A14-2', all([g1, g2, g3]), '__init__=%r CHANGELOG=%r spec=%r' % (g1, g2, g3))


def a15():
    out, err, rc = run(['/nonexistent-cl003-xyz'])
    check('A15-1', rc == 1, '`hs /nonexistent` → rc=%s out=%r' % (rc, (out + err).strip()[:80]))
    out2, err2, rc2 = run(['kill', '59999'])
    check('A15-2', rc2 == 1, '`hs kill 59999` → rc=%s out=%r' % (rc2, (out2 + err2).strip()[:80]))
    out3, err3, rc3 = run(['status', '59999'])
    check('A15-3', rc3 == 0, '`hs status 59999`（D14 保持 0）→ rc=%s' % rc3)


def a16():
    run(['dashboard', 'stop'])
    d = demo('a16')
    run(['dashboard', '-p', '8180', '-d'])
    time.sleep(1.8)
    out, err, rc = run([d, '-p', '8180'])
    ok_occ = rc == 1 and '正在使用' in err and 'PID' in err
    check('A16-占用态', ok_occ, 'dashboard 在 8180 时 `-p 8180` → rc=%s stderr=%r' % (
        rc, err.strip().replace('\n', ' | ')[:120]))
    run(['dashboard', 'stop'])
    PORTS_TO_KILL.append(8180)
    time.sleep(1.0)
    out2, err2, rc2 = run([d, '-p', '8180'])
    ok_free = rc2 == 1 and '如需启动请用 hs dashboard -p 8180' in err2
    check('A16-空闲态', ok_free, 'dashboard 停后 `-p 8180` → rc=%s stderr=%r' % (
        rc2, err2.strip().replace('\n', ' | ')[:120]))


def a17():
    g = subprocess.run(['grep', '-n', '1.3.1', 'CHANGELOG.md'], cwd=ROOT, capture_output=True, text=True)
    check('A17', '1.4.0' in open(os.path.join(ROOT, 'CHANGELOG.md'), encoding='utf-8').read() and '1.3.1' in g.stdout,
          'CHANGELOG 1.4.0 条目内含 1.3.1 补注：%r' % g.stdout.strip().splitlines()[:1])


def main():
    os.makedirs(WORK, exist_ok=True)
    print('=== HTTP-SERVER-CL003 ops 核查 harness（A1–A17）===', flush=True)
    try:
        a1dir = a1_a2()
        a3(demo('a3'))
        a4(demo('a4'))
        a5(demo('a5'))
        a6(a1dir)
        a7()
        a8()
        a9(a1dir)
        a10()
        a11()
        a12()
        a13()
        a14()
        a15()
        a16()
        a17()
    finally:
        run(['dashboard', 'stop'])
        kill_all_tracked()
        subprocess.run(['git', 'worktree', 'remove', '--force', PREFIX_WORKTREE],
                       cwd=ROOT, capture_output=True)
        for p in PORTS_TO_KILL + [8099, 8097, 8096, 8095]:
            run(['kill', str(p)])

    passed = sum(1 for r in RESULTS if r['ok'])
    total = len(RESULTS)
    print('\n=== 结论：%d/%d PASS ===' % (passed, total), flush=True)
    for r in RESULTS:
        if not r['ok']:
            print('  FAIL %s: %s' % (r['id'], r['detail']))
    residue = [e for e in list_json() if 'cl003' in str(e.get('path', '')).lower()]
    print('残留检查：registry 中 cl003 条目 %d 条' % len(residue), flush=True)
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
    with open(JSON_OUT, 'w', encoding='utf-8') as f:
        json.dump({'assertion': 'HTTP-SERVER-CL003 ops verify (A1-A17)', 'date': '2026-09-22',
                   'passed': passed, 'total': total, 'results': RESULTS,
                   'residue': residue}, f, ensure_ascii=False, indent=2)
    print('结果写入 %s' % JSON_OUT, flush=True)
    return 0 if passed == total else 1


if __name__ == '__main__':
    sys.exit(main())
