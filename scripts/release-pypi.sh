#!/bin/bash
# scripts/release-pypi.sh — PyPI 发布脚本
# 用法: bash scripts/release-pypi.sh [选项]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION_FILE="${PROJECT_DIR}/src/http_server_cli/__init__.py"

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
    --production|-p)
        VERSION=$(get_current_version)
        echo "📦 构建 http-server-cli v${VERSION}..."
        cd "$PROJECT_DIR"
        rm -rf dist/ build/
        python3 -m build
        echo "✅ 构建完成"
        echo ""
        echo "🚀 发布到 PyPI..."
        python3 -m twine upload dist/*
        echo "✅ 发布完成: http-server-cli v${VERSION}"
        ;;
    --versions)
        echo "📋 版本信息"
        echo "  当前版本:     $(get_current_version)"
        echo "  生产环境版本: $(get_pypi_version)"
        echo "  开发环境版本: $(get_testpypi_version)"
        ;;
    --help|-h|"")
        echo "scripts/release-pypi.sh — PyPI 发布脚本"
        echo ""
        echo "用法:  bash scripts/release-pypi.sh [选项]"
        echo ""
        echo "选项:"
        echo "  --production, -p   构建并发布到 PyPI"
        echo "  --versions         打印版本信息"
        echo "  --help, -h         显示此帮助"
        ;;
    *)
        echo "❌ 未知选项: $1"
        echo "用法: bash scripts/release-pypi.sh --help"
        exit 1
        ;;
esac
