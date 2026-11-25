"""A288: Preserve native Stock knob brightness in the editor."""

from build_a276 import build


if __name__ == "__main__":
    build("a288", ["--fill-dsp-gaps", "--filter-dsp-probe", "--release"])
