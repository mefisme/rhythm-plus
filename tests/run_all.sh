#!/bin/bash
# Runs the emulator tests on one build:  bash tests/run_all.sh a0085
# Needs: PYTHON with unicorn and capstone (default: python), DSPTOOL = the DSP56300 assembler (dsptool),
# remix/stock/: the official firmware image and a RAM dump (see the README).
set -u
b=${1:?build folder, for example a0085}; B=${b^^}
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
export RH_PROBES=0
export RH_AUTOPROT=$(grep -q '"autoprot"' firmware/$b/manifest.json && echo 1 || echo 0)
export RH_AUTOBANK=$(grep -q '"autobank"' firmware/$b/manifest.json && echo 1 || echo 0)
export RH_STEPMUT=$(grep -q '"stepmut"' firmware/$b/manifest.json && echo 1 || echo 0)
export RH_GFXMIX=$(grep -q '"gfxmix"' firmware/$b/manifest.json && echo 1 || echo 0)
export RH_GRANULAR=$(grep -q '"integration_version": 1' firmware/$b/manifest.json && echo 1 || echo 0)
export RH_FILETOOLS=$(grep -q '"filetools"' firmware/$b/manifest.json && echo 1 || echo 0)
STOCK=remix/stock/circuitrhythm-firmware-5706-STOCK.bin
RAM=remix/stock/rhythm-ram-frd1-synced.bin
LOG=buildtmp/$b-memaudit.txt; mkdir -p buildtmp; rm -f "$LOG"
fail=0
run() { r=$("$@" 2>&1 | tail -1); echo "$r" | grep -q "ALL PASS" || fail=1; echo "$r"; }
for t in smpads tmenu pageclear trackreset clearbrightness clkci countin diagread resetcontrols srcount stepmarker steppage trackpulse playfix_ours $( [ -n "$(grep -o "\"upguard\"" firmware/$b/manifest.json)" ] && echo upguard ) $( grep -q "\"mutset\"" firmware/$b/manifest.json && echo mutset ) $( grep -q "\"stepmut\"" firmware/$b/manifest.json && echo stepmut ) $( grep -q '"quantize"' firmware/$b/manifest.json && echo quantize ) $( grep -q "\"gfxmix\"" firmware/$b/manifest.json && echo gfxmix ) $( grep -q '"stretch": {' firmware/$b/manifest.json && echo stretch_arm ) $( grep -q '"filetools"' firmware/$b/manifest.json && echo filetools ) $( grep -q '"noeasystart"' firmware/$b/manifest.json && echo noeasystart ); do
  echo -n "$t: "; RH_BUILD=$b RH_MEMAUDIT=$LOG run "$PY" tests/emu_$t.py $STOCK firmware/$b/rhythmplus-$B.bin $RAM
done
echo -n "ramaudit: "; run "$PY" tests/emu_ramaudit.py $b $LOG
for t in dspboot $( grep -q "\"midimerge\"" firmware/$b/manifest.json && echo midimerge ) $( grep -q '"dsppack"' firmware/$b/manifest.json && echo dsppack ) $( grep -q "\"gfxsplit\"" firmware/$b/manifest.json && echo gfxsplit ) mixmove dspmap $( grep -q "\"loopfade\"" firmware/$b/manifest.json && echo loopfade ) $( grep -q "\"drone\"" firmware/$b/manifest.json && echo drone ) $( grep -q "\"xf_words\"" firmware/$b/manifest.json && echo loopxf ) $( grep -q "\"pvloop\"" firmware/$b/manifest.json && echo preview ) $( grep -q '"stretch": {' firmware/$b/manifest.json && echo stretch_entry stretch_route stretch_load ) $( grep -q '"scan_home"' firmware/$b/manifest.json && echo granular_scanhome ) $( grep -q '"mode_fade"' firmware/$b/manifest.json && echo granular_modefade ) $( grep -q '"scan_centre"' firmware/$b/manifest.json && echo granular_oneshot_home ); do echo -n "$t: "; run "$PY" tests/emu_$t.py $b; done
# Connected-Granular builds: the editor, Granular and storage tests, 8 at a time, judged by exit code.
M=firmware/$b/manifest.json
if grep -q '"arm_kernel"' $M; then
  has() { grep -q "\"$1\"" $M; }
  list="stackdepth automation3 automation3_storage automation_bank automation_bank7 automation_capture automation_codec7 automation_core
    automation_cow7 automation_edit automation_file automation_path automation_pool diag_itcm editor_settings extra_lane_memory
    fx_editor_guard fx_pagevisuals gfx_retrigger granular_ack granular_assignment_colors granular_binding granular_bridge
    granular_clear_release granular_clear_views granular_controls granular_current granular_current_arm granular_fine granular_flow
    granular_inactive_pad granular_inplace granular_knob_brightness granular_lanes granular_latch_feedback granular_layout
    granular_lifecycle granular_lifetime granular_menu_pulse granular_navigation_storage granular_notes granular_oneshot
    granular_owner granular_ownership_return granular_packing granular_poll granular_pool granular_producer granular_project
    granular_record_bar granular_retrigger granular_route granular_runtime granular_settings_ui granular_shift_settings
    granular_snapshot granular_source granular_stock granular_zones heldlights heldlocks input_trace page_clear_ownership
    plus_usb projectdma projectfile projectprobe projectqueue sample_save_pipeline sdyield_rp shift_tap stepoffload sticky_assign
    stock_knob_parity storageshadow stretch_dsp track_view_colors turn_bar"
  has filter_cutoff && list="$list filter_audio filter_cutoff filter_editor editor_reverse_cycle"
  has pitch_envelope_dsp && list="$list pitch_editor"
  has ring_mod_dsp && list="$list ring_editor"
  has scrub_knobs && list="$list scrub_editor"
  has settings_buffer_itcm_start && list="$list gs_v11_read"
  has scan_dsp && list="$list scan_dsp fx_scan_page"
  export PY
  out=$(for t in $list; do echo $t; done | xargs -P 8 -I{} bash -c '"$PY" tests/emu_{}.py '"$b"' >/dev/null 2>&1; echo "{} $?"' | sort)
  bad=$(echo "$out" | grep -v " 0$" || true)
  echo "editor and Granular tests: $(echo "$out" | wc -l) run${bad:+, failed: $(echo $bad)}"
  [ -z "$bad" ] || fail=1
fi
[ $fail = 0 ] && echo "ALL SUITES PASS" || { echo "SOME SUITES FAILED"; exit 1; }
