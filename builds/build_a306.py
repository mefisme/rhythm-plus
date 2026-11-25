"""A306: A305 with quantize's pad 25 in the probability green of Mutate; a quantize flashes it."""
from build_a276 import build
if __name__ == "__main__":
    build("a306", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--release"])
