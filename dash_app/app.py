import dash
from dash import html, dcc, dash_table, callback, Output, Input
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json

# load data
df = pd.read_csv('../data/wide_weekly_scaledPer10k.csv')

# calculate mean trolley count per region
means = df.set_index('Region').mean(axis=1).reset_index()
means.columns = ['Region', 'mean_trolleys']
means['mean_trolleys'] = means['mean_trolleys'].round(2)

# load geojson
with open('hse_regions.geojson') as f:
    geojson = json.load(f)

# map csv region names to geojson names
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

# create map
fig = px.choropleth_mapbox(
    means,
    geojson=geojson,
    locations='geojson_name',
    featureidkey='properties.HR_operational_name',
    color='mean_trolleys',
    color_continuous_scale='Reds',
    mapbox_style='carto-positron',
    center={'lat': 53.5, 'lon': -8},
    zoom=5.6,
    hover_name='Region',
    hover_data={'geojson_name': False, 'mean_trolleys': ':.2f'},
    labels={'mean_trolleys': 'Mean Weekly Trolleys (per 10k)'}
)
fig.update_layout(
    margin={'r': 0, 't': 0, 'l': 0, 'b': 0},
    coloraxis_colorbar=dict(
        title=dict(side='right'),
        thickness=15
    ),
    font_family='Inter, -apple-system, BlinkMacSystemFont, sans-serif'
)

# add region labels (mapbox charts need a Scattermapbox trace for lon/lat text)
label_df = means[['Region', 'mean_trolleys']].copy()
label_df['lat'] = label_df['Region'].map(lambda r: label_positions.get(r, {}).get('lat'))
label_df['lon'] = label_df['Region'].map(lambda r: label_positions.get(r, {}).get('lon'))
label_df = label_df.dropna(subset=['lat', 'lon'])
label_df['label'] = label_df.apply(
    lambda row: f"{row['Region'].replace('HSE ', '').replace(' and ', ' & ')}<br>{row['mean_trolleys']:.1f}",
    axis=1,
)

fig.add_trace(go.Scattermapbox(
    lat=label_df['lat'],
    lon=label_df['lon'],
    mode='markers+text',
    marker=dict(
        size=30,
        color='rgba(255,255,255,0.85)',
        line=dict(color='rgba(0,0,0,0.2)', width=1),
    ),
    text=label_df['label'],
    textfont=dict(size=12, color='#333'),
    textposition='middle center',
    hoverinfo='skip',
    showlegend=False,
))

# app
app = dash.Dash(__name__)

FONT = 'Inter, -apple-system, BlinkMacSystemFont, sans-serif'

app.layout = html.Div([
    html.H1('HSE Trolley Data by Region'),
    html.P('Mean weekly trolley counts per 10,000 population'),
    html.Div([
        html.Div([
            dash_table.DataTable(
                id='dataTable1',
                columns=[
                    {'name': 'Region', 'id': 'Region'},
                    {'name': 'Mean Trolleys', 'id': 'mean_trolleys'}
                ],
                data=means[['Region', 'mean_trolleys']].to_dict('records'),
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'left', 'padding': '10px', 'fontFamily': FONT},
                style_header={'fontWeight': 'bold'},
            )
        ], style={'flex': '1', 'minWidth': '300px', 'marginRight': '20px'}),
        html.Div([
            dcc.Graph(id='map', figure=fig, style={'height': '70vh'})
        ], style={'flex': '2', 'minWidth': '400px'})
    ], style={'display': 'flex', 'flexWrap': 'wrap'})
], style={'fontFamily': FONT, 'padding': '20px'})

# reverse lookup: geojson name -> csv name
reverse_name_map = {v: k for k, v in name_map.items()}

@callback(
    Output('dataTable1', 'style_data_conditional'),
    Input('map', 'hoverData')
)
def highlight_row(hoverData):
    if not hoverData:
        return []

    geojson_name = hoverData['points'][0]['location']
    region = reverse_name_map.get(geojson_name)

    if not region:
        return []

    return [{
        'if': {'filter_query': f'{{Region}} = "{region}"'},
        'backgroundColor': '#ffffcc'
    }]

if __name__ == '__main__':
    app.run(debug=True)
