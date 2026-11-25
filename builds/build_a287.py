"""A287: Clear released automation on assigned knobs."""

from build_a276 import build


if __name__ == "__main__":
    build("a287", ["--fill-dsp-gaps", "--filter-dsp-probe", "--release"])
