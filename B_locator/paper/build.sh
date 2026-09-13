#!/usr/bin/env bash
# 在本目录或任意目录执行 bash /path/to/paper/build.sh。
# 优先 XeLaTeX；未安装时使用 Tectonic。检查通过后才替换 main.pdf。
set -euo pipefail
cd "$(dirname "$0")"

case "${1:-build}" in
  clean)
    rm -f ./*.aux ./*.log ./*.out ./*.toc ./*.fls ./*.fdb_latexmk ./*.synctex.gz
    echo "已清理中间文件，main.pdf 保留。"
    exit 0 ;;
  help|-h|--help)
    sed -n '2,3p' "$0"
    exit 0 ;;
  build) ;;
  *) echo "用法：bash build.sh [build|clean|help]"; exit 2 ;;
esac

REQUIRED=(
  main.tex cumcmthesis.cls fonts/simsun.ttc fonts/simkai.ttf
  figures/multi_sensor_wedge_diagram.png figures/p1-algorithm-flow.png
  figures/p1-coverage-contrast.png figures/p2-contour60.png
  figures/p2-wedge-geometry.png figures/p2-mma-vs-pysim.png
  ../attachments/Q1/code/p1_intersection.py
  ../attachments/Q2/code/Q2_theory_corrected.wl
  ../attachments/Q3/code/p3_joint.py ../attachments/Q4/code/p4_compact.py
)
for source in "${REQUIRED[@]}"; do
  if [[ ! -f "$source" ]]; then
    echo "缺少文件：$source"; exit 1
  fi
done

BUILD_DIR=$(mktemp -d "${TMPDIR:-/tmp}/b-paper-build.XXXXXX")
BUILD_LOG="$BUILD_DIR/compile-output.txt"
if command -v xelatex >/dev/null 2>&1; then
  for pass in 1 2; do
    echo "XeLaTeX 第 $pass 遍……"
    if ! xelatex -interaction=nonstopmode -halt-on-error -output-directory="$BUILD_DIR" main.tex >> "$BUILD_LOG" 2>&1; then
      tail -60 "$BUILD_LOG"; exit 1
    fi
  done
else
  if command -v tectonic >/dev/null 2>&1; then
    ENGINE=$(command -v tectonic)
  elif [[ -x ../../tmp/tectonic/tectonic ]]; then
    ENGINE=../../tmp/tectonic/tectonic
  else
    echo "请安装 XeLaTeX 或 Tectonic 后再运行。"; exit 1
  fi
  if [[ -z "${TECTONIC_CACHE_DIR:-}" && -d ../../tmp/tectonic-cache ]]; then
    export TECTONIC_CACHE_DIR="$(cd ../../tmp/tectonic-cache && pwd)"
  fi
  echo "Tectonic 编译并更新交叉引用……"
  if ! "$ENGINE" -X compile main.tex --outdir "$BUILD_DIR" --reruns 2 --keep-logs > "$BUILD_LOG" 2>&1; then
    tail -60 "$BUILD_LOG"; exit 1
  fi
fi

if grep -qiE 'Missing character|^!|There were undefined references|multiply defined' "$BUILD_DIR/main.log"; then
  grep -niE 'Missing character|^!|undefined references|multiply defined' "$BUILD_DIR/main.log"
  echo "检查未通过；保留原 main.pdf。日志：$BUILD_DIR/main.log"
  exit 1
fi
if [[ ! -s "$BUILD_DIR/main.pdf" ]]; then
  echo "编译未生成有效 PDF。日志：$BUILD_LOG"; exit 1
fi
cp "$BUILD_DIR/main.pdf" main.pdf
echo "已生成 $(pwd)/main.pdf；无缺字、编译错误和失效引用。"
echo "编译日志：$BUILD_DIR/main.log"
