#!/bin/bash
# release-local.sh — 本地安装脚本
# 用法: bash release-local.sh [选项]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="${SCRIPT_DIR}/src/http_server_cli/__init__.py"

get_current_version() {
    grep "__version__" "$VERSION_FILE" | sed -E "s/.*__version__ *= *['\"]([^'\"]+)['\"].*/\1/"
}

get_pypi_version() {
    pip index versions http-server-cli -i https://pypi.org/simple/ 2>/dev/null \
        | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布"
}

get_testpypi_version() {
    pip index versions http-server-cli -i https://test.pypi.org/simple/ 2>/dev/null \
        | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布"
}

case "${1:-}" in
    --editable)
        echo "📦 可编辑模式安装..."
        pip install -e "$SCRIPT_DIR"
        echo "✅ 安装完成: http-server-cli $(get_current_version)"
        ;;
    --versions)
        echo "📋 版本信息"
        echo "  当前版本:     $(get_current_version)"
        echo "  生产环境版本: $(get_pypi_version)"
        echo "  开发环境版本: $(get_testpypi_version)"
        ;;
    --help|-h|"")
        echo "release-local.sh — 本地安装脚本"
        echo ""
        echo "用法:  bash release-local.sh [选项]"
        echo ""
        echo "选项:"
        echo "  --editable     以可编辑模式安装（pip install -e .）"
        echo "  --versions     打印版本信息"
        echo "  --help, -h     显示此帮助"
        ;;
    *)
        echo "❌ 未知选项: $1"
        echo "用法: bash release-local.sh --help"
        exit 1
        ;;
esac
