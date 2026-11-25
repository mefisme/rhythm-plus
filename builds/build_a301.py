"""A301: A300 with Scan on the Extras page (pad 30); GS v12 saves."""
from build_a276 import build
if __name__ == "__main__":
    build("a301", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--release"])
