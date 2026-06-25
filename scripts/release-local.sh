#!/bin/bash
# http-server-cli 本地开发安装脚本
# 用法: bash scripts/release-local.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
VERSION_FILE="${PROJECT_DIR}/src/http_server_cli/__init__.py"
PYPROJECT_FILE="${PROJECT_DIR}/pyproject.toml"

VERBOSE=0
DRY_RUN=0
SKIP_BUILD=0
EDITABLE=1
CLEAR_CACHE=0
SHOW_HELP=0
SHOW_VERSIONS=0
HAS_ARGS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --editable)
            EDITABLE=1
            HAS_ARGS=1
            shift
            ;;
        --versions)
            SHOW_VERSIONS=1
            HAS_ARGS=1
            shift
            ;;
        -n|--dry-run)
            DRY_RUN=1
            HAS_ARGS=1
            shift
            ;;
        --skip-build)
            SKIP_BUILD=1
            HAS_ARGS=1
            shift
            ;;
        --no-editable)
            EDITABLE=0
            HAS_ARGS=1
            shift
            ;;
        -c|--clear-cache)
            CLEAR_CACHE=1
            HAS_ARGS=1
            shift
            ;;
        -v|--verbose)
            VERBOSE=1
            HAS_ARGS=1
            shift
            ;;
        -h|--help)
            SHOW_HELP=1
            HAS_ARGS=1
            shift
            ;;
        *)
            HAS_ARGS=1
            shift
            ;;
    esac
done

# 无参数时显示帮助
if [[ $HAS_ARGS -eq 0 ]]; then
    SHOW_HELP=1
fi

# --versions 优先处理
if [[ $SHOW_VERSIONS -eq 1 ]]; then
    CURRENT_VER=$(grep "__version__" "$VERSION_FILE" | sed -E "s/.*__version__ *= *['\"]([^'\"]+)['\"].*/\1/")
    echo "📋 版本信息"
    echo "  当前版本: $CURRENT_VER"
    # 查询生产环境版本
    PYPI_VER=$(pip index versions http-server-cli -i https://pypi.org/simple/ 2>/dev/null | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布")
    echo "  生产环境版本: $PYPI_VER"
    # 查询开发环境版本
    TEST_VER=$(pip index versions http-server-cli -i https://test.pypi.org/simple/ 2>/dev/null | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布")
    echo "  开发环境版本: $TEST_VER"
    exit 0
fi

# --help 优先于其他操作
if [[ $SHOW_HELP -eq 1 ]]; then
    echo "Usage: bash scripts/release-local.sh [options]"
    echo ""
    echo "本地开发安装脚本 — 构建并安装到当前 Python 环境"
    echo ""
    echo "Options:"
    echo "  --editable        以可编辑模式安装（默认）"
    echo "  --versions        打印版本信息"
    echo "  -n, --dry-run     仅构建，不安装"
    echo "  --skip-build      跳过构建（使用已有 dist/）"
    echo "  --no-editable     以非可编辑模式安装"
    echo "  -c, --clear-cache  清理 Python 缓存文件"
    echo "  -v, --verbose     显示详细输出"
    echo "  -h, --help        显示帮助"
    exit 0
fi

if [[ $VERBOSE -eq 0 ]]; then
    QUIET_FLAG="-q"
else
    QUIET_FLAG=""
fi

EMOJI_OK="✅"
EMOJI_ERROR="❌"
EMOJI_BUILD="🔨"
EMOJI_INSTALL="📦"

cd "${PROJECT_DIR}"

EDITABLE_LABEL="可编辑模式"
INSTALL_FLAG="-e"
if [[ $EDITABLE -eq 0 ]]; then
    EDITABLE_LABEL="非可编辑模式"
    INSTALL_FLAG=""
fi

echo "========================================"
echo "  http-server-cli 开发环境配置"
echo "========================================"
echo "  模式: $([ $VERBOSE -eq 1 ] && echo 'verbose' || echo 'quiet')"
echo "  安装: ${EDITABLE_LABEL}"
echo "========================================"
echo ""

# ── 步骤 1: 清理旧构建 ────────────────────────────────
if [[ $SKIP_BUILD -eq 0 ]]; then
    echo "[1/3] ${EMOJI_BUILD} 清理旧构建产物..."
    if rm -rf dist/ build/ *.egg-info/ 2>/dev/null; then
        echo "      ${EMOJI_OK} 清理完成"
    else
        echo "      ⚠️ 无旧构建产物，跳过"
    fi
    echo ""
fi

# ── 清理缓存 ──────────────────────────────────────────
if [[ $CLEAR_CACHE -eq 1 ]]; then
    echo "[2/3] 🧹 清理 Python 缓存..."
    find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name '*.pyc' -delete 2>/dev/null || true
    rm -rf src/http_server_cli.egg-info/ .pytest_cache/ .mypy_cache/ .pytest_mypy_cache/ htmlcov/ .coverage* 2>/dev/null || true
    echo "      ${EMOJI_OK} 缓存清理完成"
    echo ""
    exit 1
fi

# ── 步骤 2: 构建 ────────────────────────────────────
if [[ $SKIP_BUILD -eq 0 ]]; then
    echo "[2/3] ${EMOJI_BUILD} 构建源码包和 wheel..."
    if python3 -m build $QUIET_FLAG; then
        echo "      ${EMOJI_OK} 构建成功"
        echo "         产物目录: dist/"
    else
        echo "      ${EMOJI_ERROR} 构建失败，请检查依赖是否安装"
        echo "         建议: pip install build"
        exit 1
    fi
    echo ""
else
    if [[ ! -d dist ]] || [[ -z "$(ls -A dist/ 2>/dev/null)" ]]; then
        echo "      ${EMOJI_ERROR} dist/ 目录不存在或为空，无法跳过构建"
        echo "         请先运行: bash scripts/release-local.sh"
        exit 1
    fi
fi

# dry-run 模式在此退出
if [[ $DRY_RUN -eq 1 ]]; then
    echo "========================================"
    echo "  dry-run 模式，跳过安装"
    echo "========================================"
    exit 0
fi

# ── 步骤 3: 安装 ─────────────────────────────────────
if [[ $SKIP_BUILD -eq 0 ]]; then
    STEP_LABEL="3/3"
else
    STEP_LABEL="1/1"
fi
echo "[${STEP_LABEL}] ${EMOJI_INSTALL} 安装到开发环境 (${EDITABLE_LABEL})..."
if pip install $QUIET_FLAG $INSTALL_FLAG .; then
    echo "      ${EMOJI_OK} 安装成功"
    echo ""
    echo "========================================"
    echo "  开发环境配置完成！"
    echo "========================================"
    echo "  可用命令:"
    echo "    hs version    # 查看版本"
    echo "    hs start . -o # 启动服务并打开浏览器"
    echo "    hs list       # 查看运行中的服务"
    echo "========================================"
else
    echo "      ${EMOJI_ERROR} 安装失败"
    exit 1
fi
