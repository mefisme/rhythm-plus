"""A303: A302 with Clear + Save, in place of Shift + Save, for saving a project whose Plus file is missing with the default settings."""
from build_a276 import build
if __name__ == "__main__":
    build("a303", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--scan-dsp-probe", "--midi-merge", "--clear-save", "--release"])
