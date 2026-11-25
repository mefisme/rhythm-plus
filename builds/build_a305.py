"""A305: A304; a linked internal project saves with no card and keeps its link; Pattern Settings pad 25 quantizes the pattern."""
from build_a276 import build
if __name__ == "__main__":
    build("a305", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--release"])
