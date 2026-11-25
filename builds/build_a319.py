"""A319: A318 + the stock's down bits kept right (Shift and Play act normally after the scrub); Play keeps its stock light; K1 one step per 2 clicks, at once; no K4."""
from build_a276 import build
if __name__ == "__main__":
    build("a319", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--cue-peek", "--cue-loop", "--cue-sync", "--cue-down", "--cue-k1", "--release"])
