#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyserial>=3.5", "pywebview>=5"]
# ///
"""밴드 히터 기록 프로그램을 전용 창으로 띄운다. 응용프로그램(.app, .exe)은 이 파일을 묶은 것이다.

    uv run heater_app.py            전용 창으로 실행
    packaging/build_mac.sh          맥용 응용프로그램 만들기 (dist/ 에 생김)
    build_windows.bat               윈도우용 exe 만들기 (윈도우 PC에서 실행)
"""
import heater_log

if __name__ == '__main__':
    heater_log.main(window=True)
