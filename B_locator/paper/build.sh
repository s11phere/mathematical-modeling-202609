#!/usr/bin/env bash
# =====================================================================
# B 题论文一键编译（必须 XeLaTeX，连跑两遍以更新交叉引用）
#
#   bash build.sh         编译 + 缺字/报错自检
#   bash build.sh clean   只清理编译中间文件
#   bash build.sh help    查看用法
#
# Windows/MiKTeX 用户也可在编辑器里把编译器设为 XeLaTeX 后连编两遍
# （等价命令：xelatex -interaction=nonstopmode main.tex，跑两次）。
# =====================================================================
set -e
cd "$(dirname "$0")"

REQUIRED=(
  "main.tex"
  "cumcmthesis.cls"
  "fonts/simsun.ttc"
  "fonts/simkai.ttf"
  "figures/p1-algorithm-flow.png"
  "figures/p1-coverage-contrast.png"
)

clean() {
  rm -f ./*.aux ./*.log ./*.out ./*.toc ./*.fls ./*.fdb_latexmk ./*.synctex.gz
  echo "[OK] 已清理编译中间文件（main.pdf 保留）"
}

case "${1:-build}" in
  clean)
    clean
    exit 0
    ;;
  help|-h|--help)
    sed -n '2,11p' "$0"
    exit 0
    ;;
esac

# ---- 预检：缺什么就明确说缺什么，不要等到 TeX 报一堆看不懂的错 ----
missing=0
for f in "${REQUIRED[@]}"; do
  if [ ! -f "$f" ]; then
    echo "[!] 缺少必需文件：$f"
    missing=1
  fi
done

# ---- 预检：附录 B 粘贴的代码必须与 Q1/ 源文件逐字节一致 ----
# （改 Q1/p1_intersection.py 后请执行：cp ../Q1/p1_intersection.py code/p1_intersection.py）
if ! cmp -s code/p1_intersection.py ../Q1/p1_intersection.py; then
  echo "[!] 附录代码未同步：code/p1_intersection.py ≠ Q1/p1_intersection.py"
  echo "    请先执行：cp ../Q1/p1_intersection.py code/p1_intersection.py"
  missing=1
fi

if [ "$missing" -ne 0 ]; then
  echo "    请在 paper/ 目录下运行本脚本，且不要移动/改名 fonts/、figures/、sections/ 里的文件。"
  exit 1
fi

if ! command -v xelatex >/dev/null 2>&1; then
  echo "[!] 找不到 xelatex：本模板必须用 XeLaTeX 编译。"
  echo "    macOS：安装 MacTeX   https://tug.org/mactex/"
  echo "    Windows：安装 MiKTeX  https://miktex.org/download"
  echo "    安装后在本目录手动执行：xelatex -interaction=nonstopmode main.tex （连续两次）"
  exit 1
fi

# ---- 编译（两遍：第二遍更新交叉引用/页码/图号）----
echo "[1/2] XeLaTeX 第一遍 …"
xelatex -interaction=nonstopmode -halt-on-error main.tex
echo "[2/2] XeLaTeX 第二遍 …"
xelatex -interaction=nonstopmode -halt-on-error main.tex

# ---- 自检 ----
echo ""
echo "== 自检 =="
status=0
if grep -qi "Missing character" main.log; then
  echo "[!] 有缺字（会显示为方框），请按下表替换后重编译："
  grep -i "Missing character" main.log
  status=1
else
  echo "[OK] 无缺字"
fi
if grep -qE "^!" main.log; then
  echo "[!] 有编译错误，详见 main.log 中「!」开头的行"
  grep -nE "^!" main.log | head -10
  status=1
else
  echo "[OK] 无编译错误"
fi
echo "[OK] 产物：$(pwd)/main.pdf"
if [ "$status" -ne 0 ]; then
  echo "[!] 自检未全部通过，请先修正上面的问题。"
  exit 1
fi
