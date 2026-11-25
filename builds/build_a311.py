"""A311: A309 + the cue scrub, held: K2 scanner, K3 cue timing, K4 K1 timing; pads 17-23 bar, 24 audition, 25-32 eight cues."""
from build_a276 import build
if __name__ == "__main__":
    build("a311", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--cues2", "--mm-gap", "--stretch-gap", "--release"])
