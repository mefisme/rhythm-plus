"""A314: A313 + the scrub latches: Shift + Play held 1 s; a Shift tap, a second 1 s hold or another button ends it."""
from build_a276 import build
if __name__ == "__main__":
    build("a314", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--k1-edge", "--cue-plus", "--cue-latch", "--release"])
