"""A324: A323 + one cue timing: pads 17-24 and K4 (pads 18-24 only) set it; a cue jumps on it and a held cue loops on it."""
from build_a276 import build
if __name__ == "__main__":
    build("a324", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--cue-peek", "--cue-loop", "--cue-sync", "--cue-down", "--cue-k1", "--cue-speed", "--cue-home", "--cue-v3", "--cue-cols", "--cue-one", "--release"])
