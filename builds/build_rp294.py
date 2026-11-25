"""Packed offline Ring Mod DSP measurement on A294."""

from build_a276 import build


if __name__ == "__main__":
    build("rp294", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe"])
