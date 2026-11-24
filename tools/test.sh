#!/usr/bin/env bash
# 一键测试：刷新 class_name 缓存 → 跑全部测试 →（存在时）资源校验。
# 用法: tools/test.sh [关键字过滤]
set -uo pipefail
cd "$(dirname "$0")/.."
G="${GODOT:-/Applications/Godot.app/Contents/MacOS/Godot}"

"$G" --headless --path . --import >/dev/null 2>&1

filter_args=()
if [ $# -gt 0 ]; then filter_args=(-- "--filter=$1"); fi
out=$("$G" --headless --path . --script res://tools/run_tests.gd ${filter_args[@]+"${filter_args[@]}"} 2>&1)
code=$?
echo "$out" | grep -E "^(PASS|FAIL|RESULT|     - )|SCRIPT ERROR|Parse Error"
if [ $code -ne 0 ]; then echo "测试失败"; exit 1; fi

if [ -f tools/validate_assets.gd ] && [ $# -eq 0 ]; then
  vout=$("$G" --headless --path . --script res://tools/validate_assets.gd 2>&1)
  vcode=$?
  echo "$vout" | grep -E "^(OK|ERR|RESULT)|SCRIPT ERROR"
  if [ $vcode -ne 0 ]; then echo "资源校验失败"; exit 1; fi
fi
echo "全部通过"
