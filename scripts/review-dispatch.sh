#!/bin/bash
# scripts/review-dispatch.sh — 审查/审计派发件模板（HTTP-SERVER-CL005 D4）
#
# 目的：由「编号 + 项目 + 步骤 + 日期」唯一推导 派发壳/日志/用量 三路径，并强制自校验：
#   ① 派发前：提示词文件必须存在且非空（≥1 字节）
#   ② 派发后：usage-file 必须存在且非空（杜绝 CL004 复审轮 1/2 的 usage 缺失）
#   ③ 生成的派发壳先过 `bash -n` 语法自检
#
# 用法：
#   scripts/review-dispatch.sh --target <repo> --code <编号> --project <项目> \
#       --step <步骤> --date <YYYYMMDD> --prompt <提示词文件> [--no-run] [--dry-run]
#
#   --step 取值示例：design / design-review / design-rereview / design-rereview2 /
#                    dev-impl / audit / ops-check / ops-verify
#   --dry-run 仅打印三路径（不落盘、不执行）；--no-run 落盘但不执行
#
# 生成的派发壳位置：<target>/cache/review-prep/dispatch-<project>-<code小写>-<step>-<date>.sh
# 日志：<target>/cache/closed-loop/<编号大写>-<step>-dispatch.log
# 用量：<target>/cache/closed-loop/<date>-<project>-<编号大写>-<step>.json

set -u

usage() {
  cat <<'USAGE'
用法: scripts/review-dispatch.sh --target <repo> --code <编号> --project <项目> \
        --step <步骤> --date <YYYYMMDD> --prompt <提示词文件> [--no-run] [--dry-run]

  --target   目标仓库绝对路径（必填）
  --code     闭环编号，如 HTTP-SERVER-CL005（必填；大小写不敏感，内部归一化为大写）
  --project  项目名，如 http-server.cli（必填）
  --step     步骤名，如 design-review / design-rereview2 / audit（必填）
  --date     日期 YYYYMMDD（必填）
  --prompt   审查提示词文件（必填；相对路径按 --target 解析，须存在且非空）
  --no-run   只生成派发壳，不执行
  --dry-run  只打印推导出的路径，不落盘、不执行
USAGE
}

TARGET="" ; CODE="" ; PROJECT="" ; STEP="" ; DATE="" ; PROMPT="" ; DRY=0 ; RUN=1
while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --code)   CODE="${2:-}";   shift 2 ;;
    --project) PROJECT="${2:-}"; shift 2 ;;
    --step)   STEP="${2:-}";   shift 2 ;;
    --date)   DATE="${2:-}";   shift 2 ;;
    --prompt) PROMPT="${2:-}"; shift 2 ;;
    --no-run) RUN=0; shift ;;
    --dry-run) DRY=1; RUN=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "❌ 未知参数: $1" >&2; usage >&2; exit 2 ;;
  esac
done

missing=""
[ -z "$TARGET" ]  && missing="$missing --target"
[ -z "$CODE" ]    && missing="$missing --code"
[ -z "$PROJECT" ] && missing="$missing --project"
[ -z "$STEP" ]    && missing="$missing --step"
[ -z "$DATE" ]    && missing="$missing --date"
[ -z "$PROMPT" ]  && missing="$missing --prompt"
if [ -n "$missing" ]; then
  echo "❌ 缺必填参数:$missing" >&2
  usage >&2
  exit 2
fi

[ -d "$TARGET" ] || { echo "❌ --target 不是目录: $TARGET" >&2; exit 2; }

# 编号归一化：大写（http-server-cl005 → HTTP-SERVER-CL005）/ 小写（用于壳文件名）
CODE_U=$(printf '%s' "$CODE" | tr '[:lower:]' '[:upper:]')
CODE_L=$(printf '%s' "$CODE" | tr '[:upper:]' '[:lower:]')

case "$PROMPT" in
  /*) PROMPT_ABS="$PROMPT" ;;
  *)  PROMPT_ABS="$TARGET/$PROMPT" ;;
esac

SHELL_FILE="$TARGET/cache/review-prep/dispatch-$PROJECT-$CODE_L-$STEP-$DATE.sh"
LOG="$TARGET/cache/closed-loop/$CODE_U-$STEP-dispatch.log"
USAGE="$TARGET/cache/closed-loop/$DATE-$PROJECT-$CODE_U-$STEP.json"

if [ "$DRY" = "1" ]; then
  echo "编号:   $CODE_U"
  echo "步骤:   $STEP"
  echo "派发壳: $SHELL_FILE"
  echo "日志:   $LOG"
  echo "提示词: $PROMPT_ABS"
  echo "用量:   $USAGE"
  exit 0
fi

# ① 派发前自校验：提示词必须存在且非空
if [ ! -s "$PROMPT_ABS" ]; then
  echo "❌ 提示词文件缺失或为空: $PROMPT_ABS" >&2
  exit 2
fi

mkdir -p "$TARGET/cache/review-prep" "$TARGET/cache/closed-loop" || exit 1

# 派发壳模板（逐字符固定；三路径由推导值填充）
cat > "$SHELL_FILE" <<EOF
#!/bin/bash
# $CODE_U 步骤 $STEP 派发器（由 scripts/review-dispatch.sh 生成，勿手改）
set -u
TARGET=$TARGET
cd "\$TARGET" || exit 1
LOG="$LOG"
PROMPT="$PROMPT_ABS"
USAGE="$USAGE"
: > "\$LOG"
echo "[\$(date '+%F %T')] $CODE_U $STEP 启动；等待 review 通道空闲" >> "\$LOG"
n=0
for i in \$(seq 1 360); do
  if ! pgrep -f "hermes -p review" >/dev/null 2>&1; then
    echo "[\$(date '+%F %T')] review 通道空闲（等待 \${n}s）→ 派发" >> "\$LOG"
    break
  fi
  sleep 15; n=\$((n + 15))
done
hermes -p review --in "\$TARGET" -z "\$(cat "\$PROMPT")" --usage-file "\$USAGE" >> "\$LOG" 2>&1
rc=\$?
echo "${CODE_U}_${STEP}_EXIT=\$rc" >> "\$LOG"
# ② 派发后自校验：usage-file 存在且非空
if [ ! -s "\$USAGE" ]; then
  echo "[\$(date '+%F %T')] ⚠️ usage-file 缺失或为空: \$USAGE" >> "\$LOG"
fi
echo "[\$(date '+%F %T')] 派发结束" >> "\$LOG"
exit \$rc
EOF
chmod +x "$SHELL_FILE"

# ③ 语法自检
if ! bash -n "$SHELL_FILE"; then
  echo "❌ 生成的派发壳语法错误: $SHELL_FILE" >&2
  exit 1
fi

echo "✅ 派发壳: $SHELL_FILE"
echo "   日志:   $LOG"
echo "   提示词: $PROMPT_ABS"
echo "   用量:   $USAGE"

[ "$RUN" = "1" ] || exit 0
echo "[$(date '+%F %T')] 执行派发壳…"
bash "$SHELL_FILE"
rc=$?
echo "[$(date '+%F %T')] 派发壳退出码=$rc"
if [ ! -s "$USAGE" ]; then
  echo "⚠️ usage-file 缺失或为空: $USAGE" >&2
fi
exit $rc
