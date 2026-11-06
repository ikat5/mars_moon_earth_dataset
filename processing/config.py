"""Versioned scientific assumptions; experimental until evaluated with site evidence."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"
DEFAULT_OUTPUT = ROOT / "prepared" / VERSION
CORE = ["slope_median_deg", "slope_p90_deg", "relief_m", "roughness_rms_m", "tri_mean_m"]
QC_FLAGS = {
    "1": "DEM coverage missing or below 95%",
    "2": "One or more core terrain measurements missing",
    "4": "Core terrain physical range or quantile ordering invalid",
    "8": "Elevation minimum/mean/maximum ordering invalid",
    "16": "Geology missing or undefined",
    "32": "Mean temperature missing",
    "64": "Earth mean elevation below -500 m; investigate land mask/source",
}
PROFILES = {
    "terrain_screening": {
        "name": "Regional terrain resemblance",
        "status": "experimental_available",
        "eligibility_column": "eligible_terrain",
        "purpose": "Regional slope and terrain-amplitude screening for field navigation exercises",
        "features": {
            "slope_median_deg": {"weight": 0.25, "tolerance": 5.0, "group": "slope"},
            "slope_p90_deg": {"weight": 0.25, "tolerance": 10.0, "group": "slope"},
            "relief_m": {"weight": 0.25, "tolerance": 500.0, "group": "terrain_amplitude"},
            "roughness_rms_m": {"weight": 0.25, "tolerance": 100.0, "group": "terrain_amplitude"},
        },
        "required_features": CORE,
        "minimum_dem_valid_fraction": 0.95,
        "earth_target_area_ratio": [2/3, 1.5],
        "minimum_fit": 50.0,
        "default_separation_km": 100.0,
        "limitations": [
            "Tolerances, area ratio and minimum fit are uncalibrated engineering defaults.",
            "Native grid cells have approximately comparable but unequal physical support.",
            "Vegetation, land cover, aridity, access, boulders and mechanical strength are not screened.",
            "Fit is not a probability, accuracy estimate or hardware-performance prediction.",
        ],
    },
    "volcanic_field_geology": {
        "status": "pending_enrichment", "missing": ["exposed_material_evidence", "validated_geology_crosswalk", "vegetation_land_cover"],
    },
    "cold_dry_operations": {
        "status": "pending_enrichment", "missing": ["precipitation_pet", "vegetation_land_cover", "temperature_sampling_harmonization", "antarctic_temperature"],
    },
    "cave_reconnaissance": {"status": "pending_validation", "missing": ["verified_cave_catalog_and_local_evidence"]},
    "ice_drilling": {"status": "unsupported", "missing": ["ice_depth_and_properties", "substrate_mechanical_properties"]},
}


def comparison_policy(name, feature):
    if name in CORE:
        return "terrain_with_scale_checks", "Native grid support differs; retain baseline and cell footprint. TRI is diagnostic, not an additional default score term."
    if name in {"water_indicator_score", "solar_power_index", "hydrogen_enrichment_pct", "cold_trap_flag"}:
        return "body_specific_context", "Different inputs or physical relevance across bodies; direct shared-name scoring prohibited."
    if name.startswith("tsurf_") or name == "liquid_water_window_frac":
        return "sampling_harmonization_required", "Earth overpass climatology, Moon lunar-day measurements and Mars modeled seasonal sampling differ."
    if feature.get("units") == "category":
        return "categorical_crosswalk_required", "Category names are preserved; numeric subtraction of category IDs is prohibited."
    if name in {"landing_hazard_index", "traversability_index", "terrain_class"}:
        return "derived_terrain_context", "Reuses terrain measurements; not independent evidence."
    if name.endswith("_sigma") or name.endswith("_coverage") or name in {"dem_valid_frac", "lst_sample_coverage"}:
        return "quality_or_uncertainty", "Use for eligibility/uncertainty, not physical resemblance."
    return "context_unvalidated", "Not admitted to the initial comparison profile; requires a purpose-specific scientific review."
