# scripts/map_outputs.py
# Produces four matplotlib figures from GEE-exported GeoTIFFs:
#   Figure 1 - Multi-panel index comparison across 2022, 2024, 2026
#   Figure 2 - Headline change detection map (classified dNBR)
#   Figure 3 - Time series line chart of mean index values
#   Figure 4 - Southern detail: RGB 2022, RGB 2026, classified dNBR

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patches as patches
import matplotlib.colors as mcolors
from matplotlib.ticker import FormatStrFormatter
from PIL import Image as PILImage
import rasterio
from rasterio.windows import from_bounds
import geopandas as gpd
import os

# --- Configuration ---
FIGURES_DIR = 'outputs/figures'
DATA_DIR = 'outputs/geotiffs'

BOUNDARY_PATH = (
    r'raw_data\WDPA_WDOECM_Jun2026_Public_555703480_shp_0'
    r'\WDPA_WDOECM_Jun2026_Public_555703480_shp-polygons.shp'
)

YEARS = [2022, 2024, 2026]

INSET_WEST  = 105.588
INSET_EAST  = 105.763
INSET_NORTH = 12.855
INSET_SOUTH = 12.759

BG = '#000000'
FIG_BG = '#000000'

ZONAL_STATS = {
    'NDVI': [0.7498, 0.6831, 0.7219],
    'EVI':  [0.4312, 0.4160, 0.4315],
    'NBR':  [0.5111, 0.4666, 0.5004],
    'NDRE': [0.5056, 0.4587, 0.4596],
    'NDMI': [0.2066, 0.1775, 0.2028],
}


def load_raster_band(filepath, band=1):
    with rasterio.open(filepath) as src:
        data = src.read(band).astype(float)
        transform = src.transform
        crs = src.crs
        nodata = src.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data, transform, crs


def load_raster_band_windowed(filepath, band, west, south, east, north):
    with rasterio.open(filepath) as src:
        window = from_bounds(west, south, east, north, src.transform)
        data = src.read(band, window=window).astype(float)
        nodata = src.nodata
    if nodata is not None:
        data[data == nodata] = np.nan
    return data


def load_rgb(year):
    filepath = os.path.join(DATA_DIR, f'PreyLang_RGB_{year}.tif')
    with rasterio.open(filepath) as src:
        r = src.read(1).astype(float)
        g = src.read(2).astype(float)
        b = src.read(3).astype(float)
        nodata = src.nodata
    if nodata is not None:
        for arr in [r, g, b]:
            arr[arr == nodata] = np.nan
    for arr in [r, g, b]:
        valid = arr[~np.isnan(arr)]
        if len(valid) > 0:
            vmin, vmax = np.percentile(valid, 2), np.percentile(valid, 98)
            arr[:] = np.clip(arr, vmin, vmax)
    def norm(arr):
        mn, mx = np.nanmin(arr), np.nanmax(arr)
        return (arr - mn) / (mx - mn) if mx > mn else arr
    return np.dstack([norm(r), norm(g), norm(b)])


def load_rgb_windowed(year, west, south, east, north):
    filepath = os.path.join(DATA_DIR, f'PreyLang_RGB_{year}.tif')
    with rasterio.open(filepath) as src:
        window = from_bounds(west, south, east, north, src.transform)
        r = src.read(1, window=window).astype(float)
        g = src.read(2, window=window).astype(float)
        b = src.read(3, window=window).astype(float)
        nodata = src.nodata
    if nodata is not None:
        for arr in [r, g, b]:
            arr[arr == nodata] = np.nan
    for arr in [r, g, b]:
        valid = arr[~np.isnan(arr)]
        if len(valid) > 0:
            vmin, vmax = np.percentile(valid, 2), np.percentile(valid, 98)
            arr[:] = np.clip(arr, vmin, vmax)
    def norm(arr):
        mn, mx = np.nanmin(arr), np.nanmax(arr)
        return (arr - mn) / (mx - mn) if mx > mn else arr
    return np.dstack([norm(r), norm(g), norm(b)])


def load_index_band(year, band_num):
    filepath = os.path.join(DATA_DIR, f'PreyLang_Indices_{year}.tif')
    data, transform, crs = load_raster_band(filepath, band=band_num)
    return data


def add_boundary_overlay(ax, boundary_gdf, color='white', linewidth=1.0):
    boundary_gdf.boundary.plot(ax=ax, color=color, linewidth=linewidth)


def style_ax(ax):
    ax.set_facecolor(BG)
    ax.tick_params(left=False, bottom=False,
                   labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_edgecolor('#333333')


def figure1_index_comparison(boundary_gdf):
    print('Producing Figure 1 - index comparison...')

    fig, axes = plt.subplots(4, 3, figsize=(15, 22))
    fig.patch.set_facecolor(FIG_BG)

    row_labels = ['RGB', 'NDVI', 'EVI', 'NBR']
    index_bands = {'NDVI': 1, 'EVI': 2, 'NBR': 3}
    veg_cmap = 'RdYlGn'

    # Compute shared global min/max per index across all three years
    # so colorbar ranges are consistent for direct year-to-year comparison
    shared_ranges = {}
    for label, band in index_bands.items():
        all_valid = []
        for year in YEARS:
            data = load_index_band(year, band)
            valid = data[~np.isnan(data)]
            if len(valid) > 0:
                all_valid.append(valid)
        if all_valid:
            combined = np.concatenate(all_valid)
            shared_ranges[label] = (
                np.percentile(combined, 2),
                np.percentile(combined, 98)
            )

    # Reference shape from first index raster
    ref_data = load_index_band(YEARS[0], 1)
    ref_h, ref_w = ref_data.shape

    # Pre-resize all RGB images to exactly match index raster dimensions
    # so all panels share identical pixel extents and align correctly
    rgb_arrays = {}
    for year in YEARS:
        rgb = load_rgb(year)
        pil_img = PILImage.fromarray((rgb * 255).astype(np.uint8))
        pil_img = pil_img.resize((ref_w, ref_h), PILImage.BILINEAR)
        rgb_arrays[year] = np.array(pil_img) / 255.0

    for col, year in enumerate(YEARS):
        for row, label in enumerate(row_labels):
            ax = axes[row, col]
            style_ax(ax)
            ax.set_xlim(0, ref_w)
            ax.set_ylim(ref_h, 0)

            # Year label above every panel in every row
            ax.set_title(str(year), color='white', fontsize=11,
                        fontweight='bold', pad=4)

            if label == 'RGB':
                ax.imshow(rgb_arrays[year], interpolation='bilinear',
                         extent=[0, ref_w, ref_h, 0], aspect='auto')
            else:
                data = load_index_band(year, index_bands[label])
                vmin, vmax = shared_ranges[label]
                clipped = np.clip(data, vmin, vmax)
                im = ax.imshow(clipped, cmap=veg_cmap,
                               vmin=vmin, vmax=vmax,
                               interpolation='bilinear',
                               extent=[0, ref_w, ref_h, 0], aspect='auto')
                cbar = plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
                cbar.ax.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
                cbar.ax.tick_params(colors='white', labelsize=7)
                cbar.outline.set_edgecolor('white')

            add_boundary_overlay(ax, boundary_gdf, color='white', linewidth=0.6)

            # Bold index label on left column only
            if col == 0:
                ax.set_ylabel(label, color='white', fontsize=11,
                            fontweight='bold', labelpad=8)

    fig.suptitle(
        'Prey Lang Wildlife Sanctuary - Forest Health Indices\n'
        'Sentinel-2 Dry Season Composites (Jan-Feb)',
        color='white', fontsize=15, fontweight='bold', y=0.99
    )

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    outpath = os.path.join(FIGURES_DIR, 'figure1_index_comparison.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=FIG_BG)
    plt.close()
    print(f'  Saved: {outpath}')


def figure2_change_detection(boundary_gdf):
    print('Producing Figure 2 - change detection map...')

    filepath = os.path.join(DATA_DIR, 'PreyLang_Classified_2022_2026.tif')
    data, transform, crs = load_raster_band(filepath, band=1)

    class_colors = ['#1a9641', '#ffffbf', '#fdae61', '#d7191c']
    class_labels = ['Gain / Recovery', 'Stable', 'Moderate Loss', 'High Loss']
    cmap = mcolors.ListedColormap(class_colors)
    bounds = [0.5, 1.5, 2.5, 3.5, 4.5]
    norm = mcolors.BoundaryNorm(bounds, cmap.N)

    fig, ax = plt.subplots(1, 1, figsize=(10, 13))
    fig.patch.set_facecolor(FIG_BG)
    style_ax(ax)

    ax.imshow(data, cmap=cmap, norm=norm, interpolation='nearest')
    add_boundary_overlay(ax, boundary_gdf, color='white', linewidth=1.2)

    # Southern detail rectangle: white outer border, black inner border
    with rasterio.open(filepath) as src:
        row_n, col_w = src.index(INSET_WEST, INSET_NORTH)
        row_s, col_e = src.index(INSET_EAST, INSET_SOUTH)
    rect_white = patches.Rectangle(
        (col_w - 2, row_n - 2), (col_e - col_w) + 4, (row_s - row_n) + 4,
        linewidth=3, edgecolor='white', facecolor='none')
    rect_black = patches.Rectangle(
        (col_w, row_n), col_e - col_w, row_s - row_n,
        linewidth=2, edgecolor='black', facecolor='none')
    ax.add_patch(rect_white)
    ax.add_patch(rect_black)
    ax.text(col_w, row_n - 15, 'Fig. 4 detail',
            color='white', fontsize=8, fontweight='bold',
            bbox=dict(facecolor='black', edgecolor='white',
                     boxstyle='round,pad=0.2'))

    # Legend with black/white swatch for inset box symbol
    legend_patches = [mpatches.Patch(color=c, label=l)
                      for c, l in zip(class_colors, class_labels)]
    inset_patch = mpatches.Patch(facecolor='black', edgecolor='white',
                                  linewidth=2, label='Detail inset (Fig. 4)')
    legend_patches.append(inset_patch)

    legend = ax.legend(
        handles=legend_patches, loc='lower left',
        facecolor=BG, edgecolor='white',
        labelcolor='white', fontsize=10,
        title='Disturbance Class', title_fontsize=10
    )
    legend.get_title().set_color('white')

    # Stats box left side below legend
    ax.text(0.02, 0.18,
            'Moderate loss: 291 km²\nHigh loss: 211 km²\n'
            'Total disturbed: ~502 km²\n(~12% of sanctuary)',
            transform=ax.transAxes, fontsize=9, color='white',
            ha='left', va='top',
            bbox=dict(boxstyle='round', facecolor=BG,
                     edgecolor='white', alpha=0.9))

    ax.set_title(
        'Prey Lang Wildlife Sanctuary\nForest Disturbance 2022-2026\n'
        'Classified dNBR | Sentinel-2 | EPSG:4326',
        color='white', fontsize=13, fontweight='bold', pad=12
    )

    ax.annotate('N', xy=(0.96, 0.12), xytext=(0.96, 0.08),
                xycoords='axes fraction',
                fontsize=12, color='white', ha='center',
                arrowprops=dict(arrowstyle='->', color='white', lw=2))

    plt.tight_layout()
    outpath = os.path.join(FIGURES_DIR, 'figure2_change_detection.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=FIG_BG)
    plt.close()
    print(f'  Saved: {outpath}')


def figure3_time_series():
    print('Producing Figure 3 - time series chart...')

    fig, ax = plt.subplots(figsize=(11, 6))
    fig.patch.set_facecolor(FIG_BG)
    ax.set_facecolor(BG)

    colors = {
        'NDVI': '#2ecc71',
        'EVI':  '#00ffff',
        'NBR':  '#e74c3c',
        'NDRE': '#f39c12',
        'NDMI': '#3498db',
    }

    # Vertical offsets to prevent label overlap where indices are close in value
    y_offsets = {
        'NDVI': 10, 'EVI': 10, 'NBR': 18, 'NDRE': 10, 'NDMI': 10
    }
    # EVI 2026 pulled left and slightly lower to sit close to its own line
    # without overlapping NDRE label above it
    evi_offsets = {2022: (0, 10), 2024: (0, 10), 2026: (-16, 4)}

    for index_name, values in ZONAL_STATS.items():
        ax.plot(YEARS, values, marker='o', linewidth=2,
                color=colors[index_name], label=index_name, markersize=7)
        for year, val in zip(YEARS, values):
            if index_name == 'EVI':
                x_off, y_off = evi_offsets[year]
            else:
                x_off, y_off = 0, y_offsets[index_name]
            ax.annotate(f'{val:.3f}', (year, val),
                       textcoords='offset points',
                       xytext=(x_off, y_off),
                       ha='center', fontsize=8,
                       color=colors[index_name])

    ax.set_xlabel('Year', color='white', fontsize=12)
    ax.set_ylabel('Mean Index Value', color='white', fontsize=12)
    ax.set_title(
        'Prey Lang Wildlife Sanctuary - Mean Spectral Index Values\n'
        'Sentinel-2 Dry Season Composites (Jan-Feb) | 2022-2026',
        color='white', fontsize=13, fontweight='bold'
    )

    ax.set_xticks(YEARS)
    ax.tick_params(colors='white')
    for spine in ax.spines.values():
        spine.set_edgecolor('#444444')
    ax.grid(True, color='#333333', linestyle='--', alpha=0.6)

    # Legend outside plot area to the right so it does not overlap data
    ax.legend(
        facecolor=BG, edgecolor='white',
        labelcolor='white', fontsize=10,
        loc='upper left', bbox_to_anchor=(1.01, 1),
        borderaxespad=0
    )

    plt.tight_layout()
    outpath = os.path.join(FIGURES_DIR, 'figure3_time_series.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=FIG_BG)
    plt.close()
    print(f'  Saved: {outpath}')


def figure4_southern_detail(boundary_gdf):
    print('Producing Figure 4 - southern detail inset...')

    class_colors = ['#1a9641', '#ffffbf', '#fdae61', '#d7191c']
    class_labels = ['Gain / Recovery', 'Stable', 'Moderate Loss', 'High Loss']
    cmap = mcolors.ListedColormap(class_colors)
    bounds_cls = [0.5, 1.5, 2.5, 3.5, 4.5]
    norm = mcolors.BoundaryNorm(bounds_cls, cmap.N)

    boundary_clip = boundary_gdf.clip(
        (INSET_WEST, INSET_SOUTH, INSET_EAST, INSET_NORTH))

    fig, axes = plt.subplots(1, 3, figsize=(18, 7))
    fig.patch.set_facecolor(FIG_BG)

    # Left - RGB 2022
    ax0 = axes[0]
    style_ax(ax0)
    rgb_2022 = load_rgb_windowed(
        2022, INSET_WEST, INSET_SOUTH, INSET_EAST, INSET_NORTH)
    ax0.imshow(rgb_2022, interpolation='bilinear')
    if not boundary_clip.empty:
        boundary_clip.boundary.plot(ax=ax0, color='white', linewidth=0.8)
    ax0.set_title('RGB Composite 2022\nSouthern Detail Area',
                  color='white', fontsize=11, fontweight='bold', pad=6)

    # Middle - RGB 2026
    ax1 = axes[1]
    style_ax(ax1)
    rgb_2026 = load_rgb_windowed(
        2026, INSET_WEST, INSET_SOUTH, INSET_EAST, INSET_NORTH)
    ax1.imshow(rgb_2026, interpolation='bilinear')
    if not boundary_clip.empty:
        boundary_clip.boundary.plot(ax=ax1, color='white', linewidth=0.8)
    ax1.set_title('RGB Composite 2026\nSouthern Detail Area',
                  color='white', fontsize=11, fontweight='bold', pad=6)

    # Right - classified dNBR
    ax2 = axes[2]
    style_ax(ax2)
    classified_detail = load_raster_band_windowed(
        os.path.join(DATA_DIR, 'PreyLang_Classified_2022_2026.tif'), 1,
        INSET_WEST, INSET_SOUTH, INSET_EAST, INSET_NORTH)
    ax2.imshow(classified_detail, cmap=cmap, norm=norm,
               interpolation='nearest')
    if not boundary_clip.empty:
        boundary_clip.boundary.plot(ax=ax2, color='white', linewidth=0.8)

    legend_patches = [mpatches.Patch(color=class_colors[i],
                                     label=class_labels[i])
                      for i in range(4)]
    legend = ax2.legend(
        handles=legend_patches, loc='lower left',
        facecolor=BG, edgecolor='white',
        labelcolor='white', fontsize=7,
        title='Disturbance Class', title_fontsize=7,
        handlelength=1, handleheight=0.8,
        borderpad=0.4, labelspacing=0.3
    )
    legend.get_title().set_color('white')
    ax2.set_title('Forest Disturbance 2022-2026\nClassified dNBR | Southern Detail Area',
                  color='white', fontsize=11, fontweight='bold', pad=6)

    fig.suptitle(
        'Prey Lang Wildlife Sanctuary - Southern Disturbance Detail\n'
        'Sentinel-2 | EPSG:4326 | See Figure 2 for full sanctuary context',
        color='white', fontsize=13, fontweight='bold'
    )

    plt.tight_layout()
    outpath = os.path.join(FIGURES_DIR, 'figure4_southern_detail.png')
    plt.savefig(outpath, dpi=150, bbox_inches='tight', facecolor=FIG_BG)
    plt.close()
    print(f'  Saved: {outpath}')


def main():
    os.makedirs(FIGURES_DIR, exist_ok=True)
    boundary_gdf = gpd.read_file(BOUNDARY_PATH).to_crs('EPSG:4326')

    figure1_index_comparison(boundary_gdf)
    figure2_change_detection(boundary_gdf)
    figure3_time_series()
    figure4_southern_detail(boundary_gdf)

    print('All figures saved to', FIGURES_DIR)


if __name__ == '__main__':
    main()