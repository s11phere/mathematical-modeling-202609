#!/usr/bin/env bash
# =====================================================================
# 一键编译 B 题论文（必须 XeLaTeX，连跑两遍以更新交叉引用）
# 用法：bash build.sh
# =====================================================================
set -e
cd "$(dirname "$0")"

xelatex -interaction=nonstopmode -halt-on-error main.tex
xelatex -interaction=nonstopmode -halt-on-error main.tex

echo ""
echo "== 自检 =="
if grep -qi "Missing character" main.log; then
  echo "[!] 有缺字（会显示为方框），请定位并替换："
  grep -i "Missing character" main.log
else
  echo "[OK] 无缺字"
fi
if grep -qE "^!" main.log; then
  echo "[!] 有编译错误，见 main.log"
else
  echo "[OK] 无编译错误"
fi
