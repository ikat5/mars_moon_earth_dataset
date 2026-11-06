"""Explicit Earth-only screening rules, separate from planetary resemblance."""
import numpy as np

RULES={
    'minimum_landcover_coverage':.95,
    'minimum_aridity_coverage':.95,
    'minimum_barren_class_fraction':.80,
    'maximum_water_class_fraction':.05,
    'maximum_built_class_fraction':.01,
    'maximum_cropland_or_mosaic_class_fraction':.05,
    'maximum_aridity_index':.20,
}
FLAGS={
    '1':'Land-cover evidence missing, invalid, or below 95% strict area coverage',
    '2':'Aridity evidence missing, invalid, or below 95% area coverage',
    '4':'Less than 80% of cell area is strictly classified as barren',
    '8':'More than 5% of cell area is classified as water',
    '16':'More than 1% of cell area is classified as built-up',
    '32':'More than 5% of cell area is classified as cropland or crop mosaic',
    '64':'Historical aridity index exceeds 0.20',
}
LAND_FIELDS=['landcover_strict_area_coverage','landcover_barren_class_fraction',
             'landcover_water_class_fraction','landcover_built_class_fraction',
             'landcover_cropland_or_mosaic_class_fraction']
ARIDITY_FIELDS=['aridity_index','aridity_index_area_coverage']


def environment_flags(arrays):
    """Returns flags and environmental eligibility; NULL cannot pass a gate.

Thresholds are declared engineering selections, not fitted acceptance criteria.
"""
    values={name:np.ma.asarray(arrays[name],dtype=float).filled(np.nan) for name in LAND_FIELDS+ARIDITY_FIELDS}
    lengths={len(value) for value in values.values()}
    if len(lengths)!=1:raise ValueError('Environment arrays must have equal lengths')
    flags=np.zeros(next(iter(lengths)),dtype=np.uint16)
    land_valid=np.logical_and.reduce([np.isfinite(values[n])&(values[n]>=0)&(values[n]<=1) for n in LAND_FIELDS])
    land_valid &= values['landcover_strict_area_coverage']>=RULES['minimum_landcover_coverage']
    ai,coverage=values['aridity_index'],values['aridity_index_area_coverage']
    ai_valid=np.isfinite(ai)&(ai>=0)&np.isfinite(coverage)&(coverage>=RULES['minimum_aridity_coverage'])&(coverage<=1)
    flags[~land_valid] |= 1
    flags[~ai_valid] |= 2
    comparisons=[(4,'landcover_barren_class_fraction',np.less,RULES['minimum_barren_class_fraction']),
                 (8,'landcover_water_class_fraction',np.greater,RULES['maximum_water_class_fraction']),
                 (16,'landcover_built_class_fraction',np.greater,RULES['maximum_built_class_fraction']),
                 (32,'landcover_cropland_or_mosaic_class_fraction',np.greater,RULES['maximum_cropland_or_mosaic_class_fraction']),
                 (64,'aridity_index',np.greater,RULES['maximum_aridity_index'])]
    for bit,name,comparison,threshold in comparisons:
        flags[np.isfinite(values[name]) & comparison(values[name],threshold)] |= bit
    return flags,flags==0
