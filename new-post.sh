#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
python3 tools/blog.py new "$@"
status=$?
echo
read -r -p "按回车关闭..." _ || true
exit "$status"
