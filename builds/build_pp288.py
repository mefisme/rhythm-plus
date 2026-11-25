"""PP288: offline measurement of the Pitch DSP playback adapter."""

from build_a276 import build


if __name__ == "__main__":
    build("pp288", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe"])
