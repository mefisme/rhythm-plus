"""A0122: remove the custom Clear-button error reporter; keep read-only diagnostics."""
from build_a0121 import HERE, build as baseline
NAME = "A0122"

def build():
    b = baseline(name=NAME, error_led=False)
    assert "errled" not in b.report
    return b

def main():
    out = build().finish(HERE / "firmware" / NAME.lower())
    for f in out.glob(f"circuitrhythm-5706-{NAME}.*"):
        f.replace(out / f"rhythmplus-{NAME}{f.suffix}")

if __name__ == "__main__":
    main()
