#!/bin/sh
# 수동 리셋 업로드: 자동 리셋이 안 될 때 보드의 RESET 버튼으로 부트로더를 직접 깨워서 올린다.
# 사용법: 이 스크립트를 실행하고 ">>> 지금 RESET" 문구가 뜰 때마다 보드의 RESET 버튼을 눌렀다 뗀다.

AD=$(ls -d "$HOME"/Library/Arduino15/packages/arduino/tools/avrdude/*/ | tail -1)
HEX="$(dirname "$0")/build/band_heater_pid.hex"
PORT=$(ls /dev/cu.usbserial-* 2>/dev/null | head -1)

if [ -z "$PORT" ]; then
  echo "보드가 안 보여요. USB 케이블을 다시 꽂아주세요."
  exit 1
fi
echo "포트: $PORT"

for i in 1 2 3; do
  for BAUD in 57600 115200; do
    echo ""
    echo ">>> 시도 $i ($BAUD baud): 지금 보드의 RESET 버튼을 눌렀다 떼세요"
    if "${AD}bin/avrdude" -C "${AD}etc/avrdude.conf" -p m328p -c arduino -P "$PORT" -b "$BAUD" \
         -x attempts=15 -D -U "flash:w:$HEX:i"; then
      echo ""
      echo "=== 업로드 성공 ($BAUD baud) ==="
      exit 0
    fi
  done
done

echo ""
echo "=== 6번 모두 실패: 부트로더가 없거나 보드 쪽 문제일 가능성이 커요 ==="
exit 1
