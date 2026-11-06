import unittest
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds
from processing.landcover import class_fractions


class LandcoverQualityTests(unittest.TestCase):
    def test_unclassified_barren_does_not_count_as_barren(self):
        classes=np.array([[16,16,2,2],[16,16,2,2],[255,255,17,17],[255,255,17,17]],dtype=np.uint8)
        qc=np.array([[1,0,0,8],[1,0,0,8],[255,255,2,2],[255,255,2,2]],dtype=np.uint8)
        with MemoryFile() as a,MemoryFile() as b:
            options=dict(driver='GTiff',width=4,height=4,count=1,dtype='uint8',nodata=255,
                         transform=from_bounds(-180,-90,180,90,4,4),crs='EPSG:4326')
            with a.open(**options) as da,b.open(**options) as db:
                da.write(classes,1);db.write(qc,1)
                result,_=class_fractions(da,db,(2,2),1)
        np.testing.assert_allclose(result['landcover_strict_area_coverage'],[[.5,.5],[0,1]])
        np.testing.assert_allclose(result['landcover_barren_class_fraction'],[[.5,0],[np.nan,0]],equal_nan=True)
        np.testing.assert_allclose(result['landcover_unclassified_land_fraction'],[[.5,0],[0,0]])
        np.testing.assert_allclose(result['landcover_modified_quality_fraction'],[[0,.5],[0,0]])
        np.testing.assert_allclose(result['landcover_water_class_fraction'],[[0,0],[np.nan,1]],equal_nan=True)


if __name__=='__main__':unittest.main()
