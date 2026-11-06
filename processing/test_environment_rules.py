import unittest
import numpy as np
from processing.environment_rules import environment_flags


class EnvironmentalScreeningTests(unittest.TestCase):
    def test_unknown_wet_built_and_crop_cases_fail_independently(self):
        n=8
        data={'landcover_strict_area_coverage':np.ones(n),
              'landcover_barren_class_fraction':np.full(n,.9),
              'landcover_water_class_fraction':np.zeros(n),
              'landcover_built_class_fraction':np.zeros(n),
              'landcover_cropland_or_mosaic_class_fraction':np.zeros(n),
              'aridity_index':np.full(n,.1),'aridity_index_area_coverage':np.ones(n)}
        data['landcover_barren_class_fraction'][1]=np.nan
        data['aridity_index'][2]=np.nan
        data['aridity_index'][3]=.9
        data['landcover_barren_class_fraction'][4]=.2
        data['landcover_built_class_fraction'][5]=.1
        data['landcover_cropland_or_mosaic_class_fraction'][6]=.2
        data['landcover_water_class_fraction'][7]=.2
        flags,eligible=environment_flags(data)
        np.testing.assert_array_equal(flags,[0,1,2,64,4,16,32,8])
        np.testing.assert_array_equal(eligible,[True,False,False,False,False,False,False,False])

    def test_boundaries_valid_zero_and_masked_missing(self):
        data={'landcover_strict_area_coverage':np.array([.95,.949,1.]),
              'landcover_barren_class_fraction':np.array([.8,.9,1.]),
              'landcover_water_class_fraction':np.array([.05,0.,0.]),
              'landcover_built_class_fraction':np.array([.01,0.,0.]),
              'landcover_cropland_or_mosaic_class_fraction':np.array([.05,0.,0.]),
              'aridity_index':np.ma.array([.2,0.,0.],mask=[False,False,True]),
              'aridity_index_area_coverage':np.array([.95,1.,1.])}
        flags,eligible=environment_flags(data)
        np.testing.assert_array_equal(flags,[0,1,2])
        np.testing.assert_array_equal(eligible,[True,False,False])


if __name__=='__main__':unittest.main()
