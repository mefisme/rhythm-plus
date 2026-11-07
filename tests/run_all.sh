#!/bin/bash
# Runs the emulator tests on one build:  bash tests/run_all.sh a0085
# Needs: PYTHON with unicorn and capstone (default: python), DSPTOOL = the DSP56300 assembler (dsptool),
# remix/stock/: the official firmware image and a RAM dump (see the README).
set -u
b=${1:?build folder, for example a0085}; B=${b^^}
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
export RH_PROBES=0
STOCK=remix/stock/circuitrhythm-firmware-5706-STOCK.bin
RAM=remix/stock/rhythm-ram-frd1-synced.bin
LOG=buildtmp/$b-memaudit.txt; mkdir -p buildtmp; rm -f "$LOG"
fail=0
run() { r=$("$@" 2>&1 | tail -1); echo "$r" | grep -q "ALL PASS" || fail=1; echo "$r"; }
for t in smpads tmenu pageclear trackreset clearbrightness clkci countin diagread resetcontrols srcount stepmarker steppage trackpulse playfix_ours $( [ -n "$(grep -o "\"upguard\"" firmware/$b/manifest.json)" ] && echo upguard ) $( grep -q "\"mutset\"" firmware/$b/manifest.json && echo mutset ); do
  echo -n "$t: "; RH_BUILD=$b RH_MEMAUDIT=$LOG run "$PY" tests/emu_$t.py $STOCK firmware/$b/rhythmplus-$B.bin $RAM
done
echo -n "ramaudit: "; run "$PY" tests/emu_ramaudit.py $b $LOG
for t in dspboot pshape fshape mixmove dspmap $( grep -q "\"loopfade\"" firmware/$b/manifest.json && echo loopfade ) $( grep -q "\"declick\"" firmware/$b/manifest.json && echo declick ) $( grep -q "\"drone\"" firmware/$b/manifest.json && echo drone ) $( grep -q "\"c0fx\"" firmware/$b/manifest.json && echo c0fx ) $( grep -q "\"xf_words\"" firmware/$b/manifest.json && echo loopxf ) $( grep -q "\"pvloop\"" firmware/$b/manifest.json && echo preview ); do echo -n "$t: "; run "$PY" tests/emu_$t.py $b; done
[ $fail = 0 ] && echo "ALL SUITES PASS" || { echo "SOME SUITES FAILED"; exit 1; }
