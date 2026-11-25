"""A322: A321 + Shift + Play held 0.5 s latches (no hold mode; a tap is the stock Shift + Play); pads 17-24 the jump timing; K2 K1 speed, K3 scanner, K4 loop length, K5 sound; sticky Shift kept."""
from build_a276 import build
if __name__ == "__main__":
    build("a322", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--cue-peek", "--cue-loop", "--cue-sync", "--cue-down", "--cue-k1", "--cue-speed", "--cue-home", "--cue-v3", "--release"])
