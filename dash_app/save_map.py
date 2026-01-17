import plotly.graph_objects as go
import pandas as pd
import json

# load data
df = pd.read_csv('../data/wide_weekly_scaledPer10k.csv')
means = df.set_index('Region').mean(axis=1).reset_index()
means.columns = ['Region', 'mean_trolleys']
means['mean_trolleys'] = means['mean_trolleys'].round(2)

# load geojson
with open('hse_regions.geojson') as f:
    geojson = json.load(f)

# map names
name_map = {
    'HSE Dublin and Midlands': 'HSE Dublin and Midlands HR',
    'HSE Dublin and North East': 'HSE Dublin and North East HR',
    'HSE Dublin and South East': 'HSE Dublin and South East HR',
    'HSE Mid West': 'HSE Midwest HR',
    'HSE South West': 'HSE South West HR',
    'HSE West and North West': 'HSE West and North West HR',
}
means['geojson_name'] = means['Region'].map(name_map)

# label positions (hand-picked for readability)
label_positions = {
    'HSE Dublin and Midlands': {'lat': 53.35, 'lon': -7.5},
    'HSE Dublin and North East': {'lat': 53.85, 'lon': -6.4},
    'HSE Dublin and South East': {'lat': 52.5, 'lon': -6.8},
    'HSE Mid West': {'lat': 52.7, 'lon': -8.8},
    'HSE South West': {'lat': 51.9, 'lon': -9.2},
    'HSE West and North West': {'lat': 54.0, 'lon': -9.0},
}

# create choropleth
fig = go.Figure(go.Choropleth(
    geojson=geojson,
    locations=means['geojson_name'],
    z=means['mean_trolleys'],
    featureidkey='properties.HR_operational_name',
    colorscale='Reds',
    marker_line_width=1,
    marker_line_color='white',
    colorbar=dict(
        title=dict(text='Mean Weekly<br>Trolleys (per 10k)', side='right'),
        thickness=15
    )
))

# add annotations with white rectangular backgrounds
annotations = []
for _, row in means.iterrows():
    region = row['Region']
    pos = label_positions[region]
    short_name = region.replace('HSE ', '').replace(' and ', ' & ')

    annotations.append(dict(
        x=pos['lon'],
        y=pos['lat'],
        text=f"<b>{short_name}</b><br>{row['mean_trolleys']:.1f}",
        showarrow=False,
        font=dict(size=12, color='#333'),
        bgcolor='rgba(255,255,255,0.9)',
        bordercolor='#ccc',
        borderwidth=1,
        borderpad=6,
    ))

fig.update_layout(
    geo=dict(
        scope='europe',
        center=dict(lat=53.4, lon=-7.8),
        projection_scale=28,
        showland=True,
        landcolor='#f0f0f0',
        showlakes=False,
        showcountries=False,
        showcoastlines=True,
        coastlinecolor='#ccc',
    ),
    margin={'r': 10, 't': 80, 'l': 10, 'b': 10},
    title=dict(
        text='<b>Mean Weekly Trolley Counts by HSE Region</b>',
        font=dict(size=28),
        x=0.5,
        xanchor='center'
    ),
    font_family='Inter, -apple-system, BlinkMacSystemFont, sans-serif',
    annotations=annotations
)

# save
fig.write_image('map.png', width=1000, height=900, scale=2)
print('Saved to map.png')
