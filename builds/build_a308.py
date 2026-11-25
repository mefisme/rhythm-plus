"""A308: A307; the scrub's knobs work on every Track Parameter Editor page."""
from build_a276 import build
if __name__ == "__main__":
    build("a308", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--scrub-knobs", "--release"])
