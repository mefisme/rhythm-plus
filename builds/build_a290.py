"""A290: Stock Tune on the Pitch page."""

from build_a276 import build


if __name__ == "__main__":
    build("a290", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--release"])
