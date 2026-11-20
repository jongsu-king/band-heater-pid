#!/bin/zsh
# 두 번 누르면 기록 프로그램이 켜지고 브라우저에 화면이 뜬다. 끝낼 때는 이 창에서 Ctrl+C.
cd "$(dirname "$0")" || exit 1
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
exec "$UV" run -q heater_log.py "$@"
