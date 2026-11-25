"""A300: A299 without the Macro page; reads GS v11 saves from A297-A299."""

from build_a276 import build


if __name__ == "__main__":
    build("a300", ["--fill-dsp-gaps", "--filter-dsp-probe", "--pitch-dsp-probe", "--ring-dsp-probe", "--read-v11", "--release"])
