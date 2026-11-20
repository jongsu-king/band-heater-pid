#!/bin/zsh
# 보드 없이 가상 보드(30배속)로 연습한다. 실제 히터는 켜지지 않는다. 기록은 연습용 폴더에 따로 남는다.
cd "$(dirname "$0")" || exit 1
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
exec "$UV" run -q heater_log.py --sim 30 --out "$HOME/Documents/밴드히터_기록/연습" "$@"
