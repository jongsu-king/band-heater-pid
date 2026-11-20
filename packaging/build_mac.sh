#!/bin/zsh
# 맥용 응용프로그램을 만든다. 결과: dist/밴드히터 기록.app
# 세션 폴더(프로젝트 폴더)에서 실행: packaging/build_mac.sh
set -e
cd "$(dirname "$0")/.."
UV="$(command -v uv || echo /opt/homebrew/bin/uv)"
# 연습 모드용 가상 보드를 최신 펌웨어로 다시 컴파일
c++ -std=c++17 -w -x c++ -I tools/sim/mock -I band_heater_pid tools/sim/sim.cpp -o tools/sim/sim_bin
WORK=$(mktemp -d)
"$UV" run -q --with pyinstaller --with "pywebview>=5" --with "pyserial>=3.5" \
  pyinstaller --noconfirm --clean --workpath "$WORK" --distpath dist packaging/heater_app.spec
rm -rf "$WORK" dist/HeaterLog
echo "만듦: dist/밴드히터 기록.app"
