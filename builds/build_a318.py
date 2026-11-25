"""A318: A317 + latched, a held button (or Shift + a held button) shows its view; Clear + a cue deletes it; a held cue loops at the K3 length; timed jumps happen on the clock."""
from build_a276 import build
if __name__ == "__main__":
    build("a318", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--cue-peek", "--cue-loop", "--cue-sync", "--release"])
