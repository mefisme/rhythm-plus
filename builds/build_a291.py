"""A291: Pitch Decay follows the K3 Length label."""

from build_a276 import build


if __name__ == "__main__":
    build("a291", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--release"])
