#!/bin/bash
# 后台启动 不打字（macOS）。在 Finder 里双击，或在终端运行 ./start_mac.command
# 日志在 budazi.log。第一次运行时 macOS 会请求麦克风、输入监控、辅助功能权限，见 README。
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "还没装依赖：请先在这个目录运行 uv sync"
  exit 1
fi
nohup .venv/bin/python -m budazi.app >/dev/null 2>&1 &
echo "不打字 已在后台启动（菜单栏右侧有麦克风图标）。这个窗口可以关掉。"
