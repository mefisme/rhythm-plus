"""A325: A324 + a saved cue pulses only on the pattern pass that holds its song step."""
from build_a276 import build
if __name__ == "__main__":
    build("a325", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--latch-tap", "--cue-tune", "--cue-auto", "--cue-peek", "--cue-loop", "--cue-sync", "--cue-down", "--cue-k1", "--cue-speed", "--cue-home", "--cue-v3", "--cue-cols", "--cue-one", "--cue-pass", "--release"])
