"""A317: A316 + jumps land on the first pulse and each track takes its automation; only a Shift tap ends the latch."""
from build_a276 import build
if __name__ == "__main__":
    build("a317", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--release"])
