"""A310: A309 + the cue scrub: hot cues on pads 17-32 while scrubbing, K3 marker, K4 jump timing, a 1 s hold latches."""
from build_a276 import build
if __name__ == "__main__":
    build("a310", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues", "--release"])
