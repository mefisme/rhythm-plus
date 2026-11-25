"""A302: A301 with the MIDI Thru modes (Merge, Filter), USB merge and the Merge clock rule."""
from build_a276 import build
if __name__ == "__main__":
    build("a302", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--release"])
