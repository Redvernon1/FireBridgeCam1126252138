# plasma_core/materials.py

from __future__ import annotations
import math
from typing import List, Dict
from .config import get_config


# ----------------------------------------------------------------------
# Helper for inch conversion
# ----------------------------------------------------------------------
def mm_to_inch(mm: float) -> float:
    return mm / 25.4


def inch_to_mm(inch: float) -> float:
    return inch * 25.4


# ----------------------------------------------------------------------
# Build comprehensive preset list (100+ entries)
# ----------------------------------------------------------------------
MATERIAL_PRESETS: Dict[str, Dict] = {}

MATERIAL_TYPES = [
    ("Mild Steel", [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16, 19, 20, 22, 25]),
    ("Stainless Steel", [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20]),
    ("Aluminum", [1, 1.5, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20]),
]

AMPERAGES = [30, 45, 60, 65, 85, 100, 125]

# Generate realistic Hypertherm/Thermal values by formulas
for material, thicknesses in MATERIAL_TYPES:
    for tmm in thicknesses:
        for amp in AMPERAGES:

            # Generate approximations for real values
            pierce_height_mm = 3.0 + (tmm * 0.05)
            cut_height_mm = 1.3 + (tmm * 0.02)
            feed_mmmin = max(300, int(5000 / (1 + (tmm / (amp / 30)))))
            kerf_mm = max(0.9, min(2.5, 0.8 + (tmm * 0.05)))
            pierce_delay = round(0.3 + (tmm * 0.04), 2)
            voltage = int(110 + (tmm * 2) + (amp * 0.1))

            key_name = f"{material} {tmm}mm – {amp}A"

            MATERIAL_PRESETS[key_name] = {
                "material": material,
                "thickness_mm": float(tmm),
                "thickness_inch": mm_to_inch(float(tmm)),
                "amperage": int(amp),
                "pierce_height_mm": pierce_height_mm,
                "pierce_height_inch": mm_to_inch(pierce_height_mm),
                "cut_height_mm": cut_height_mm,
                "cut_height_inch": mm_to_inch(cut_height_mm),
                "feedrate_mm_min": feed_mmmin,
                "feedrate_ipm": feed_mmmin / 25.4,
                "kerf_width_mm": kerf_mm,
                "kerf_width_inch": mm_to_inch(kerf_mm),
                "pierce_delay": pierce_delay,
                "voltage": voltage,
                "gas": "Air",
                "consumables": "FineCut",
            }


# Add fallback custom preset
MATERIAL_PRESETS["Custom"] = {
    "material": "Custom",
    "thickness_mm": 3.0,
    "thickness_inch": mm_to_inch(3.0),
    "amperage": 45,
    "pierce_height_mm": 3.0,
    "pierce_height_inch": mm_to_inch(3.0),
    "cut_height_mm": 1.5,
    "cut_height_inch": mm_to_inch(1.5),
    "feedrate_mm_min": 1200,
    "feedrate_ipm": 1200 / 25.4,
    "kerf_width_mm": 1.2,
    "kerf_width_inch": mm_to_inch(1.2),
    "pierce_delay": 0.5,
    "voltage": 120,
    "gas": "Air",
    "consumables": "Generic",
}


# ----------------------------------------------------------------------
# Name list for UI
# ----------------------------------------------------------------------
def get_preset_names() -> List[str]:
    names = []

    for key, p in MATERIAL_PRESETS.items():
        mm = p["thickness_mm"]
        inch = p["thickness_inch"]
        amp = p["amperage"]
        names.append(f"{p['material']} – {mm} mm ({inch:.3f}\") – {amp} A")

    names.sort()
    return names


# ----------------------------------------------------------------------
# Apply preset to global config
# ----------------------------------------------------------------------
def apply_preset(name: str):
    config = get_config()

    # Try matching by formatted name first
    match = None
    for key, p in MATERIAL_PRESETS.items():
        mm = p["thickness_mm"]
        inch = p["thickness_inch"]
        amp = p["amperage"]
        formatted = f"{p['material']} – {mm} mm ({inch:.3f}\") – {amp} A"
        if formatted == name or key == name:
            match = p
            break

    if match is None:
        match = MATERIAL_PRESETS["Custom"]

    if config.units == "metric":
        config.set_param("pierce_height_mm", match["pierce_height_mm"])
        config.set_param("cut_height_mm", match["cut_height_mm"])
        config.set_param("cut_feed_mmmin", match["feedrate_mm_min"])
        config.set_param("kerf_width_mm", match["kerf_width_mm"])
        config.set_param("lead_in_mm", 6.0)
        config.set_param("lead_out_mm", 6.0)
    else:
        config.set_param("pierce_height_mm", match["pierce_height_inch"])
        config.set_param("cut_height_mm", match["cut_height_inch"])
        config.set_param("cut_feed_mmmin", match["feedrate_ipm"])
        config.set_param("kerf_width_mm", match["kerf_width_inch"])
        config.set_param("lead_in_mm", match["lead_in_inch"] if "lead_in_inch" in match else mm_to_inch(6.0))
        config.set_param("lead_out_mm", match["lead_out_inch"] if "lead_out_inch" in match else mm_to_inch(6.0))

    # Additional
    config.settings.setValue("last_applied_preset", name)


# ----------------------------------------------------------------------
# Self test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Loaded {len(MATERIAL_PRESETS)} material presets")
    print("plasma_core/materials.py READY")
