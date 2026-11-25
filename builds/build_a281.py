"""A281: Filter encoder contrast on Tracks 3 and 5."""

from build_a276 import build


if __name__ == "__main__":
    build("a281", ["--fill-dsp-gaps", "--filter-dsp-probe", "--release"])
