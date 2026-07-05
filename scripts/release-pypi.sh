#!/bin/bash
# http-server-cli 发布脚本 — 发布到 TestPyPI/PyPI
# 用法: bash scripts/release-pypi.sh [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 解析参数
VERBOSE=0
DRY_RUN=0
SKIP_BUILD=0
TARGET=""
SHOW_VERSIONS=0
SHOW_HELP=0
HAS_ARGS=0
VERSION_FILE="${PROJECT_DIR}/src/http_server_cli/__init__.py"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --production|-p)
            TARGET="pypi"
            HAS_ARGS=1
            shift
            ;;
        --versions)
            SHOW_VERSIONS=1
            HAS_ARGS=1
            shift
            ;;
        -t|--test)
            TARGET="testpypi"
            HAS_ARGS=1
            shift
            ;;
        -v|--verbose)
            VERBOSE=1
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
        -h|--help|*)
            SHOW_HELP=1
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
    CURRENT_VER=$(grep "__version__" "$VERSION_FILE" | sed -E "s/.*__version__ *= *['\"]([^'\"]+)['\"].*/\\1/")
    # 检测 editable 模式
    if pip show http-server-cli 2>/dev/null | grep -q "Editable project location"; then
        EDITABLE_STATUS="editable"
    else
        EDITABLE_STATUS="no-editable"
    fi
    echo "📋 版本信息"
    echo "  当前版本: $CURRENT_VER ($EDITABLE_STATUS)"
    PYPI_VER=$(pip index versions http-server-cli -i https://pypi.org/simple/ 2>/dev/null | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布")
    echo "  生产环境版本: $PYPI_VER"
    TEST_VER=$(pip index versions http-server-cli -i https://test.pypi.org/simple/ 2>/dev/null | head -1 | sed -E 's/.*\(([0-9.]+)\).*/\1/' || echo "未发布")
    echo "  开发环境版本: $TEST_VER"
    exit 0
fi

# --help 或 --production 未指定时显示帮助
if [[ $SHOW_HELP -eq 1 ]] || [[ -z "$TARGET" ]]; then
    if [[ -z "$TARGET" ]] && [[ $SHOW_HELP -eq 0 ]] && [[ $HAS_ARGS -gt 0 ]]; then
        # 有参数但既不是 --production 也不是 --versions/--help
        :
    fi
    echo "用法: bash scripts/release-pypi.sh [options]"
    echo ""
    echo "Options:"
    echo "  --versions         打印版本信息"
    echo "  -t, --test         发布到 TestPyPI"
    echo "  -p, --production   构建并发布到 PyPI"
    echo "  -n, --dry-run      仅构建，不上传"
    echo "  --skip-build       跳过构建步骤（使用已有 dist/）"
    echo "  -v, --verbose      显示详细输出"
    echo "  -h, --help         显示帮助"
    exit 0
fi

if [[ $VERBOSE -eq 0 ]]; then
    QUIET_FLAG="-q"
else
    QUIET_FLAG=""
fi

# Emoji
EMOJI_STEP="📦"
EMOJI_OK="✅"
EMOJI_ERROR="❌"
EMOJI_BUILD="🔨"
EMOJI_UPLOAD="🚀"
EMOJI_VERIFY="🔍"

cd "${PROJECT_DIR}"

REPOSITORY_NAME="$TARGET"
REPOSITORY_LABEL="$([ "$TARGET" = "testpypi" ] && echo 'TestPyPI' || echo 'PyPI')"

echo "========================================"
echo "  http-server-cli ${REPOSITORY_LABEL} 发布"
echo "========================================"
echo "  目标: ${REPOSITORY_LABEL}"
echo "  模式: $([ $DRY_RUN -eq 1 ] && echo 'dry-run' || echo '正式发布')"
echo "========================================"
echo ""

# ── 步骤 1: 清理旧构建 ────────────────────────────────
echo "[1/4] ${EMOJI_BUILD} 清理旧构建产物..."
rm -rf dist/ build/ *.egg-info/ src/*.egg-info/
echo "      ${EMOJI_OK} 清理完成"
echo ""

# ── 步骤 2: 构建 ────────────────────────────────────
echo "[2/4] ${EMOJI_BUILD} 构建源码包和 wheel..."
python3 -m build ${QUIET_FLAG}

# 显示构建产物
echo "      ${EMOJI_OK} 构建成功"
echo "      产物目录: dist/"
echo "      ---"
ls -lh dist/ 2>/dev/null || echo "      (dist/ 目录为空)"
echo "      ---"
echo ""

# 检查构建产物
shopt -s nullglob
whl_files=(dist/*.whl)
tar_files=(dist/*.tar.gz)
shopt -u nullglob

if [[ ${#whl_files[@]} -eq 0 ]] && [[ ${#tar_files[@]} -eq 0 ]]; then
    echo "      ${EMOJI_ERROR} 构建失败：dist/ 目录为空"
    exit 1
fi

# dry-run 模式在此退出
if [[ $DRY_RUN -eq 1 ]]; then
    echo "========================================"
    echo "  dry-run 模式，跳过上传"
    echo "========================================"
    exit 0
fi

# ── 步骤 3: 验证构建产物 ─────────────────────────────
echo "[3/4] ${EMOJI_VERIFY} 验证构建产物..."
python3 -m twine check dist/*
echo "      ${EMOJI_OK} 验证通过"
echo ""

# ── 从 ~/.pypirc 读取密码 ────────────────────────────
get_password() {
    local section="$1"
    awk -v s="[$section]" '
    $0 == s {found=1; next}
    /^\[/{found=0}
    found && /password[[:space:]]*[=:]/{
        sub(/^[[:space:]]*password[[:space:]]*[=:][[:space:]]*/, "");
        print; exit
    }
    ' ~/.pypirc
}

PASSWORD="$(get_password "$REPOSITORY_NAME")"

if [[ -z "$PASSWORD" ]]; then
    echo "      ${EMOJI_ERROR} 未在 ~/.pypirc 中找到 [$REPOSITORY_NAME] 的 password"
    echo "      请确保 ~/.pypirc 包含以下内容："
    echo "        [$REPOSITORY_NAME]"
    echo "        username = __token__"
    echo "        password = 你的-token"
    exit 1
fi

# ── 步骤 4: 上传 ─────────────────────────────────────
echo "[4/4] ${EMOJI_UPLOAD} 上传到 ${REPOSITORY_LABEL}..."
echo ""

UPLOAD_OUTPUT=$(TWINE_PASSWORD="$PASSWORD" python3 -m twine upload --verbose --repository "$REPOSITORY_NAME" dist/* 2>&1) && UPLOAD_OK=true || UPLOAD_OK=false

if [ "$UPLOAD_OK" = true ]; then
    echo "      ${EMOJI_OK} 上传成功"
    echo ""

    echo "========================================"
    echo "  发布成功！"
    echo "========================================"
    echo ""

    if [ "$TARGET" = "testpypi" ]; then
        echo "  验证安装:"
        echo "    pip install http-server-cli --index-url https://test.pypi.org/simple/"
        echo ""
        echo "  或升级:"
        echo "    pip install --upgrade http-server-cli --index-url https://test.pypi.org/simple/"
    else
        echo "  验证安装:"
        echo "    pip install http-server-cli --index-url https://pypi.org/simple/"
        echo ""
        echo "  或升级:"
        echo "    pip install --upgrade http-server-cli --index-url https://pypi.org/simple/"
    fi

    echo "  验证版本:"
    echo "    hs version"
    echo ""
else
    echo ""
    echo "      ${EMOJI_ERROR} 上传失败"
    echo ""
    echo "      ── 错误诊断 ──"
    echo ""

    # ── 常见错误匹配 ──
    if echo "$UPLOAD_OUTPUT" | grep -qi "File already exists"; then
        echo "      原因: 当前版本 ($(python3 -c "from http_server_cli import __version__; print(__version__)")) 已发布到 $REPOSITORY_LABEL"
        echo "      修复:"
        echo "        1. 在 src/http_server_cli/__init__.py 中升级版本号"
        echo "        2. 重新运行本脚本"
        echo ""
        echo "      或删除已有版本:"
        echo "        https://$REPOSITORY_NAME.pypi.org/manage/project/http-server-cli/releases/"
    elif echo "$UPLOAD_OUTPUT" | grep -qi "401\|403\|Authentication\|invalid.*token\|not.*authorized"; then
        echo "      原因: ~/.pypirc 中的 token 无效或已过期"
        echo "      修复:"
        echo "        1. 登录 https://$REPOSITORY_NAME.pypi.org/manage/account/token/"
        echo "        2. 生成新 API token"
        echo "        3. 更新 ~/.pypirc 中的 password"
    elif echo "$UPLOAD_OUTPUT" | grep -qi "410\|Gone\|removed\|deprecated"; then
        echo "      原因: 仓库地址已变更或废弃"
        echo "      修复:"
        echo "        1. 检查 PyPI 官方公告"
        echo "        2. 更新脚本中的仓库 URL"
    elif echo "$UPLOAD_OUTPUT" | grep -qi "refused\|timeout\|connect\|network\|reset"; then
        echo "      原因: 网络连接失败"
        echo "      修复:"
        echo "        1. 检查网络连接"
        echo "        2. 确认可访问 pypi.org"
        echo "        3. 重试"
    elif echo "$UPLOAD_OUTPUT" | grep -qi "400\|Bad Request"; then
        echo "      原因: 请求被服务器拒绝，包元数据可能有问题"
        echo "      修复:"
        echo "        1. 运行 python3 -m twine check dist/* 查看具体问题"
        echo "        2. 检查 pyproject.toml 配置"
    else
        echo "      未知错误，请查看上方详细输出"
    fi

    echo ""
    echo "      ── 完整错误输出 ──"
    echo "$UPLOAD_OUTPUT"
    echo ""
    exit 1
fi
