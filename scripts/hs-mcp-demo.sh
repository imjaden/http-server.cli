#!/usr/bin/env bash
# =============================================================================
# hs-mcp-demo.sh — MCP 集成示例脚本
#
# 演示通过 curl 与 hs mcp SSE 服务器进行 MCP 协议交互：
#   1. 初始化握手 (initialize)
#   2. 列出工具 (tools/list)
#   3. 调用 hs_list (tools/call)
#   4. 调用 hs_kill_all (tools/call)
#
# 用法:
#   ./scripts/hs-mcp-demo.sh
#
# 依赖: bash 4+, curl, python3 (with http_server_cli installed)
# =============================================================================
set -euo pipefail

# ── 配置 ──────────────────────────────────────────────────────────────────────
MCP_PORT=8181
MCP_BASE="http://127.0.0.1:${MCP_PORT}"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── 颜色 ──────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# ── 辅助函数 ──────────────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()      { echo -e "${GREEN}[✓]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
error()   { echo -e "${RED}[✗]${NC} $*"; }
header()  {
    echo -e "\n${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}${BOLD}  $*${NC}"
    echo -e "${CYAN}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
}
json_pretty() {
    # Pretty-print JSON, fallback to raw output
    python3 -m json.tool 2>/dev/null || cat
}
show_curl() {
    # Print a curl command (colorized) before executing it
    local method="$1" url="$2" body="$3"
    echo -e "${MAGENTA}\$${NC} curl -s -X ${YELLOW}${method}${NC} \\"
    echo -e "     ${BLUE}${url}${NC} \\"
    echo -e "     -H 'Content-Type: application/json' \\"
    echo -e "     -d '${body}'"
    echo ""
}

# ── 打印横幅 ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}║              hs MCP 集成示例                                 ║${NC}"
echo -e "${CYAN}${BOLD}║              hs CLI MCP Integration Demo                     ║${NC}"
echo -e "${CYAN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 清理函数（trap 注册） ──────────────────────────────────────────────────────
cleanup() {
    local exit_code=$?
    echo ""
    if [ -n "${MCP_PID:-}" ]; then
        if kill -0 "${MCP_PID}" 2>/dev/null; then
            info "正在停止 hs mcp (PID: ${MCP_PID})..."
            kill "${MCP_PID}" 2>/dev/null || true
            wait "${MCP_PID}" 2>/dev/null || true
            ok "hs mcp 已停止"
        fi
    fi
    # 保险：确保端口释放
    local leftover
    leftover=$(lsof -ti:"${MCP_PORT}" 2>/dev/null || true)
    if [ -n "${leftover}" ]; then
        kill "${leftover}" 2>/dev/null || true
        info "已清理残留进程 (PID: ${leftover})"
    fi
    if [ "${exit_code}" -eq 0 ]; then
        echo ""
        ok "演示完成！"
    fi
}
trap cleanup EXIT INT TERM

# ═══════════════════════════════════════════════════════════════════════════════
# Step 1: 检查环境
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 1: 检查环境依赖"

# 检查 curl
if ! command -v curl &>/dev/null; then
    error "curl 未安装，请先安装 curl"
    exit 1
fi
ok "curl 可用"

# 检查 python3
if ! command -v python3 &>/dev/null; then
    error "python3 未安装，请先安装 Python 3"
    exit 1
fi
ok "python3 可用: $(python3 --version 2>&1)"

# 检查 hs CLI / http_server_cli 模块
HS_CMD=""
if command -v hs &>/dev/null; then
    HS_CMD="hs"
    ok "hs CLI 可用: $(hs _v 2>/dev/null || echo 'installed')"
elif python3 -c "from http_server_cli import __version__; print(__version__)" &>/dev/null; then
    HS_CMD="python3 -m http_server_cli"
    ver=$(python3 -c "from http_server_cli import __version__; print(__version__)" 2>/dev/null || echo "?")
    ok "http_server_cli 模块可用 (version ${ver})"
else
    error "hs CLI 未安装 / http_server_cli 模块未找到"
    echo ""
    echo "  请先安装:"
    echo "    pip install http-server-cli"
    echo "  或从项目目录运行:"
    echo "    pip install -e ."
    exit 1
fi
ok "Python 依赖就绪"

# ═══════════════════════════════════════════════════════════════════════════════
# Step 2: 启动 hs mcp (SSE 模式)
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 2: 启动 hs mcp（SSE 模式，端口 ${MCP_PORT}）"

# 先确保端口未被占用
existing_pid=$(lsof -ti:"${MCP_PORT}" 2>/dev/null || true)
if [ -n "${existing_pid}" ]; then
    warn "端口 ${MCP_PORT} 已被进程 PID:${existing_pid} 占用，正在释放..."
    kill "${existing_pid}" 2>/dev/null || true
    sleep 1
fi

# 用 Python 直接启动服务器（绕过 daemon 模式的子进程复杂性）
# 这样我们就能直接控制服务器进程的生命周期
info "正在启动 MCP Server..."
python3 <<PYEOF &
import sys, os

# 确保能找到项目 src
sys.path.insert(0, os.path.expanduser("${PROJECT_DIR}/src"))

from http_server_cli.mcp import _serve_sse
_serve_sse(port=${MCP_PORT})
PYEOF

MCP_PID=$!
sleep 1

# 验证服务器是否已启动
if kill -0 "${MCP_PID}" 2>/dev/null; then
    if lsof -ti:"${MCP_PORT}" 2>/dev/null | grep -q .; then
        ok "hs mcp 已启动 (PID: ${MCP_PID})"
        info "SSE endpoint: ${MCP_BASE}/sse"
        info "POST endpoint: ${MCP_BASE}/messages"
    else
        warn "进程已启动但端口还未就绪，正在等待..."
        sleep 2
        if lsof -ti:"${MCP_PORT}" 2>/dev/null | grep -q .; then
            ok "hs mcp 已启动 (PID: ${MCP_PID})"
        else
            # 可能是子进程方式，尝试从端口反向查找
            MCP_PID=$(lsof -ti:"${MCP_PORT}" 2>/dev/null || true)
            if [ -n "${MCP_PID}" ]; then
                ok "hs mcp 已启动 (PID: ${MCP_PID})"
            else
                error "MCP 服务器未能启动"
                exit 1
            fi
        fi
    fi
else
    error "MCP 服务器进程未能启动"
    exit 1
fi

echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Step 3: 初始化握手 (initialize)
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 3: 初始化握手 — POST ${MCP_BASE}/messages"

INIT_BODY='{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "clientInfo": {
            "name": "hs-mcp-demo",
            "version": "1.0.0"
        }
    }
}'

show_curl "POST" "${MCP_BASE}/messages" "${INIT_BODY}"

INIT_RESP=$(curl -s -X POST "${MCP_BASE}/messages" \
    -H "Content-Type: application/json" \
    -d "${INIT_BODY}")

# Validate response is non-empty
if [ -z "${INIT_RESP}" ]; then
    error "初始化请求未收到响应"
    exit 1
fi

echo "${INIT_RESP}" | json_pretty
echo ""

# 提取 server info 验证
SERVER_NAME=$(echo "${INIT_RESP}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
res = d.get('result', {})
print(res.get('serverInfo', {}).get('name', 'unknown'))
" 2>/dev/null || echo "unknown")

if [ "${SERVER_NAME}" = "hs-mcp" ]; then
    ok "MCP 握手成功 — 已连接到 \"${SERVER_NAME}\" 服务器"
else
    warn "服务器名称: ${SERVER_NAME}"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Step 4: 列出工具 (tools/list)
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 4: 列出工具 — POST ${MCP_BASE}/messages"

LIST_BODY='{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list"
}'

show_curl "POST" "${MCP_BASE}/messages" "${LIST_BODY}"

LIST_RESP=$(curl -s -X POST "${MCP_BASE}/messages" \
    -H "Content-Type: application/json" \
    -d "${LIST_BODY}")

if [ -z "${LIST_RESP}" ]; then
    error "tools/list 请求未收到响应"
    exit 1
fi

echo "${LIST_RESP}" | json_pretty
echo ""

# 统计工具数量
TOOL_COUNT=$(echo "${LIST_RESP}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
tools = d.get('result', {}).get('tools', [])
for t in tools:
    print(f\"  • {t['name']}: {t['description']}\")
print(f\"\\n共 {len(tools)} 个工具\")
" 2>/dev/null)

echo "${TOOL_COUNT}"
ok "工具列表获取成功"
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Step 5: 调用 hs_list (列出所有服务)
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 5: 调用工具 — hs_list"

CALL_LIST_BODY='{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "hs_list",
        "arguments": {}
    }
}'

show_curl "POST" "${MCP_BASE}/messages" "${CALL_LIST_BODY}"

LIST_RESULT=$(curl -s -X POST "${MCP_BASE}/messages" \
    -H "Content-Type: application/json" \
    -d "${CALL_LIST_BODY}")

if [ -z "${LIST_RESULT}" ]; then
    error "hs_list 调用未收到响应"
    exit 1
fi

echo "${LIST_RESULT}" | json_pretty
echo ""

# 检查是否返回了预期内容
IS_ERROR=$(echo "${LIST_RESULT}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('true' if d.get('error') or d.get('result', {}).get('isError') else 'false')
" 2>/dev/null || echo "true")

if [ "${IS_ERROR}" = "true" ]; then
    warn "hs_list 返回了错误（可能当前没有运行中的服务）"
else
    ok "hs_list 调用成功"
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════════
# Step 6: 调用 hs_kill_all (关闭所有服务)
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 6: 调用工具 — hs_kill_all"

CALL_KILLALL_BODY='{
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
        "name": "hs_kill_all",
        "arguments": {}
    }
}'

show_curl "POST" "${MCP_BASE}/messages" "${CALL_KILLALL_BODY}"

KILLALL_RESULT=$(curl -s -X POST "${MCP_BASE}/messages" \
    -H "Content-Type: application/json" \
    -d "${CALL_KILLALL_BODY}")

if [ -z "${KILLALL_RESULT}" ]; then
    error "hs_kill_all 调用未收到响应"
    exit 1
fi

echo "${KILLALL_RESULT}" | json_pretty
echo ""

# 验证
IS_KILL_ERROR=$(echo "${KILLALL_RESULT}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('true' if d.get('error') or d.get('result', {}).get('isError') else 'false')
" 2>/dev/null || echo "true")

if [ "${IS_KILL_ERROR}" = "true" ]; then
    warn "hs_kill_all 返回了错误"
else
    ok "hs_kill_all 调用成功"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Step 7: 清理
# ═══════════════════════════════════════════════════════════════════════════════
header "Step 7: 清理 — 停止 hs mcp"

# cleanup 函数会在 trap 中自动执行
# 但这里我们显式调用以确保输出顺序
kill -0 "${MCP_PID}" 2>/dev/null && {
    info "正在停止 hs mcp (PID: ${MCP_PID})..."
    kill "${MCP_PID}" 2>/dev/null || true
    wait "${MCP_PID}" 2>/dev/null || true
    ok "hs mcp 已停止"
} || {
    ok "hs mcp 进程已自动退出"
}

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║                  演示完成！                                    ║${NC}"
echo -e "${GREEN}${BOLD}║                  Demo Complete!                                ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  所有 MCP 协议步骤已成功演示:"
echo -e "  ${BOLD}1.${NC} 环境检查"
echo -e "  ${BOLD}2.${NC} 启动 MCP Server (SSE 模式, 端口 ${MCP_PORT})"
echo -e "  ${BOLD}3.${NC} 初始化握手 (POST /messages, method: initialize)"
echo -e "  ${BOLD}4.${NC} 列出工具 (POST /messages, method: tools/list)"
echo -e "  ${BOLD}5.${NC} 调用工具 hs_list (POST /messages, method: tools/call)"
echo -e "  ${BOLD}6.${NC} 调用工具 hs_kill_all (POST /messages, method: tools/call)"
echo -e "  ${BOLD}7.${NC} 清理 MCP Server"
echo ""
