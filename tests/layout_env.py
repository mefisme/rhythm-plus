"""RAM-layout flags that ourram reads at import, taken from a build's manifest report."""
import os


def granular(report):
    g = report.get("granular", {})
    if "arm_kernel" in g and g.get("base_build"):   # build_granular_current's connected builds
        os.environ["RH_GRANULAR_CURRENT_ARM"] = "1"
        os.environ["RH_GRANULAR_COMPANION"] = "1" if report.get("storageshadow", {}).get("granular_settings_bytes") in (224, 288) else "0"
        os.environ["RH_GRANULAR_FINE"] = "1" if g.get("fine_controls") else "0"
    os.environ["RH_DSPZIP"] = "1" if "dspzip" in report else "0"
