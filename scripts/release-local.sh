
VERBOSE=0
QUIET_FLAG="-q"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -v|--verbose)
            VERBOSE=1
            QUIET_FLAG=""
            shift
            ;;
        *)
            shift
            ;;
    esac
done

echo "========================================"
echo "  http-server-cli 开发环境配置"
echo "========================================"
echo "  模式: $(if [ $VERBOSE -eq 1 ]; then echo "verbose"; else echo "quiet"; fi)"
echo "========================================"

# 1. 清理旧构建
echo ""
echo "[1/3] 清理旧构建产物..."
if rm -rf dist/ build/ *.egg-info/ 2>/dev/null; then
    echo "      ✅ 清理完成"
else
    echo "      ⚠️ 无旧构建产物，跳过"
fi

# 2. 构建 source distribution + wheel
echo ""
echo "[2/3] 构建源码包和 wheel..."
if python3 -m build $QUIET_FLAG; then
    echo "      ✅ 构建成功"
    echo "         产物目录: dist/"
    # ls -la dist/ 2>/dev/null || true
else
    echo "      ❌ 构建失败，请检查依赖是否安装"
    echo "         建议: pip install build twine"
    exit 1
fi

# 3. 可编辑模式安装
echo ""
echo "[3/3] 安装到开发环境 (-e 可编辑模式)..."
if pip install $QUIET_FLAG -e .; then
    echo "      ✅ 安装成功"
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
    echo "      ❌ 安装失败"
    exit 1
fi