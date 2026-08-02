#!/bin/zsh

SCRIPT_DIR=${0:A:h}
cd "$SCRIPT_DIR" || exit 1
export PYTHONPATH="$SCRIPT_DIR/src"

echo "正在启动 AIP 非对称博弈实验室……"
echo "请保持这个窗口开启；关闭窗口会结束本地游戏。"
echo

python3 -m aip play
exit_code=$?

if (( exit_code != 0 )); then
  echo
  echo "启动失败。请将上面的错误信息发给 Codex。"
  echo "按回车键关闭窗口。"
  read
fi
