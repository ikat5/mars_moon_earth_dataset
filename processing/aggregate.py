"""Exact spherical cell-overlap means for north-up geographic rasters.

Each source pixel is piecewise constant. Missing area contributes zero coverage,
never a zero measurement. Longitude and sin(latitude) overlaps are separable.
"""
import numpy as np


def overlap_map(source_edges, target_edges, latitude=False):
    source_edges, target_edges = np.asarray(source_edges), np.asarray(target_edges)
    if np.any(np.diff(source_edges) <= 0) or np.any(np.diff(target_edges) <= 0):
        raise ValueError("Edges must be strictly increasing")
    measure = (lambda x: np.sin(np.radians(np.clip(x, -90, 90)))) if latitude else (lambda x: x)
    mappings = []
    for lo, hi in zip(target_edges[:-1], target_edges[1:]):
        first = max(0, int(np.searchsorted(source_edges, lo, side="right"))-1)
        last = min(len(source_edges)-2, int(np.searchsorted(source_edges, hi, side="left"))-1)
        row = []
        for i in range(first, last+1):
            a, b = max(lo, source_edges[i]), min(hi, source_edges[i+1])
            if b > a:
                row.append((i, (measure(b)-measure(a))/(measure(hi)-measure(lo))))
        mappings.append(row)
    width = max(1, max(map(len, mappings)))
    indices = np.zeros((len(mappings), width), dtype=np.int64)
    weights = np.zeros((len(mappings), width), dtype=np.float64)
    for j, row in enumerate(mappings):
        for k, (i, w) in enumerate(row):
            indices[j,k], weights[j,k] = i, w
    return indices, weights


class GeographicAggregator:
    def __init__(self, transform, source_shape, target_shape=(1440, 2880)):
        if transform.b or transform.d or transform.a <= 0 or transform.e >= 0:
            raise ValueError("Only north-up geographic grids are supported")
        h, w = source_shape
        self.source_shape, self.target_shape = source_shape, target_shape
        x = transform.c + np.arange(w+1)*transform.a
        y = (transform.f + np.arange(h+1)*transform.e)[::-1]
        self.columns = overlap_map(x, np.linspace(-180,180,target_shape[1]+1))
        self.rows = overlap_map(y, np.linspace(-90,90,target_shape[0]+1), latitude=True)

    def weighted_sum(self, values):
        if values.shape != self.source_shape:
            raise ValueError("Source shape changed")
        source = values[::-1]
        ir, wr = self.rows
        ic, wc = self.columns
        middle = np.zeros((len(ir), source.shape[1]), dtype=np.float64)
        for k in range(ir.shape[1]):
            middle += source[ir[:,k],:] * wr[:,k,None]
        output = np.zeros(self.target_shape, dtype=np.float64)
        for k in range(ic.shape[1]):
            output += middle[:,ic[:,k]] * wc[None,:,k]
        return output[::-1].copy()

    def mean(self, values, valid):
        coverage = self.weighted_sum(valid.astype(np.float32))
        numerator = self.weighted_sum(np.where(valid, values, 0))
        mean = np.full(self.target_shape, np.nan)
        np.divide(numerator, coverage, out=mean, where=coverage > 1e-12)
        return mean, np.clip(coverage, 0, 1)


def aggregate_raster_blocks(dataset, target_shape=(1440,2880), block_rows=12, positive_support=None):
    """Memory-bounded exact-area aggregation for a large single-band raster."""
    from rasterio.windows import Window
    if dataset.crs.to_epsg() != 4326:
        raise ValueError("Input must use EPSG:4326")
    if positive_support is not None:
        # AI and ET0 origins differ by ~1.4e-8 degrees in provider metadata.
        if (positive_support.shape != dataset.shape or positive_support.crs != dataset.crs
            or not np.allclose(tuple(positive_support.transform),tuple(dataset.transform),rtol=0,atol=1e-7)):
            raise ValueError("Positive-support raster must share the input pixel grid")
    ag = GeographicAggregator(dataset.transform, dataset.shape, target_shape)
    ir, wr = ag.rows
    ic, wc = ag.columns
    means = np.full(target_shape, np.nan)
    coverage = np.zeros(target_shape)
    for start in range(0, target_shape[0], block_rows):
        stop = min(start+block_rows, target_shape[0])
        indices, weights = ir[start:stop], wr[start:stop]
        active = indices[weights > 0]
        if not active.size:
            continue
        first, last = int(active.min()), int(active.max())
        window = Window(0, dataset.height-1-last, dataset.width, last-first+1)
        arr = dataset.read(1, window=window, masked=True)[::-1]
        valid = ~np.ma.getmaskarray(arr) & np.isfinite(arr.data)
        # Negative AI/ET0 is invalid. Valid zero is retained.
        valid &= arr.data >= 0
        if positive_support is not None:
            support=positive_support.read(1,window=window,masked=True)[::-1]
            valid &= (~np.ma.getmaskarray(support) & np.isfinite(support.data) & (support.data>0))
        positions = np.clip(indices-first, 0, last-first)
        for is_coverage in (True, False):
            source = valid.astype(np.float64) if is_coverage else np.where(valid, arr.data, 0)
            middle = np.zeros((stop-start, dataset.width))
            for k in range(indices.shape[1]):
                middle += source[positions[:,k],:] * weights[:,k,None]
            out = np.zeros((stop-start,target_shape[1]))
            for k in range(ic.shape[1]):
                out += middle[:,ic[:,k]] * wc[None,:,k]
            if is_coverage:
                cover = out
                coverage[start:stop] = np.clip(cover,0,1)
            else:
                np.divide(out, cover, out=means[start:stop], where=cover > 1e-12)
    return means[::-1].copy(), coverage[::-1].copy()
