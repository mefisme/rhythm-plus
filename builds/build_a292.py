"""A292: Pitch value-bar taps."""

from build_a276 import build


if __name__ == "__main__":
    build("a292", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--release"])
