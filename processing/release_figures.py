"""Scientific overview of the complete terrain/environment release."""
import json
import duckdb
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from processing.config import ROOT
from processing.prepare import digest, write_json


def figures():
    version='0.2.0';data=ROOT/'prepared'/version
    output=ROOT/'analysis'/f'figures_{version}';output.mkdir(exist_ok=True)
    summary=json.loads((ROOT/'analysis'/f'release_summary_{version}.json').read_text())
    evaluation=json.loads((ROOT/'analysis'/f'evaluation_{version}'/'retrieval_evaluation.json').read_text())
    with duckdb.connect() as db:
        earth=db.execute('''SELECT cell_id,eligible_terrain,eligible_dry_barren,ndvi_valid_month_count,
          ndvi_gapfilled_area_time_fraction FROM read_parquet(?) ORDER BY cell_id''',[str(data/'earth_features.parquet')]).fetchnumpy()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(14,9.5),layout='constrained')
    ax=axes[0,0]
    labels=['Earth','Moon','Mars'];bodies=[summary['bodies'][b] for b in ['earth','moon','mars']]
    eligible=[b['terrain_eligible_rows']/b['rows']*100 for b in bodies]
    ax.barh(labels,eligible,color='#257f8c');ax.set(xlim=(0,105),xlabel='Source cells eligible for terrain screening (%)',title='A. Broad terrain coverage; limited comparison dimensions')
    for i,(pct,b) in enumerate(zip(eligible,bodies)):ax.text(2,i,f'{pct:.1f}% of {b["rows"]:,} cells',color='white',va='center',weight='bold')
    ax.set_xticks([0,25,50,75,100]);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    ax=axes[0,1];x=np.arange(4)
    for i,(case,label,color) in enumerate([('jezero','Jezero','#257f8c'),('lunar_equatorial_coordinate','Moon 0°, 0°','#c37b34')]):
        values=[evaluation['cases'][case][k]['regional_retention']*100 for k in ['slope_emphasis','amplitude_emphasis','no_median_slope','no_relief']]
        ax.bar(x+(i-.5)*.36,values,.36,label=label,color=color)
    ax.set(ylim=(0,105),ylabel='Baseline top-ten regions retained (%)',title='B. Dry/barren ranking sensitivity')
    ax.set_xticks(x,['Slope emphasis','Amplitude emphasis','Drop median slope','Drop relief'],rotation=12,ha='right')
    ax.legend(frameon=False);ax.text(.01,.98,'One-to-one regional match within 100 km',transform=ax.transAxes,va='top',fontsize=9)
    grid=np.zeros(1440*2880,dtype=np.uint8);grid[earth['cell_id']]=1
    grid[earth['cell_id'][earth['eligible_terrain']]]=2;grid[earth['cell_id'][earth['eligible_dry_barren']]]=3
    ax=axes[1,0]
    ax.imshow(grid.reshape(1440,2880),extent=(-180,180,-90,90),origin='upper',interpolation='nearest',
        cmap=ListedColormap(['#f0f3f5','#c7cbd1','#92b4bb','#a55d25']),vmin=0,vmax=3)
    ax.set(title=f'C. {summary["earth_counts"]["dry_barren_terrain_cells"]:,} cells pass historical dry/barren gates')
    ax.legend(handles=[Patch(color='#a55d25',label='Dry/barren + terrain'),Patch(color='#92b4bb',label='Other terrain eligible'),
                       Patch(color='#c7cbd1',label='Terrain ineligible')],loc='lower left',fontsize=8,framealpha=.96)
    grid[:]=0;grid[earth['cell_id']]=1
    any_month=earth['ndvi_valid_month_count']>0;complete=earth['ndvi_valid_month_count']==204
    grid[earth['cell_id'][any_month]]=2;grid[earth['cell_id'][complete]]=3
    ax=axes[1,1]
    ax.imshow(grid.reshape(1440,2880),extent=(-180,180,-90,90),origin='upper',interpolation='nearest',
        cmap=ListedColormap(['#f0f3f5','#babfc8','#d69b35','#507d45']),vmin=0,vmax=3)
    ax.set(title='D. Historical vegetation support, 2001–2017')
    ax.legend(handles=[Patch(color='#507d45',label='All 204 months accepted'),Patch(color='#d69b35',label='1–203 months accepted'),
                       Patch(color='#babfc8',label='No month meets 80% valid area')],loc='lower left',fontsize=8,framealpha=.96)
    for ax in axes[1]:
        ax.set(xlabel='Longitude (degrees east)',ylabel='Latitude (degrees north)',xticks=[-180,-90,0,90,180],yticks=[-90,-45,0,45,90])
    fig.suptitle('TerraTwin: evidence available for regional analog screening',fontsize=18,weight='bold')
    fig.supxlabel('Fit is uncalibrated terrain resemblance. NDVI is smoothed/gap-filled, provisional and unscored.\nMaps are geographic, not equal-area. Historical coverage does not establish field suitability or a new analog discovery.',fontsize=10)
    for extension in ['png','pdf']:fig.savefig(output/f'dataset_diagnostics.{extension}',dpi=160)
    plt.close(fig)
    inputs=[data/'manifest.json',ROOT/'analysis'/f'release_summary_{version}.json',ROOT/'analysis'/f'evaluation_{version}'/'retrieval_evaluation.json']
    write_json(output/'provenance.json',{'dataset_version':version,'inputs':{str(p.relative_to(ROOT)):digest(p) for p in inputs},'code_sha256':digest(__file__)})
    print(f'Wrote {output}')


if __name__=='__main__':figures()
