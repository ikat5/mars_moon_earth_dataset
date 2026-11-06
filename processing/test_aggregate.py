import unittest
import numpy as np
from rasterio.transform import from_bounds
from rasterio.io import MemoryFile
from processing.aggregate import GeographicAggregator, aggregate_raster_blocks


class AreaAggregationTests(unittest.TestCase):
    def test_constant_partial_coverage_and_zero(self):
        transform = from_bounds(-180,-90,180,90,4,4)
        ag = GeographicAggregator(transform,(4,4),(2,2))
        x = np.full((4,4),8.0)
        valid = np.ones((4,4),bool)
        valid[0:2,0] = False
        x[0:2,2:4] = 0
        mean, coverage = ag.mean(x,valid)
        np.testing.assert_allclose(mean,[[8,0],[8,8]])
        np.testing.assert_allclose(coverage,[[.5,1],[1,1]])

    def test_spherical_latitude_weighting_and_missing(self):
        ag = GeographicAggregator(from_bounds(-180,-90,180,90,2,4),(4,2),(2,2))
        x = np.array([[100,100],[0,0],[0,0],[100,100]],float)
        valid = np.ones((4,2),bool)
        valid[2:,1] = False
        mean, coverage = ag.mean(x,valid)
        self.assertAlmostEqual(mean[0,0],100*(1-np.sin(np.pi/4)),9)
        self.assertTrue(np.isnan(mean[1,1]))
        self.assertEqual(coverage[1,1],0)

    def test_misaligned_grids_preserve_constant_and_mass(self):
        ag = GeographicAggregator(from_bounds(-180.02,-90.01,180.02,90.01,8,4),(4,8),(6,10))
        mean, coverage = ag.mean(np.full((4,8),7.),np.ones((4,8),bool))
        np.testing.assert_allclose(mean,7.)
        np.testing.assert_allclose(coverage,1.,atol=1e-12)

    def test_blocked_raster_matches_full_grid(self):
        transform=from_bounds(-180,-90,180,90,10,8)
        values=np.arange(80,dtype=np.float32).reshape(8,10)
        values[1:3,3]=-9999
        with MemoryFile() as memory:
            with memory.open(driver='GTiff',width=10,height=8,count=1,dtype='float32',
                             transform=transform,crs='EPSG:4326',nodata=-9999) as ds:
                ds.write(values,1)
                actual=aggregate_raster_blocks(ds,(6,8),block_rows=2)
        expected=GeographicAggregator(transform,(8,10),(6,8)).mean(values,values>=0)
        for a,b in zip(actual,expected):np.testing.assert_allclose(a,b,equal_nan=True,atol=1e-10)

    def test_support_mask_distinguishes_ocean_zero_from_valid_dry_zero(self):
        transform=from_bounds(-180,-90,180,90,4,2)
        raw=np.array([[0,0,100,300],[0,0,200,400]],dtype='uint16')
        et0=np.array([[65535,65535,1000,1000],[1000,1000,0,0]],dtype='uint16')
        with MemoryFile() as am,MemoryFile() as em:
            common=dict(driver='GTiff',width=4,height=2,count=1,dtype='uint16',
                        transform=transform,crs='EPSG:4326')
            with am.open(**common) as a,em.open(**common,nodata=65535) as e:
                a.write(raw,1);e.write(et0,1)
                mean,coverage=aggregate_raster_blocks(a,(2,2),block_rows=1,positive_support=e)
        np.testing.assert_allclose(mean,[[np.nan,200],[0,np.nan]],equal_nan=True)
        np.testing.assert_allclose(coverage,[[0,1],[1,0]])


if __name__=='__main__':unittest.main()
