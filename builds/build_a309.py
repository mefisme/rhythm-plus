"""A309: A308; while scrubbing, the Track Parameter Editor draws no knob or page lights, so K1-K2 are green and K3-K8 dark on every page."""
from build_a276 import build
if __name__ == "__main__":
    build("a309", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--scrub-lights", "--release"])
