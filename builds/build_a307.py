"""A307: A306; while Shift + Play is held, the selected track's steps show on every screen."""
from build_a276 import build
if __name__ == "__main__":
    build("a307", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--internal-plus", "--internal-keep", "--quantize", "--quantize-flash", "--scrub-any", "--release"])
