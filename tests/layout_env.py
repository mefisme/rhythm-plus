"""RAM-layout flags that ourram reads at import, taken from a build's manifest report."""
import os


def granular(report):
    g = report.get("granular", {})
    if "arm_kernel" in g and g.get("base_build"):   # build_granular_current's connected builds
        os.environ["RH_GRANULAR_CURRENT_ARM"] = "1"
        os.environ["RH_GRANULAR_COMPANION"] = "1" if report.get("storageshadow", {}).get("granular_settings_bytes") else "0"
        os.environ["RH_GRANULAR_FINE"] = "1" if g.get("fine_controls") else "0"
        # The settings slot grows with the Filter and Pitch pages (ourram's granstore).
        os.environ["RH_FILTER_EDITOR_PROBE"] = "1" if "filter_cutoff" in report else "0"
        os.environ["RH_PITCH_DSP_PROBE"] = "1" if "pitch_envelope_dsp" in report else "0"
    os.environ["RH_DSPZIP"] = "1" if "dspzip" in report else "0"
    os.environ["RH_STRETCH"] = "1" if "arm" in report.get("stretch", {}) else "0"
    os.environ["RH_TRACKWIPE"] = "1" if report.get("trackreset", {}).get("wipe") else "0"
