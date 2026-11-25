"""A279: FX and editor size savings, plus Filter cycle-pad brightness."""

from build_a276 import build


if __name__ == "__main__":
    build("a279", ["--fill-dsp-gaps", "--filter-dsp-probe", "--release"])
