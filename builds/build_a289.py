"""A289: Pitch envelope, LFO and editor."""

from build_a276 import build


if __name__ == "__main__":
    build("a289", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--release"])
