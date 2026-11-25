"""A296: Fine Ring Mod frequency control."""

from build_a276 import build


if __name__ == "__main__":
    build("a296", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--release"])
