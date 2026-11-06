"""Reproducible diagnostic figures; no scores are labeled analog accuracy."""
import json
from pathlib import Path
import duckdb
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from processing.config import ROOT, DEFAULT_OUTPUT


def figures():
    output=ROOT/'analysis'/'figures';output.mkdir(exist_ok=True)
    quality=json.loads((DEFAULT_OUTPUT/'validation.json').read_text())['bodies']
    evaluation=json.loads((ROOT/'analysis/retrieval_evaluation.json').read_text())
    with duckdb.connect() as db:
        earth=db.execute('SELECT cell_id,eligible_terrain FROM read_parquet(?) ORDER BY cell_id',
                         [str(DEFAULT_OUTPUT/'earth_features.parquet')]).fetchnumpy()
        ndvi=db.execute('SELECT cell_id,ndvi_valid_month_count,ndvi_gapfilled_area_time_fraction FROM read_parquet(?) ORDER BY cell_id',
                        [str(ROOT/'prepared/environment_0.1.0/ndvi_sample/features.parquet')]).fetchnumpy()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(14,9),layout='constrained')
    ax=axes[0,0]
    labels=['Earth','Moon','Mars']
    counts=[quality[b]['input_rows'] for b in ['earth','moon','mars']]
    eligible=[quality[b]['eligible_terrain_rows']/counts[i]*100 for i,b in enumerate(['earth','moon','mars'])]
    ax.barh(labels,eligible,color='#257f8c')
    ax.set(xlim=(0,109),xlabel='Source cells eligible for terrain screening (%)',title='A. Large coverage, limited scientific dimensions')
    for i,(pct,n) in enumerate(zip(eligible,counts)):
        ax.text(2,i,f'{pct:.1f}% of {n:,} cells',color='white',va='center',weight='bold')
    ax.set_xticks([0,25,50,75,100]);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    ax=axes[0,1]
    names=['Slope emphasis','Amplitude emphasis','Drop median slope','Drop relief']
    keys=['slope_emphasis','amplitude_emphasis','no_median_slope','no_relief']
    xpos=np.arange(4)
    for i,(case,label,color) in enumerate([('jezero','Jezero','#257f8c'),('lunar_equatorial_coordinate','Moon 0°, 0°','#c37b34')]):
        values=[evaluation['cases'][case][k]['regional_retention']*100 for k in keys]
        ax.bar(xpos+(i-.5)*.36,values,.36,label=label,color=color)
    ax.set(ylim=(0,105),ylabel='Baseline top-ten regions retained (%)',title='B. Rankings depend strongly on chosen features')
    ax.set_xticks(xpos,names,rotation=12,ha='right');ax.legend(frameon=False)
    ax.text(.01,.98,'One-to-one regional match within 100 km',transform=ax.transAxes,va='top',fontsize=9)
    grid=np.zeros(1440*2880,dtype=np.uint8)
    grid[earth['cell_id']]=np.where(earth['eligible_terrain'],2,1)
    ax=axes[1,0]
    ax.imshow(grid.reshape(1440,2880),extent=(-180,180,-90,90),origin='upper',interpolation='nearest',
              cmap=ListedColormap(['#f0f3f5','#d18c67','#357f87']),vmin=0,vmax=2)
    ax.set(title='C. Earth terrain eligibility on the native grid',xlabel='Longitude (degrees east)',ylabel='Latitude (degrees north)')
    ax.set_xticks([-180,-90,0,90,180]);ax.set_yticks([-90,-45,0,45,90])
    ax.legend(handles=[Patch(color='#357f87',label='Terrain eligible'),Patch(color='#d18c67',label='Retained, ineligible')],
              loc='lower left',fontsize=8,framealpha=.95)
    grid[:]=0;grid[earth['cell_id']]=1
    accepted=ndvi['ndvi_valid_month_count']>0
    gap=np.ma.filled(ndvi['ndvi_gapfilled_area_time_fraction'],np.nan)
    grid[ndvi['cell_id'][accepted]]=np.where(gap[accepted]<=.2,2,3)
    ax=axes[1,1]
    ax.imshow(grid.reshape(1440,2880),extent=(-180,180,-90,90),origin='upper',interpolation='nearest',
              cmap=ListedColormap(['#f0f3f5','#babfc8','#507d45','#d69b35']),vmin=0,vmax=3)
    ax.set(title='D. January 2001 vegetation sample: evidence gaps',xlabel='Longitude (degrees east)',ylabel='Latitude (degrees north)')
    ax.set_xticks([-180,-90,0,90,180]);ax.set_yticks([-90,-45,0,45,90])
    ax.legend(handles=[Patch(color='#507d45',label='Accepted; ≤20% gap-filled'),Patch(color='#d69b35',label='Accepted; >20% gap-filled'),
                       Patch(color='#babfc8',label='Absent or <80% area coverage')],loc='lower left',fontsize=8,framealpha=.95)
    fig.suptitle('TerraTwin: what the prepared data can support',fontsize=18,weight='bold')
    fig.supxlabel('Terrain scores are uncalibrated resemblance measures. Vegetation sample is not a seasonal screen. Maps use geographic grids, not equal-area projection.',fontsize=10)
    fig.savefig(output/'dataset_diagnostics.png',dpi=160)
    fig.savefig(output/'dataset_diagnostics.pdf')
    plt.close(fig)
    print(f'Wrote diagnostic PNG and PDF in {output}')


if __name__=='__main__':figures()
