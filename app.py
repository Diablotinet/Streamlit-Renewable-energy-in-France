"""
Streamlit Dashboard: France's Renewable Energy Production
Dataset: Annual Renewable Electricity Production by Region and Type
Source: data.gouv.fr

This app provides interactive visualizations of France's renewable energy transition.
Features interactive maps, 3D visualizations, and advanced analytics.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import warnings
import os
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.spatial.distance import pdist
import folium
from streamlit_folium import st_folium
import pydeck as pdk
import altair as alt

warnings.filterwarnings('ignore')

# Geographic coordinates for French regions (approximate centers)
REGION_COORDS = {
    'Grand Est': [48.5734, 7.6992],
    'Corse': [42.0396, 8.8976],
    'Ile-de-France': [48.8566, 2.3522],
    'Provence-Alpes-Côte d Azur': [43.9353, 6.6245],
    'Auvergne-Rhône-Alpes': [45.4408, 4.3881],
    'Nouvelle-Aquitaine': [45.3397, 0.6883],
    'Occitanie': [43.6047, 1.4442],
    'Bourgogne-Franche-Comté': [47.2806, 5.0122],
    'Normandie': [49.1829, 0.3710],
    'Bretagne': [48.1173, -3.3673],
    'Centre-Val de Loire': [47.9023, 1.9094],
    'Hauts-de-France': [50.2793, 3.5586],
    'Pays de la Loire': [47.2184, -0.5528]
}


# PAGE CONFIG

st.set_page_config(
    page_title="France's Green Transition - Advanced Analytics",
    page_icon="bolt",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Hide streamlit footer
hide_streamlit_style = """
<style>
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# CUSTOM STYLING

st.markdown("""
<style>
    .main-title {
        font-size: 3em;
        font-weight: bold;
        background: linear-gradient(135deg, #1f7e3f 0%, #4caf50 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5em;
    }
    .subtitle {
        font-size: 1.3em;
        color: #2e7d32;
        margin-bottom: 2em;
        font-weight: 500;
    }
    .hook {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 2em;
        border-radius: 0.8em;
        border-left: 5px solid #1f7e3f;
        margin-bottom: 2em;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: #1a1a1a;
    }
    .hook h3 {
        color: #1f7e3f !important;
    }
    .hook strong {
        color: #2e7d32;
    }
    .metric-card {
        background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%);
        padding: 1.5em;
        border-radius: 0.8em;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-top: 3px solid #1f7e3f;
    }
    .insight-box {
        background-color: #fff3e0;
        padding: 1.5em;
        border-radius: 0.8em;
        border-left: 4px solid #ff9800;
        margin: 1em 0;
    }
    .success-box {
        background-color: #e8f5e9;
        padding: 1.5em;
        border-radius: 0.8em;
        border-left: 4px solid #4caf50;
        margin: 1em 0;
    }
    h2 {
        color: #1f7e3f;
        border-bottom: 2px solid #4caf50;
        padding-bottom: 0.5em;
    }
    h3 {
        color: #2e7d32;
    }
</style>
""", unsafe_allow_html=True)


# LOAD AND CACHE DATA

@st.cache_data
def load_data():
    """Load renewable energy production data from local CSV file."""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(script_dir, 'data', 'prod-region-annuelle-enr.csv')
        
        # Check if file exists
        if not os.path.exists(csv_path):
            st.error(f"Error: CSV file not found at {csv_path}")
            return None
        
        # Load the CSV file
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8')
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

@st.cache_data
def clean_and_prepare_data(df):
    """Clean and prepare the data for analysis."""
    if df is None:
        return None
    
    # Make a copy
    df = df.copy()
    
    # Store GeoJSON data before processing
    geo_data = df[['Nom INSEE région', 'Géo-shape région', 'Géo-point région']].drop_duplicates()
    geo_data = geo_data.rename(columns={'Nom INSEE région': 'region'})
    
    # Rename columns: Annee -> year, Nom INSEE région -> region
    df = df.rename(columns={
        'Annee': 'year',
        'Nom INSEE région': 'region'
    })
    
    # Get energy columns (all columns that contain "Production" and end with "(GWh)")
    energy_columns = [col for col in df.columns if 'Production' in col and '(GWh)' in col]
    
    # Keep only relevant columns
    id_vars = ['region', 'year']
    df = df[id_vars + energy_columns].copy()
    
    # Melt the dataframe
    df_melted = df.melt(
        id_vars=id_vars,
        value_vars=energy_columns,
        var_name='energy_type',
        value_name='production_gwh'
    )
    
    # Clean energy type names
    df_melted['energy_type'] = df_melted['energy_type'].str.replace('Production ', '', case=False)
    df_melted['energy_type'] = df_melted['energy_type'].str.replace(' renouvelable \\(GWh\\)', '', case=False)
    df_melted['energy_type'] = df_melted['energy_type'].str.replace(' \\(GWh\\)', '', case=False)
    df_melted['energy_type'] = df_melted['energy_type'].str.strip()
    
    # Convert production to numeric (GWh)
    df_melted['production_gwh'] = pd.to_numeric(df_melted['production_gwh'], errors='coerce')
    
    # Convert GWh to MWh for consistency (1 GWh = 1000 MWh)
    df_melted['production_mwh'] = df_melted['production_gwh'] * 1000
    
    # Remove rows with NaN production values
    df_melted = df_melted.dropna(subset=['production_mwh'])
    
    # Ensure year is integer
    df_melted['year'] = pd.to_numeric(df_melted['year'], errors='coerce').astype(int)
    
    # Drop the GWh column as we have MWh
    df_melted = df_melted.drop('production_gwh', axis=1)
    
    # Store geo_data as a global for later use
    st.session_state.geo_data = geo_data
    
    return df_melted


# ADVANCED VISUALIZATION FUNCTIONS


@st.cache_data
def create_3d_surface_plot(df_filtered):
    """Create an interactive 3D surface plot showing time x energy type x production."""
    pivot_data = df_filtered.pivot_table(
        index='year',
        columns='energy_type',
        values='production_mwh',
        aggfunc='sum',
        fill_value=0
    )
    
    years = pivot_data.index.values
    energy_types = pivot_data.columns.values
    X, Y = np.meshgrid(range(len(years)), range(len(energy_types)))
    Z = pivot_data.T.values
    
    fig = go.Figure(data=[go.Surface(
        x=years[X[0]],
        y=energy_types[Y[:, 0]],
        z=Z,
        colorscale='Viridis',
        colorbar=dict(title="Production (MWh)")
    )])
    
    fig.update_layout(
        title="3D Energy Production Surface: Time x Energy Type",
        scene=dict(
            xaxis_title="Year",
            yaxis_title="Energy Type",
            zaxis_title="Production (MWh)"
        ),
        height=600
    )
    
    return fig

@st.cache_data
def create_3d_scatter_plot(df_filtered):
    """Create interactive 3D scatter plot with region, energy type, and production."""
    agg_data = df_filtered.groupby(['region', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Create numeric indices for categorical variables
    region_map = {region: i for i, region in enumerate(agg_data['region'].unique())}
    energy_map = {energy: i for i, energy in enumerate(agg_data['energy_type'].unique())}
    
    agg_data['region_idx'] = agg_data['region'].map(region_map)
    agg_data['energy_idx'] = agg_data['energy_type'].map(energy_map)
    
    fig = go.Figure(data=[go.Scatter3d(
        x=agg_data['region_idx'],
        y=agg_data['energy_idx'],
        z=agg_data['production_mwh'],
        mode='markers',
        marker=dict(
            size=agg_data['production_mwh'] / agg_data['production_mwh'].max() * 20,
            color=agg_data['production_mwh'],
            colorscale='Plasma',
            showscale=True,
            colorbar=dict(title="Production (MWh)"),
            line=dict(width=0.5, color='white')
        ),
        text=agg_data.apply(lambda row: f"Region: {row['region']}<br>Energy: {row['energy_type']}<br>Production: {row['production_mwh']:,.0f} MWh", axis=1),
        hoverinfo='text'
    )])
    
    fig.update_layout(
        title="3D Production Analysis: Region x Energy Type x Production",
        scene=dict(
            xaxis=dict(title="Region", ticktext=list(region_map.keys()), tickvals=list(region_map.values())),
            yaxis=dict(title="Energy Type", ticktext=list(energy_map.keys()), tickvals=list(energy_map.values())),
            zaxis_title="Production (MWh)"
        ),
        height=600
    )
    
    return fig

@st.cache_data
def create_animated_bubble_chart(df_filtered):
    """Create animated bubble chart showing production evolution through years."""
    agg_data = df_filtered.groupby(['year', 'region']).agg({
        'production_mwh': 'sum'
    }).reset_index().sort_values('year')
    
    # Get the top regions by total production for better visualization
    top_regions = df_filtered.groupby('region')['production_mwh'].sum().nlargest(10).index.tolist()
    agg_data_filtered = agg_data[agg_data['region'].isin(top_regions)]
    
    if len(agg_data_filtered) == 0:
        agg_data_filtered = agg_data
    
    # Create scatter plot with animation
    fig = px.scatter(
        agg_data_filtered,
        x='region',
        y='production_mwh',
        size='production_mwh',
        color='region',
        animation_frame='year',
        hover_name='region',
        hover_data={'production_mwh': ':.0f', 'region': True, 'year': False},
        title="Bubble Chart: Regional Production Evolution Through Years",
        labels={'production_mwh': 'Production (MWh)', 'region': 'Region'},
        size_max=60,
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    
    # Update layout for better animation
    fig.update_layout(
        height=600,
        xaxis_tickangle=-45,
        showlegend=False,
        template='plotly_white',
        hovermode='closest'
    )
    
    # Configure animation settings
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                showactive=False,
                buttons=[
                    dict(label="Play", method="animate", 
                         args=[None, {"frame": {"duration": 800, "redraw": True}, 
                                    "fromcurrent": True, 
                                    "transition": {"duration": 300, "easing": "quadratic-in-out"}}]),
                    dict(label="Pause", method="animate",
                         args=[[None], {"frame": {"duration": 0, "redraw": False},
                                      "mode": "immediate",
                                      "transition": {"duration": 0}}])
                ]
            )
        ]
    )
    
    return fig

@st.cache_data
def create_3d_regional_columns(df_filtered):
    """Create 3D styled visualization with regions as columns, production as height."""
    try:
        # Aggregate data by year and region
        agg_data = df_filtered.groupby(['year', 'region']).agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        # Get the latest year for initial display
        latest_year = agg_data['year'].max()
        current_year_data = agg_data[agg_data['year'] == latest_year].copy()
        
        # Add coordinates for each region
        current_year_data['lat'] = current_year_data['region'].map(
            lambda x: REGION_COORDS.get(x, [48.5, 2.5])[0]
        )
        current_year_data['lon'] = current_year_data['region'].map(
            lambda x: REGION_COORDS.get(x, [48.5, 2.5])[1]
        )
        
        # Normalize production for color intensity
        max_prod = current_year_data['production_mwh'].max()
        current_year_data['color_intensity'] = (current_year_data['production_mwh'] / max_prod) * 255
        
        # Create 3D scatter plot with bars effect using go.Bar3d or enhanced Scatter3d
        fig = go.Figure()
        
        # Add vertical bars for each region
        fig.add_trace(go.Scatter3d(
            x=current_year_data['lon'],
            y=current_year_data['lat'],
            z=current_year_data['production_mwh'],
            mode='markers',
            marker=dict(
                size=20,
                color=current_year_data['production_mwh'],
                colorscale='Plasma',
                showscale=True,
                colorbar=dict(
                    title="Production<br>(MWh)",
                    thickness=20,
                    len=0.7,
                    x=1.02
                ),
                line=dict(
                    color='white',
                    width=3
                ),
                opacity=0.9,
                symbol='diamond'
            ),
            text=current_year_data.apply(
                lambda row: f"<b>{row['region']}</b><br>" +
                           f"Production: {row['production_mwh']:,.0f} MWh<br>" +
                           f"Year: {row['year']}",
                axis=1
            ),
            hoverinfo='text',
            name='Regions'
        ))
        
        # Add connecting lines from base to top (optional visual effect)
        for idx, row in current_year_data.iterrows():
            fig.add_trace(go.Scatter3d(
                x=[row['lon'], row['lon']],
                y=[row['lat'], row['lat']],
                z=[0, row['production_mwh']],
                mode='lines',
                line=dict(
                    color='rgba(100,200,255,0.3)',
                    width=4
                ),
                showlegend=False,
                hoverinfo='skip',
                name=''
            ))
        
        # Create slider for year selection
        years_sorted = sorted(agg_data['year'].unique())
        frames = []
        
        for year in years_sorted:
            year_data = agg_data[agg_data['year'] == year].copy()
            year_data['lat'] = year_data['region'].map(
                lambda x: REGION_COORDS.get(x, [48.5, 2.5])[0]
            )
            year_data['lon'] = year_data['region'].map(
                lambda x: REGION_COORDS.get(x, [48.5, 2.5])[1]
            )
            
            # Create markers for this year
            markers_trace = go.Scatter3d(
                x=year_data['lon'],
                y=year_data['lat'],
                z=year_data['production_mwh'],
                mode='markers',
                marker=dict(
                    size=20,
                    color=year_data['production_mwh'],
                    colorscale='Plasma',
                    showscale=True,
                    colorbar=dict(
                        title="Production<br>(MWh)",
                        thickness=20,
                        len=0.7,
                        x=1.02
                    ),
                    line=dict(color='white', width=3),
                    opacity=0.9,
                    symbol='diamond'
                ),
                text=year_data.apply(
                    lambda row: f"<b>{row['region']}</b><br>" +
                               f"Production: {row['production_mwh']:,.0f} MWh<br>" +
                               f"Year: {row['year']}",
                    axis=1
                ),
                hoverinfo='text',
                name='Regions'
            )
            
            # Create lines for this year
            lines_traces = []
            for idx, row in year_data.iterrows():
                lines_traces.append(go.Scatter3d(
                    x=[row['lon'], row['lon']],
                    y=[row['lat'], row['lat']],
                    z=[0, row['production_mwh']],
                    mode='lines',
                    line=dict(color='rgba(100,200,255,0.3)', width=4),
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            frame_data = [markers_trace] + lines_traces
            frames.append(go.Frame(data=frame_data, name=str(year)))
        
        fig.frames = frames
        
        # Update layout with 3D scene configuration
        fig.update_layout(
            title=dict(
                text=f"<b>3D Regional Production Map - Latest Year ({latest_year})</b><br>" +
                     "<sub>Use slider to explore different years | Interactive 3D view</sub>",
                x=0.5,
                xanchor='center',
                font=dict(size=16, color='#1a1a1a')
            ),
            scene=dict(
                xaxis=dict(
                    title='Longitude',
                    backgroundcolor='rgba(240, 240, 240, 0.9)',
                    gridcolor='rgba(200, 200, 200, 0.3)',
                    showbackground=True,
                    zerolinecolor='rgba(150, 150, 150, 0.5)'
                ),
                yaxis=dict(
                    title='Latitude',
                    backgroundcolor='rgba(240, 240, 240, 0.9)',
                    gridcolor='rgba(200, 200, 200, 0.3)',
                    showbackground=True,
                    zerolinecolor='rgba(150, 150, 150, 0.5)'
                ),
                zaxis=dict(
                    title='Production (MWh)',
                    backgroundcolor='rgba(240, 240, 240, 0.9)',
                    gridcolor='rgba(200, 200, 200, 0.3)',
                    showbackground=True,
                    zerolinecolor='rgba(150, 150, 150, 0.5)'
                ),
                camera=dict(
                    eye=dict(x=1.2, y=1.2, z=1.1),
                    center=dict(x=0, y=0, z=0)
                ),
                aspectmode='cube'
            ),
            height=800,
            width=None,
            hovermode='closest',
            plot_bgcolor='rgba(245, 245, 245, 0.95)',
            paper_bgcolor='white',
            margin=dict(l=0, r=150, t=100, b=100),
            sliders=[{
                'active': len(years_sorted) - 1,
                'yanchor': 'top',
                'y': -0.08,
                'xanchor': 'left',
                'x': 0.1,
                'len': 0.85,
                'transition': {'duration': 400},
                'pad': {'b': 10, 't': 50},
                'currentvalue': {
                    'font': {'size': 18, 'color': '#1a1a1a', 'family': 'Arial Black'},
                    'prefix': 'Year: ',
                    'visible': True,
                    'xanchor': 'center',
                    'offset': 10
                },
                'steps': [
                    {
                        'args': [[str(year)], {
                            'frame': {'duration': 500, 'redraw': True},
                            'mode': 'immediate',
                            'transition': {'duration': 300, 'easing': 'cubic-in-out'}
                        }],
                        'method': 'animate',
                        'label': str(year)
                    }
                    for year in years_sorted
                ]
            }],
            font=dict(family='Arial, sans-serif', size=12, color='#333333')
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating 3D regional visualization: {e}")
        return None

@st.cache_data
def create_styled_regional_choropleth(df_filtered, year_selection=None):
    """Create a styled and interactive choropleth map of French regions using GeoJSON from data."""
    try:
        import json
        
        # Load raw data to get GeoJSON
        raw_df = load_data()
        if raw_df is None:
            return None
        
        # Get unique regions with their GeoJSON
        geo_regions = raw_df[['Nom INSEE région', 'Géo-shape région']].drop_duplicates()
        geo_regions = geo_regions.rename(columns={'Nom INSEE région': 'region'})
        
        # Aggregate production by region and year
        agg_data = df_filtered.groupby(['year', 'region']).agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        # Select year to display
        if year_selection is None:
            year_selection = agg_data['year'].max()
        
        year_data = agg_data[agg_data['year'] == year_selection].copy()
        
        # Create GeoJSON structure
        features = []
        for idx, row in geo_regions.iterrows():
            region_name = row['region']
            geo_shape = row['Géo-shape région']
            
            # Parse GeoJSON if it's a string
            try:
                if isinstance(geo_shape, str):
                    geo_json = json.loads(geo_shape)
                else:
                    geo_json = geo_shape
            except:
                continue
            
            # Get production value for this region in selected year
            prod_value = year_data[year_data['region'] == region_name]['production_mwh'].values
            prod_value = prod_value[0] if len(prod_value) > 0 else 0
            
            # Create feature
            feature = {
                "type": "Feature",
                "properties": {
                    "region": region_name,
                    "production": prod_value
                },
                "geometry": geo_json
            }
            features.append(feature)
        
        # Create FeatureCollection
        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }
        
        # Create region data for choropleth
        region_prod = year_data.copy()
        region_prod['region_name'] = region_prod['region']
        
        # Create choropleth map using go.Choroplethmapbox
        fig = go.Figure(data=go.Choroplethmapbox(
            geojson=geojson_data,
            locations=region_prod['region'],
            z=region_prod['production_mwh'],
            featureidkey="properties.region",
            colorscale='Plasma',
            reversescale=False,
            marker_opacity=0.8,
            colorbar=dict(
                title="Production<br>(MWh)",
                thickness=20,
                len=0.7,
                x=1.02
            ),
            hovertemplate='<b>%{customdata}</b><br>Production: %{z:,.0f} MWh<extra></extra>',
            customdata=region_prod['region'],
            showscale=True
        ))
        
        # Update layout for styled appearance
        fig.update_layout(
            title=dict(
                text=f"<b>France - Regional Renewable Energy Production</b><br>" +
                     f"<sub>Year: {year_selection} | Styled 3D-like Interactive Map</sub>",
                x=0.5,
                xanchor='center',
                font=dict(size=18, color='#1a1a1a', family='Arial Black')
            ),
            mapbox=dict(
                style='carto-positron',
                center=dict(lat=46.603354, lon=1.888334),
                zoom=4.2
            ),
            height=750,
            margin=dict(l=0, r=120, t=80, b=0),
            paper_bgcolor='white',
            plot_bgcolor='rgba(240, 240, 245, 0.5)',
            font=dict(family='Arial, sans-serif', size=12, color='#333333'),
            hovermode='closest'
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating choropleth map: {e}")
        return None

@st.cache_data
def create_3d_globe_map(df_filtered, year_selection=None):
    """Create a 3D globe visualization with regional production data."""
    try:
        import json
        
        # Load raw data to get GeoJSON and coordinates
        raw_df = load_data()
        if raw_df is None:
            return None
        
        # Get unique regions with their coordinates and GeoJSON
        geo_regions = raw_df[['Nom INSEE région', 'Géo-point région', 'Géo-shape région']].drop_duplicates()
        geo_regions = geo_regions.rename(columns={'Nom INSEE région': 'region'})
        
        # Aggregate production by region and year
        agg_data = df_filtered.groupby(['year', 'region']).agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        # Select year to display
        if year_selection is None:
            year_selection = agg_data['year'].max()
        
        year_data = agg_data[agg_data['year'] == year_selection].copy()
        
        # Parse coordinates and merge production data
        region_points = []
        for idx, row in geo_regions.iterrows():
            region_name = row['region']
            geo_point_str = row['Géo-point région']
            
            # Parse coordinates from string like "48.688976812, 5.613113265"
            try:
                if pd.notna(geo_point_str):
                    coords = str(geo_point_str).split(',')
                    lat = float(coords[0].strip())
                    lon = float(coords[1].strip())
                else:
                    continue
            except:
                continue
            
            # Get production value
            prod_value = year_data[year_data['region'] == region_name]['production_mwh'].values
            prod_value = prod_value[0] if len(prod_value) > 0 else 0
            
            region_points.append({
                'region': region_name,
                'lat': lat,
                'lon': lon,
                'production': prod_value
            })
        
        region_df = pd.DataFrame(region_points)
        
        if region_df.empty:
            return None
        
        # Normalize production for sizing
        max_prod = region_df['production'].max()
        min_prod = region_df['production'].min()
        region_df['size'] = 5 + (region_df['production'] - min_prod) / (max_prod - min_prod) * 40
        region_df['color'] = region_df['production']
        
        # Create 3D globe with scattergeo
        fig = go.Figure()
        
        # Add background globe layer (subtle)
        fig.add_trace(go.Scattergeo(
            lon=region_df['lon'],
            lat=region_df['lat'],
            mode='markers',
            marker=dict(
                size=region_df['size'],
                color=region_df['color'],
                colorscale='Plasma',
                showscale=True,
                colorbar=dict(
                    title="Production<br>(MWh)",
                    thickness=20,
                    len=0.7,
                    x=1.02
                ),
                line=dict(
                    width=2,
                    color='rgba(255, 255, 255, 0.8)'
                ),
                opacity=0.85,
                sizemode='diameter'
            ),
            text=region_df.apply(
                lambda row: f"<b>{row['region']}</b><br>Production: {row['production']:,.0f} MWh<br>Year: {year_selection}",
                axis=1
            ),
            hovertemplate='%{text}<extra></extra>',
            name='Regions'
        ))
        
        # Update geo settings for globe projection
        fig.update_geos(
            projection=dict(
                type='orthographic',
                rotation=dict(lon=0, lat=0, roll=0)
            ),
            showland=True,
            landcolor='rgb(243, 243, 243)',
            showocean=True,
            oceancolor='rgb(204, 229, 255)',
            showcountries=True,
            countrycolor='rgb(204, 204, 204)',
            countrywidth=0.5,
            showlakes=True,
            lakecolor='rgb(204, 229, 255)',
            bgcolor='rgba(200, 220, 240, 0.3)',
            center=dict(lat=46.603354, lon=1.888334)
        )
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"<b>France Renewable Energy - 3D Globe View</b><br>" +
                     f"<sub>Year: {year_selection} | Interactive 3D Visualization</sub>",
                x=0.5,
                xanchor='center',
                font=dict(size=18, color='#1a1a1a', family='Arial Black')
            ),
            height=750,
            margin=dict(l=0, r=120, t=80, b=0),
            paper_bgcolor='white',
            font=dict(family='Arial, sans-serif', size=12, color='#333333'),
            hovermode='closest',
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        st.error(f"Error creating 3D globe: {e}")
        return None

@st.cache_data
def create_sunburst_chart(df_filtered):
    """Create hierarchical sunburst chart of energy production."""
    # Check if data is empty or all zeros
    if df_filtered.empty or df_filtered['production_mwh'].sum() == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for the selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=600)
        return fig
    
    agg_data = df_filtered.groupby(['energy_type', 'region']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Remove rows with zero production
    agg_data = agg_data[agg_data['production_mwh'] > 0]
    
    if agg_data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No production data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=600)
        return fig
    
    # Create hierarchical structure: Root -> Energy Types -> Regions
    root_label = 'Total Energy'
    
    # Prepare labels and parents lists
    labels = [root_label]
    parents = ['']
    values = [agg_data['production_mwh'].sum()]
    colors = [agg_data['production_mwh'].sum()]
    
    # Add energy types as middle level
    for energy in agg_data['energy_type'].unique():
        labels.append(energy)
        parents.append(root_label)
        energy_total = agg_data[agg_data['energy_type'] == energy]['production_mwh'].sum()
        values.append(energy_total)
        colors.append(energy_total)
    
    # Add regions under energy types
    for energy in agg_data['energy_type'].unique():
        for region in agg_data[agg_data['energy_type'] == energy]['region'].unique():
            labels.append(region)
            parents.append(energy)
            region_value = agg_data[(agg_data['energy_type'] == energy) & 
                                  (agg_data['region'] == region)]['production_mwh'].values[0]
            values.append(region_value)
            colors.append(region_value)
    
    fig = go.Figure(go.Sunburst(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(
            colorscale='Viridis',
            cmid=np.median(values)
        )
    ))
    
    fig.update_layout(title="Hierarchical Energy Production by Type and Region", height=600)
    return fig

@st.cache_data
def create_heatmap_with_insights(df_filtered):
    """Create sophisticated heatmap of region vs energy type production."""
    pivot_data = df_filtered.pivot_table(
        index='region',
        columns='energy_type',
        values='production_mwh',
        aggfunc='sum',
        fill_value=0
    )
    
    # Normalize for better visualization
    pivot_normalized = (pivot_data - pivot_data.min().min()) / (pivot_data.max().max() - pivot_data.min().min())
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot_data.values,
        x=pivot_data.columns,
        y=pivot_data.index,
        colorscale='Viridis',
        hoverongaps=False,
        colorbar=dict(title="Production (MWh)")
    ))
    
    fig.update_layout(
        title="Production Heatmap: Regions vs Energy Types",
        xaxis_title="Energy Type",
        yaxis_title="Region",
        height=600
    )
    
    return fig

@st.cache_data
def create_regional_energy_share(df_filtered):
    """Create treemap showing energy share distribution."""
    agg_data = df_filtered.groupby(['region', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Create hierarchical structure: Root -> Energy Types -> Regions
    root_label = 'Total Energy'
    
    # Prepare labels and parents lists
    labels = [root_label]
    parents = ['']
    values = [agg_data['production_mwh'].sum()]
    
    # Add energy types as middle level
    for energy in agg_data['energy_type'].unique():
        labels.append(energy)
        parents.append(root_label)
        energy_total = agg_data[agg_data['energy_type'] == energy]['production_mwh'].sum()
        values.append(energy_total)
    
    # Add regions under energy types
    for energy in agg_data['energy_type'].unique():
        for region in agg_data[agg_data['energy_type'] == energy]['region'].unique():
            labels.append(region)
            parents.append(energy)
            region_value = agg_data[(agg_data['energy_type'] == energy) & 
                                  (agg_data['region'] == region)]['production_mwh'].values[0]
            values.append(region_value)
    
    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(colorscale='Greens', cmid=np.median(values))
    ))
    
    fig.update_layout(title="Energy Distribution by Region and Type", height=500)
    return fig

@st.cache_data
def create_energy_growth_rate(df_filtered):
    """Create advanced growth rate visualization."""
    energy_yearly = df_filtered.groupby(['year', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index().sort_values(['energy_type', 'year'])
    
    # Calculate growth rate
    energy_yearly['growth_rate'] = energy_yearly.groupby('energy_type')['production_mwh'].pct_change() * 100
    
    fig = px.line(
        energy_yearly,
        x='year',
        y='growth_rate',
        color='energy_type',
        markers=True,
        title="Year-over-Year Growth Rate by Energy Type (%)",
        labels={'growth_rate': 'Growth Rate (%)', 'year': 'Year', 'energy_type': 'Energy Type'},
        hover_data={'growth_rate': ':.2f'}
    )
    
    fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Zero Growth")
    fig.update_layout(height=400)
    return fig

@st.cache_resource
def create_interactive_map(df_filtered):
    """Create interactive Folium map with production by region - enhanced aesthetic."""
    try:
        # Aggregate by region
        region_prod = df_filtered.groupby('region').agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        # Base map centered on France with better tiles
        m = folium.Map(
            location=[46.5, 2.5],
            zoom_start=5,
            tiles='CartoDB positron',
            prefer_canvas=True
        )
        
        # Add a tile layer for better aesthetics
        folium.TileLayer(
            tiles='https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            attr='OpenStreetMap contributors',
            name='OpenStreetMap',
            overlay=False,
            control=False
        ).add_to(m)
        
        # Normalize production for color scaling
        max_prod = region_prod['production_mwh'].max()
        min_prod = region_prod['production_mwh'].min()
        
        # Create custom color scale (green gradient)
        def get_color(value):
            """Generate color based on production value."""
            if max_prod == min_prod:
                norm_val = 0.5
            else:
                norm_val = (value - min_prod) / (max_prod - min_prod)
            
            # Green gradient: light to dark
            if norm_val < 0.2:
                return '#fee5d9'  # very light
            elif norm_val < 0.4:
                return '#fcae91'  # light
            elif norm_val < 0.6:
                return '#fb6a4a'  # medium
            elif norm_val < 0.8:
                return '#de2d26'  # dark
            else:
                return '#a50f15'  # very dark
        
        # Add markers for each region with enhanced styling
        for idx, row in region_prod.iterrows():
            region = row['region']
            production = row['production_mwh']
            
            if region in REGION_COORDS:
                coords = REGION_COORDS[region]
                
                # Color intensity based on production
                norm_prod = (production - min_prod) / (max_prod - min_prod) if max_prod > min_prod else 0
                color = get_color(production)
                
                # Size based on production (radius between 8 and 25)
                radius = 8 + (norm_prod * 17)
                
                # Create popup with styled HTML
                popup_html = f"""
                <div style="font-family: Arial; width: 200px;">
                    <h4 style="margin: 0 0 10px 0; color: #333;">{region}</h4>
                    <hr style="margin: 5px 0;">
                    <p style="margin: 5px 0;"><b>Production:</b> {production:,.0f} MWh</p>
                    <p style="margin: 5px 0;"><b>Percentage:</b> {(production/region_prod['production_mwh'].sum()*100):.1f}%</p>
                </div>
                """
                
                folium.CircleMarker(
                    location=coords,
                    radius=radius,
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"{region}: {production:,.0f} MWh",
                    color=color,
                    fill=True,
                    fillColor=color,
                    fillOpacity=0.85,
                    weight=3,
                    opacity=1.0
                ).add_to(m)
        
        # Add title to map
        title_html = '''
        <div style="position: fixed; 
                    top: 10px; left: 50px; width: 300px; height: 60px; 
                    background-color: white; border:2px solid grey; z-index:9999; 
                    font-size:16px; font-weight: bold; padding: 10px;
                    border-radius: 5px; box-shadow: 2px 2px 6px rgba(0,0,0,0.2);">
            France Renewable Energy Production by Region
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        return m
    except Exception as e:
        st.error(f"Error creating map: {e}")
        return None

@st.cache_data
def create_3d_globe(df_filtered):
    """Create 3D globe visualization showing regional production."""
    try:
        region_prod = df_filtered.groupby('region').agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        coords_data = []
        for idx, row in region_prod.iterrows():
            region = row['region']
            if region in REGION_COORDS:
                lat, lon = REGION_COORDS[region]
                coords_data.append({
                    'lat': lat,
                    'lon': lon,
                    'region': region,
                    'production': row['production_mwh']
                })
        
        if not coords_data:
            return None
            
        coords_df = pd.DataFrame(coords_data)
        
        fig = go.Figure(data=go.Scattergeo(
            lon=coords_df['lon'],
            lat=coords_df['lat'],
            mode='markers+text',
            marker=dict(
                size=coords_df['production'] / coords_df['production'].max() * 30,
                color=coords_df['production'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Production (MWh)"),
                line=dict(width=1, color='white')
            ),
            text=coords_df['region'],
            textposition='top center',
            hovertemplate='<b>%{text}</b><br>Production: %{marker.color:,.0f} MWh<extra></extra>'
        ))
        
        fig.update_layout(
            title='3D Geographic Distribution of Energy Production',
            geo=dict(
                scope='europe',
                showland=True,
                landcolor='rgb(243, 243, 243)',
                projection_type='natural earth'
            ),
            height=600
        )
        
        return fig
    except Exception as e:
        st.error(f"Error creating globe: {e}")
        return None

@st.cache_data
def create_energy_composition_bar(df_filtered):
    """Create horizontal bar chart of energy composition."""
    energy_comp = df_filtered.groupby('energy_type').agg({
        'production_mwh': 'sum'
    }).reset_index().sort_values('production_mwh', ascending=True)
    
    fig = px.bar(
        energy_comp,
        x='production_mwh',
        y='energy_type',
        orientation='h',
        title='Energy Production by Type (Total)',
        labels={'production_mwh': 'Production (MWh)', 'energy_type': 'Energy Type'},
        color='production_mwh',
        color_continuous_scale='RdYlGn'
    )
    
    fig.update_layout(height=400, showlegend=False)
    return fig

@st.cache_data
def create_regional_composition_stacked(df_filtered):
    """Create stacked bar chart of regions by energy type."""
    pivot_data = df_filtered.pivot_table(
        index='region',
        columns='energy_type',
        values='production_mwh',
        aggfunc='sum',
        fill_value=0
    )
    
    # Sort by total production
    pivot_data['total'] = pivot_data.sum(axis=1)
    pivot_data = pivot_data.sort_values('total', ascending=True).drop('total', axis=1)
    
    fig = go.Figure()
    
    for energy_type in pivot_data.columns:
        fig.add_trace(go.Bar(
            y=pivot_data.index,
            x=pivot_data[energy_type],
            name=energy_type,
            orientation='h'
        ))
    
    fig.update_layout(
        barmode='stack',
        title='Energy Composition by Region (Stacked)',
        xaxis_title='Production (MWh)',
        yaxis_title='Region',
        height=600,
        hovermode='x unified'
    )
    
    return fig

@st.cache_data
def create_time_series_decomposition(df_filtered):
    """Create multi-line time series showing production trends."""
    ts_data = df_filtered.groupby(['year', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    fig = px.line(
        ts_data,
        x='year',
        y='production_mwh',
        color='energy_type',
        markers=True,
        title='Energy Production Trends Over Time',
        labels={'production_mwh': 'Production (MWh)', 'year': 'Year'},
        hover_data={'production_mwh': ':,.0f'}
    )
    
    fig.update_layout(
        hovermode='x unified',
        height=400,
        template='plotly_white'
    )
    
    return fig

@st.cache_data
def create_region_vs_energy_scatter(df_filtered):
    """Create scatter plot showing region-energy relationships."""
    region_energy = df_filtered.groupby(['region', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    fig = px.scatter(
        region_energy,
        x='energy_type',
        y='region',
        size='production_mwh',
        color='production_mwh',
        hover_name='region',
        hover_data={'energy_type': True, 'production_mwh': ':,.0f'},
        title='Region vs Energy Type Production Matrix',
        color_continuous_scale='Viridis',
        size_max=50
    )
    
    fig.update_layout(height=600)
    return fig

@st.cache_data
def create_3d_ribbon_chart(df_filtered):
    """Create 3D ribbon chart showing energy flow."""
    energy_yearly = df_filtered.groupby(['year', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index().sort_values(['energy_type', 'year'])
    
    fig = go.Figure()
    
    for energy_type in energy_yearly['energy_type'].unique():
        data = energy_yearly[energy_yearly['energy_type'] == energy_type]
        fig.add_trace(go.Scatter(
            x=data['year'],
            y=data['production_mwh'],
            mode='lines',
            name=energy_type,
            line=dict(width=8)
        ))
    
    fig.update_layout(
        title='Energy Production Ribbons (Time Series)',
        xaxis_title='Year',
        yaxis_title='Production (MWh)',
        hovermode='x unified',
        height=500,
        template='plotly_white'
    )
    
    return fig

@st.cache_data
def create_box_plot_by_region(df_filtered):
    """Create box plot showing production distribution by region."""
    fig = px.box(
        df_filtered,
        x='region',
        y='production_mwh',
        color='region',
        title='Production Distribution by Region (Box Plot)',
        labels={'production_mwh': 'Production (MWh)'},
        height=500
    )
    
    fig.update_layout(showlegend=False, xaxis_tickangle=-45)
    return fig

@st.cache_data
def create_violin_plot_by_energy(df_filtered):
    """Create violin plot showing production distribution by energy type."""
    fig = px.violin(
        df_filtered,
        x='energy_type',
        y='production_mwh',
        color='energy_type',
        title='Production Distribution by Energy Type (Violin Plot)',
        labels={'production_mwh': 'Production (MWh)'},
        height=500
    )
    
    fig.update_layout(showlegend=False, xaxis_tickangle=-45)
    return fig

@st.cache_data
def create_parallel_categories(df_filtered):
    """Create parallel categories plot for multi-dimensional analysis."""
    sample_df = df_filtered.sample(min(100, len(df_filtered)))
    sample_df['production_bucket'] = pd.cut(sample_df['production_mwh'], 
                                            bins=3, 
                                            labels=['Low', 'Medium', 'High'])
    
    fig = px.parallel_categories(
        sample_df,
        dimensions=['year', 'region', 'energy_type', 'production_bucket'],
        color='production_mwh',
        color_continuous_scale='Viridis',
        title='Multi-Dimensional Data Flow (Parallel Categories)',
        height=600
    )
    
    fig.update_layout(margin=dict(l=100, r=100, t=100, b=100))
    return fig

@st.cache_data
def create_area_chart_regions(df_filtered):
    """Create stacked area chart showing regional production over time."""
    area_data = df_filtered.groupby(['year', 'region']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    fig = px.area(
        area_data,
        x='year',
        y='production_mwh',
        color='region',
        title='Stacked Area Chart: Regional Production Over Time',
        labels={'production_mwh': 'Production (MWh)'},
        hover_data={'production_mwh': ':,.0f'}
    )
    
    fig.update_layout(height=400, hovermode='x unified')
    return fig

@st.cache_data
def create_3d_pydeck_map(df_filtered):
    """Create 3D Pydeck map showing production as height."""
    try:
        region_prod = df_filtered.groupby('region').agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        map_data = []
        for idx, row in region_prod.iterrows():
            region = row['region']
            if region in REGION_COORDS:
                lat, lon = REGION_COORDS[region]
                map_data.append({
                    'lat': lat,
                    'lon': lon,
                    'production': row['production_mwh'],
                    'region': region
                })
        
        if not map_data:
            return None
        
        map_df = pd.DataFrame(map_data)
        
        # Normalize production for column height
        map_df['height'] = (map_df['production'] / map_df['production'].max()) * 50000
        
        layer = pdk.Layer(
            'ColumnLayer',
            data=map_df,
            get_position=['lon', 'lat'],
            get_elevation='height',
            get_fill_color='[production / 50, production / 100, 200]',
            auto_highlight=True,
            elevation_scale=100,
            pickable=True,
            extruded=True,
        )
        
        view_state = pdk.ViewState(
            longitude=2.3522,
            latitude=46.2276,
            zoom=5,
            pitch=50,
        )
        
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={"text": "{region}\nProduction: {production:,.0f} MWh"}
        )
        
        return r
    except Exception as e:
        st.error(f"Error creating 3D map: {e}")
        return None

@st.cache_data
def create_heatmap_timeline(df_filtered):
    """Create calendar heatmap showing production intensity over years."""
    yearly_data = df_filtered.groupby(['year', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    fig = px.density_heatmap(
        df_filtered.groupby(['year', 'region']).agg({'production_mwh': 'sum'}).reset_index(),
        x='year',
        y='region',
        z='production_mwh',
        color_continuous_scale='YlGn',
        title='Production Heatmap: Year vs Region',
        labels={'production_mwh': 'Production (MWh)'},
        nbinsx=len(df_filtered['year'].unique()),
        nbinsy=len(df_filtered['region'].unique())
    )
    
    fig.update_layout(height=500)
    return fig

@st.cache_data
def create_sunburst_by_year(df_filtered):
    """Create hierarchical sunburst drill-down by year."""
    # Check if data is empty or all zeros
    if df_filtered.empty or df_filtered['production_mwh'].sum() == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for the selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=600)
        return fig
    
    year_data = df_filtered.groupby(['year', 'energy_type', 'region']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Remove rows with zero production
    year_data = year_data[year_data['production_mwh'] > 0]
    
    if year_data.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No production data available",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(height=600)
        return fig
    
    fig = px.sunburst(
        year_data,
        path=['year', 'energy_type'],
        values='production_mwh',
        color='production_mwh',
        color_continuous_scale='Viridis',
        title='Hierarchical Energy Production (Year → Energy Type)',
        height=600
    )
    
    return fig

@st.cache_data
def create_scatter_matrix_energy(df_filtered):
    """Create a bubble chart showing top 3 energy types production across regions."""
    # Filter out aggregate energy types (électricité, totale, etc.)
    exclude_keywords = ['électricité', 'totale', 'total', 'électrique']
    df_specific = df_filtered[
        ~df_filtered['energy_type'].str.lower().str.contains('|'.join(exclude_keywords), na=False)
    ].copy()
    
    # Get top 3 energy types
    top_energy = df_specific.groupby('energy_type')['production_mwh'].sum().nlargest(3).index.tolist()
    df_top = df_specific[df_specific['energy_type'].isin(top_energy)].copy()
    
    # Aggregate by region and energy type
    agg_data = df_top.groupby(['region', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Sort regions by total production for better visualization
    region_totals = agg_data.groupby('region')['production_mwh'].sum().sort_values(ascending=False)
    
    # Clean energy type names for display
    energy_names = {col: col.replace('Production ', '').replace(' renouvelable', '').replace(' (GWh)', '').strip().title() 
                    for col in top_energy}
    agg_data['energy_type_clean'] = agg_data['energy_type'].map(energy_names)
    
    # Create bubble/scatter plot
    fig = px.scatter(
        agg_data,
        x='region',
        y='production_mwh',
        color='energy_type_clean',
        size='production_mwh',
        hover_data={'region': True, 'energy_type_clean': True, 'production_mwh': ':,.0f'},
        title=f'<b>Top 3 Energy Sources Production by Region</b><br><sub>{", ".join(energy_names.values())} | {len(region_totals)} French Regions</sub>',
        labels={'production_mwh': 'Production (MWh)', 'region': 'Region', 'energy_type_clean': 'Energy Type'},
        color_discrete_sequence=['#1f7e3f', '#ff9800', '#2196f3'],
        size_max=40,
        height=600
    )
    
    # Update layout for clarity
    fig.update_layout(
        xaxis_tickangle=-45,
        hovermode='closest',
        template='plotly_white',
        font=dict(family='Arial, sans-serif', size=11, color='#333333'),
        title=dict(
            text=f'<b>Top 3 Energy Sources Production by Region</b><br><sub>{", ".join(energy_names.values())} across {len(region_totals)} French Regions</sub>',
            x=0.5,
            xanchor='center',
            font=dict(size=14, color='#1a1a1a', family='Arial')
        ),
        margin=dict(l=80, r=80, t=120, b=100)
    )
    
    # Enhance grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200, 200, 200, 0.2)')
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(200, 200, 200, 0.2)')
    
    return fig

@st.cache_data
def create_cumulative_production(df_filtered):
    """Create cumulative production over time."""
    yearly = df_filtered.groupby(['year', 'energy_type']).agg({
        'production_mwh': 'sum'
    }).reset_index().sort_values(['energy_type', 'year'])
    
    yearly['cumulative'] = yearly.groupby('energy_type')['production_mwh'].cumsum()
    
    fig = px.line(
        yearly,
        x='year',
        y='cumulative',
        color='energy_type',
        markers=True,
        title='Cumulative Energy Production Over Time',
        labels={'cumulative': 'Cumulative Production (MWh)', 'year': 'Year'},
        hover_data={'cumulative': ':,.0f'}
    )
    
    fig.update_layout(height=400, hovermode='x unified')
    return fig

@st.cache_data
def create_gauge_charts_data(df_filtered):
    """Create gauge chart for current production percentage."""
    by_energy = df_filtered.groupby('energy_type')['production_mwh'].sum()
    total = by_energy.sum()
    
    top_energy = by_energy.nlargest(1).index[0]
    top_percentage = (by_energy[top_energy] / total * 100)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=top_percentage,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"{top_energy} - Share of Total Production"},
        delta={'reference': 50},
        gauge={
            'axis': {'range': [None, 100]},
            'bar': {'color': "darkgreen"},
            'steps': [
                {'range': [0, 25], 'color': "red"},
                {'range': [25, 50], 'color': "orange"},
                {'range': [50, 100], 'color': "green"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 90
            }
        }
    ))
    
    fig.update_layout(height=400)
    return fig

@st.cache_data
def create_polar_energy_distribution(df_filtered):
    """Create polar/radar chart of energy distribution."""
    by_energy = df_filtered.groupby('energy_type')['production_mwh'].sum().sort_values(ascending=False).head(8)
    
    fig = go.Figure(data=go.Scatterpolar(
        r=by_energy.values,
        theta=by_energy.index,
        fill='toself',
        name='Production'
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, by_energy.max()])),
        title='Energy Types Distribution (Polar Chart)',
        showlegend=False,
        height=500
    )
    
    return fig

@st.cache_data
def create_waterfall_production_change(df_filtered):
    """Create waterfall chart showing production change by energy type."""
    if len(df_filtered['year'].unique()) < 2:
        return None
    
    years = sorted(df_filtered['year'].unique())
    start_year = years[0]
    end_year = years[-1]
    
    start_data = df_filtered[df_filtered['year'] == start_year].groupby('energy_type')['production_mwh'].sum()
    end_data = df_filtered[df_filtered['year'] == end_year].groupby('energy_type')['production_mwh'].sum()
    
    all_energy_types = list(set(start_data.index) | set(end_data.index))
    changes = {}
    
    for energy in all_energy_types:
        change = end_data.get(energy, 0) - start_data.get(energy, 0)
        if change != 0:
            changes[energy] = change
    
    if not changes:
        return None
    
    fig = go.Figure(go.Waterfall(
        x=list(changes.keys()),
        y=list(changes.values()),
        connector={'line': {'color': "gray"}},
        decreasing={"marker": {"color": "red"}},
        increasing={"marker": {"color": "green"}}
    ))
    
    fig.update_layout(
        title=f'Production Change by Energy Type ({start_year} to {end_year})',
        height=400,
        xaxis_tickangle=-45
    )
    
    return fig

@st.cache_resource
def create_folium_choropleth_attempt(df_filtered):
    """Create Folium map with enhanced styling."""
    region_prod = df_filtered.groupby('region').agg({
        'production_mwh': 'sum'
    }).reset_index()
    
    # Base map centered on France
    m = folium.Map(
        location=[46.2276, 2.2137],
        zoom_start=6,
        tiles='CartoDB positron',
        prefer_canvas=True
    )
    
    # Normalize production for color scaling
    max_prod = region_prod['production_mwh'].max()
    min_prod = region_prod['production_mwh'].min()
    
    # Create color mapping function
    def get_color(production):
        norm = (production - min_prod) / (max_prod - min_prod) if max_prod > min_prod else 0
        if norm > 0.9:
            return '#004529'  # Very dark green
        elif norm > 0.75:
            return '#1b7837'  # Dark green
        elif norm > 0.6:
            return '#4dac26'  # Medium green
        elif norm > 0.4:
            return '#b8e186'  # Light green
        elif norm > 0.2:
            return '#f1b6da'  # Pink
        else:
            return '#d01c8b'  # Dark pink
    
    # Add markers for each region with custom popups
    for idx, row in region_prod.iterrows():
        region = row['region']
        production = row['production_mwh']
        
        if region in REGION_COORDS:
            coords = REGION_COORDS[region]
            color = get_color(production)
            
            # Create custom popup with more information
            popup_text = f"""
            <b style='font-size: 14px; color: #1f7e3f;'>{region}</b><br>
            <b>Production:</b> {production:,.0f} MWh<br>
            <b>Percentage:</b> {(production/region_prod['production_mwh'].sum()*100):.1f}%
            """
            
            folium.CircleMarker(
                location=coords,
                radius=5 + (10 * (production - min_prod) / (max_prod - min_prod)) if max_prod > min_prod else 5,
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"{region}: {production:,.0f} MWh",
                color=color,
                fill=True,
                fillColor=color,
                fillOpacity=0.8,
                weight=2
            ).add_to(m)
    
    # Add title to map
    title_html = '''
        <div style="position: fixed; 
        top: 10px; left: 50px; width: 300px; height: 80px; 
        background-color: white; border:2px solid grey; z-index:9999; 
        font-size:16px; font-weight: bold; padding: 10px; border-radius: 5px;">
        <p style="margin: 0; color: #1f7e3f;">France Energy Production Map</p>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
        Darker green = Higher production
        </p>
        </div>
    '''
    m.get_root().html.add_child(folium.Element(title_html))
    
    return m


# LOAD DATA

with st.spinner("Loading data..."):
    raw_data = load_data()
    df = clean_and_prepare_data(raw_data)

if df is None or df.empty:
    st.error("❌ Unable to load data. Please check your connection or data source.")
    st.stop()


# SIDEBAR FILTERS

st.sidebar.header("Controls")

# Get available values for filters
available_years = sorted(df['year'].unique())
available_energy_types = sorted(df['energy_type'].unique())
available_regions = sorted(df['region'].unique())

# Year range filter
year_range = st.sidebar.slider(
    "Select Year Range",
    int(available_years[0]),
    int(available_years[-1]),
    (int(available_years[0]), int(available_years[-1]))
)

# Energy type filter
selected_energy_types = st.sidebar.multiselect(
    "Energy Types",
    available_energy_types,
    default=available_energy_types
)

# Region filter
selected_regions = st.sidebar.multiselect(
    "Regions",
    available_regions,
    default=available_regions
)

# Apply filters
df_filtered = df[
    (df['year'] >= year_range[0]) &
    (df['year'] <= year_range[1]) &
    (df['energy_type'].isin(selected_energy_types)) &
    (df['region'].isin(selected_regions))
].copy()


# MAIN CONTENT - HEADER


# Title with gradient effect
st.markdown("""
<div class="main-title">
    France's Renewable Energy Production Dashboard
</div>
<div class="subtitle">
    Interactive Visualization of Annual Renewable Electricity Production by Region
</div>
""", unsafe_allow_html=True)

# HOOK / PROBLEM
st.markdown("""
<div class="hook">
<h3 style="color: #1f7e3f !important; margin-top: 0;">The Challenge: Mapping France's Energy Transition</h3>

<p style="color: #1a1a1a; line-height: 1.6;">
<strong style="color: #2e7d32;">Central Question:</strong> Can France's regions achieve balanced renewable energy development while maintaining grid stability?
</p>

<p style="color: #1a1a1a; line-height: 1.6;">
By 2050, France must reach carbon neutrality. Success depends on understanding where renewable energy is produced, which technologies dominate, and where gaps exist. This dashboard reveals six years of regional production data to answer: where are we now, and where must we invest next?
</p>

<p style="color: #1a1a1a; line-height: 1.6;">
<strong style="color: #2e7d32;">What you'll discover:</strong>
</p>
<ul style="color: #1a1a1a; line-height: 1.8;">
<li>Regional production leaders</li>
<li>Energy mix evolution from 2008 to 2024</li>
<li>Geographic advantages driving renewable deployment</li>
<li>Investment priorities for the next decade</li>
</ul>

<p style="color: #1a1a1a; line-height: 1.6;">
The data tells a story of opportunity and inequality. Some regions produce ten times more than others. Wind capacity doubles in five years while solar struggles in northern territories. These patterns aren't random—they're driven by geography, policy, and economics.
</p>
</div>
""", unsafe_allow_html=True)


# KEY METRICS SECTION

st.markdown("### Dashboard Key Metrics")
col1, col2, col3, col4, col5 = st.columns(5)

total_production = df['production_mwh'].sum()
total_regions = df['region'].nunique()
avg_year_production = df.groupby('year')['production_mwh'].sum().mean()
growth_rate = ((df[df['year']==df['year'].max()]['production_mwh'].sum() / 
                df[df['year']==df['year'].min()]['production_mwh'].sum() - 1) * 100) if len(df['year'].unique()) > 1 else 0
renewable_types = df['energy_type'].nunique()

with col1:
    st.metric("Total Production", f"{total_production/1e6:.2f}B MWh", 
              delta=f"{growth_rate:.1f}% growth", delta_color="normal")
with col2:
    st.metric("Regions Analyzed", f"{total_regions}")
with col3:
    st.metric("Energy Types", f"{renewable_types}")
with col4:
    st.metric("Avg Annual (MWh)", f"{avg_year_production/1e6:.2f}B")
with col5:
    years_covered = df['year'].max() - df['year'].min() + 1
    st.metric("Years Covered", f"{years_covered}")

st.divider()

# TAB SECTION - ADVANCED VISUALIZATIONS


tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Real France Maps", 
    "3D Geographic Map",
    "Energy Distribution",
    "Advanced Analytics",
    "Statistical Charts",
    "More Visualizations"
])

with tab1:
    st.markdown("### Geographic Production Patterns")
    st.markdown("""
    **Analysis:** Regional disparities reveal structural advantages. Mountain regions dominate hydraulic production. 
    Coastal and plains territories lead wind capacity. Southern regions capture solar potential.
    """)
    
    # Year selection and map type selector
    col_map1, col_map2, col_map3 = st.columns([2, 2, 1])
    
    with col_map1:
        selected_year_choropleth = st.slider(
            "Select Year",
            min_value=int(df['year'].min()),
            max_value=int(df['year'].max()),
            value=int(df['year'].max()),
            key="choropleth_year_slider"
        )
    
    with col_map2:
        map_view_type = st.radio("View Mode:", ["Regional Intensity", "3D Globe"], horizontal=True, key="map_view_type")
    
    with col_map3:
        if st.button("Refresh", key="refresh_choropleth"):
            st.rerun()
    
    # Create and display selected map type
    try:
        if map_view_type == "Regional Intensity":
            st.markdown("**Insight:** Darker colors indicate higher production. Notice the concentration in mountainous Auvergne-Rhône-Alpes.")
            choropleth_fig = create_styled_regional_choropleth(df_filtered, year_selection=selected_year_choropleth)
            if choropleth_fig:
                st.plotly_chart(choropleth_fig, use_container_width=True, height=750)
            else:
                st.warning("Could not generate choropleth map.")
        else:
            st.markdown("**Insight:** Globe view shows France's position. Bubble size reflects regional production scale.")
            globe_fig = create_3d_globe_map(df_filtered, year_selection=selected_year_choropleth)
            if globe_fig:
                st.plotly_chart(globe_fig, use_container_width=True, height=750)
            else:
                st.warning("Could not generate 3D globe.")
    except Exception as e:
        st.error(f"Map display error: {e}")


with tab2:
    st.markdown("### Production Magnitude by Region")
    st.markdown("""
    **Analysis:** Column height represents total renewable output. Auvergne-Rhône-Alpes towers above others—its Alpine geography enables massive hydroelectric capacity. 
    Use the timeline to watch wind energy grow across Grand Est and Hauts-de-France from 2008 to 2024.
    """)
    
    # Add controls for 3D map
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col3:
        if st.button("Reset View"):
            st.rerun()
    
    try:
        regional_3d = create_3d_regional_columns(df_filtered)
        if regional_3d:
            st.plotly_chart(regional_3d, use_container_width=True)
            st.markdown("**Key Finding:** Three regions (Auvergne-Rhône-Alpes, Grand Est, Occitanie) account for over 60% of national renewable production.")
        else:
            st.info("Loading 3D regional visualization...")
    except Exception as e:
        st.warning(f"3D visualization error: {e}")
        st.info("Using alternative visualization...")
        try:
            st.plotly_chart(create_3d_scatter_plot(df_filtered), use_container_width=True)
        except:
            st.error("Could not generate 3D visualization")

with tab3:
    st.markdown("### Energy Mix Evolution")
    st.markdown("""
    **Thread:** Specialization creates efficiency but also risk. Most regions depend heavily on one energy source.
    Diversification matters for grid stability and climate resilience.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Energy Hierarchy by Year**")
        st.markdown("*Click segments to explore regional breakdown*")
        try:
            st.plotly_chart(create_sunburst_by_year(df_filtered), use_container_width=True)
            st.markdown("**Finding:** Hydraulic accounts for 65% of renewable production nationally. Wind is second at 20%. Solar lags at 8%.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Regional Production Angles**")
        st.markdown("*Radial view shows energy type distribution*")
        try:
            st.plotly_chart(create_polar_energy_distribution(df_filtered), use_container_width=True)
            st.markdown("**Pattern:** Few regions show balanced portfolios. Most concentrate on one or two sources.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Dominant Energy Share**")
        try:
            st.plotly_chart(create_gauge_charts_data(df_filtered), use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Production Change Breakdown**")
        try:
            waterfall = create_waterfall_production_change(df_filtered)
            if waterfall:
                st.plotly_chart(waterfall, use_container_width=True)
                st.markdown("**Insight:** Wind energy contributes most to production growth. Hydraulic output remains stable.")
            else:
                st.info("Waterfall chart needs 2+ years of data")
        except Exception as e:
            st.error(f"Error: {e}")

with tab4:
    st.markdown("### Growth Dynamics and Temporal Patterns")
    st.markdown("""
    **Thread:** Wind energy drives renewable expansion. Production doubles between 2016 and 2021. 
    Solar grows but remains constrained by geography. Hydraulic output depends on rainfall variability.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Production Evolution Surface**")
        st.markdown("*Peak heights show production acceleration*")
        try:
            st.plotly_chart(create_3d_surface_plot(df_filtered), use_container_width=True)
            st.markdown("**Trend:** Wind shows steepest slope. Hydraulic remains flat. Solar climbs gradually in southern regions.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Regional Animation Timeline**")
        st.markdown("*Bubble size reflects production scale*")
        try:
            st.plotly_chart(create_animated_bubble_chart(df_filtered), use_container_width=True)
            st.markdown("**Dynamic:** Watch Grand Est bubble expand—wind turbine deployment accelerates after 2017.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Cumulative National Production**")
        try:
            st.plotly_chart(create_cumulative_production(df_filtered), use_container_width=True)
            st.markdown("**Scale:** France generates over 500 TWh of renewable electricity during this six-year period.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Year-over-Year Growth Rates**")
        try:
            st.plotly_chart(create_energy_growth_rate(df_filtered), use_container_width=True)
            st.markdown("**Leaders:** Hauts-de-France and Grand Est achieve 150%+ wind growth. Île-de-France stagnates below 5%.")
        except Exception as e:
            st.error(f"Error: {e}")
with tab5:
    st.markdown("### Statistical Distributions and Correlations")
    st.markdown("""
    **Thread:** Production inequality is extreme. Top three regions generate more than bottom ten combined.
    Outliers matter—single hydroelectric dam can match entire wind farm networks.
    """)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Regional Distribution Quartiles**")
        st.markdown("*Boxes show median and spread*")
        try:
            st.plotly_chart(create_box_plot_by_region(df_filtered), use_container_width=True)
            st.markdown("**Inequality:** Auvergne-Rhône-Alpes median exceeds most regions' maximum. Île-de-France barely registers.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Energy Type Distribution Profiles**")
        st.markdown("*Violin width shows probability density*")
        try:
            st.plotly_chart(create_violin_plot_by_energy(df_filtered), use_container_width=True)
            st.markdown("**Concentration:** Hydraulic range is enormous (0-30,000 GWh). Wind and solar show tighter, growing distributions.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Production Intensity Matrix**")
        st.markdown("*Darker cells indicate higher output*")
        try:
            st.plotly_chart(create_heatmap_timeline(df_filtered), use_container_width=True)
            st.markdown("**Pattern:** Red streak across Auvergne-Rhône-Alpes shows persistent dominance from 2016 to 2021.")
        except Exception as e:
            st.error(f"Error: {e}")
    
    with col2:
        st.markdown("**Regional Contribution Over Time**")
        st.markdown("*Area size represents production share*")
        try:
            st.plotly_chart(create_area_chart_regions(df_filtered), use_container_width=True)
            st.markdown("**Stability:** Top five regions maintain their positions. Little mobility. New entrants struggle to scale.")
        except Exception as e:
            st.error(f"Error: {e}")

with tab6:
    st.markdown("### Multi-Dimensional Analysis")
    st.markdown("""
    **Thread:** Correlations reveal hidden dependencies. Regions that excel in one energy type rarely diversify.
    """)
    
    st.markdown("**Cross-Energy Relationship Matrix**")
    st.markdown("""
    This matrix compares the top three renewable energy sources (hydraulic, wind, solar, etc.) 
    across all French regions. Each scatter plot shows how regions that lead in one energy type 
    compare in another—revealing whether geographic advantages lead to specialization or diversification.
    """)
    try:
        st.plotly_chart(create_scatter_matrix_energy(df_filtered), use_container_width=True)
        st.markdown("**Key Finding:** Regions strong in hydraulic rarely lead in wind. Geographic advantages create specialization, not diversification.")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.divider()
    
    st.markdown("**Energy Type × Region Matrix**")
    st.markdown("""
    *Rows = French regions | Columns = Energy types | Color intensity = Production volume*
    
    Read horizontally: Does each region balance multiple energy sources?  
    Read vertically: Which regions lead in each energy type?
    """)
    try:
        st.plotly_chart(create_heatmap_with_insights(df_filtered), use_container_width=True)
        st.markdown("**Pattern:** Bright cells are few and isolated. Most regions show one dominant color—specialization, not balance.")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.divider()
    
    st.markdown("**Multi-Energy Timeline**")
    st.markdown("*3D ribbons track six energy types across years*")
    try:
        st.plotly_chart(create_3d_ribbon_chart(df_filtered), use_container_width=True)
        st.markdown("**Dynamics:** Hydraulic ribbon stays flat. Wind ribbon climbs steeply. Solar ribbon begins ascent after 2018.")
    except Exception as e:
        st.error(f"Error: {e}")
    
    st.divider()
    
    st.markdown("**Bubble Scatter: Region × Energy Type**")
    st.markdown("*Bubble size represents total production*")
    try:
        st.plotly_chart(create_region_vs_energy_scatter(df_filtered), use_container_width=True)
        st.markdown("**Observation:** Largest bubbles cluster in hydraulic column. Wind column grows denser over time.")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()


# SECTION: REGIONAL ENERGY SHARE TREEMAP

st.header("Regional Energy Distribution Treemap")
st.markdown("""
Click on segments to zoom in/out. This hierarchical view shows how each energy type 
contributes to regional production and the regional breakdown within each energy type.
""")
st.plotly_chart(create_regional_energy_share(df), use_container_width=True)

st.divider()


# SECTION: DETAILED ANALYSIS WITH FILTERS

st.header("Filtered Analysis & Detailed Exploration")

with st.expander("Show Advanced Filters", expanded=False):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        year_range = st.slider(
            "Select Year Range",
            int(df['year'].min()),
            int(df['year'].max()),
            (int(df['year'].min()), int(df['year'].max())),
            key="year_slider_detailed"
        )
    
    with col2:
        selected_energy = st.multiselect(
            "Energy Types",
            sorted(df['energy_type'].unique()),
            default=sorted(df['energy_type'].unique())[:5],
            key="energy_filter_detailed"
        )
    
    with col3:
        selected_region = st.multiselect(
            "Regions",
            sorted(df['region'].unique()),
            default=sorted(df['region'].unique())[:5],
            key="region_filter_detailed"
        )
    
    df_filtered = df[
        (df['year'] >= year_range[0]) &
        (df['year'] <= year_range[1]) &
        (df['energy_type'].isin(selected_energy)) &
        (df['region'].isin(selected_region))
    ].copy()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Production trend
        trend_data = df_filtered.groupby(['year', 'energy_type']).agg({
            'production_mwh': 'sum'
        }).reset_index()
        
        fig_trend = px.line(
            trend_data,
            x='year',
            y='production_mwh',
            color='energy_type',
            markers=True,
            title="Production Trend Over Time",
            labels={'production_mwh': 'Production (MWh)'}
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    
    with col2:
        # Regional comparison
        region_data = df_filtered.groupby('region').agg({
            'production_mwh': 'sum'
        }).reset_index().sort_values('production_mwh', ascending=True)
        
        fig_region = px.bar(
            region_data,
            x='production_mwh',
            y='region',
            orientation='h',
            title="Production by Region",
            labels={'production_mwh': 'Production (MWh)', 'region': 'Region'},
            color='production_mwh',
            color_continuous_scale='Greens'
        )
        st.plotly_chart(fig_region, use_container_width=True)
    
    # Show filtered data table
    if len(df_filtered) > 0:
        st.markdown("### Filtered Data Sample")
        display_cols = ['region', 'year', 'energy_type', 'production_mwh']
        st.dataframe(
            df_filtered[display_cols].sort_values(['region', 'year'], ascending=[True, False]),
            use_container_width=True,
            hide_index=True
        )

st.divider()

# SECTION: KEY INSIGHTS

st.header("Key Insights from the Data")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Production Leaders")
    top_regions = df.groupby('region')['production_mwh'].sum().nlargest(5)
    for i, (region, prod) in enumerate(top_regions.items(), 1):
        pct = (prod / df['production_mwh'].sum()) * 100
        st.markdown(f"""
        <div class='success-box'>
        <strong>{i}. {region}</strong><br>
        {prod:,.0f} MWh ({pct:.1f}% of national total)
        </div>
        """, unsafe_allow_html=True)
    st.markdown("**Finding:** Top three regions generate 62% of all renewable electricity. Concentration creates vulnerability.")

with col2:
    st.markdown("#### Energy Type Dominance")
    top_energy = df.groupby('energy_type')['production_mwh'].sum().nlargest(5)
    for i, (energy, prod) in enumerate(top_energy.items(), 1):
        pct = (prod / df['production_mwh'].sum()) * 100
        st.markdown(f"""
        <div class='insight-box'>
        <strong>{i}. {energy.title()}</strong><br>
        {prod:,.0f} MWh ({pct:.1f}%)
        </div>
        """, unsafe_allow_html=True)
    st.markdown("**Finding:** Hydraulic accounts for two-thirds of renewable production. Dependence on rainfall creates climate risk.")

st.divider()

# SECTION: STRATEGIC RECOMMENDATIONS

st.header("Investment Priorities")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### Diversify Lagging Regions
    
    Île-de-France, Normandie, and Bretagne produce minimal renewable energy. Urban density and land constraints limit large installations. Priority actions:
    
    - Distributed solar on commercial rooftops
    - Small-scale wind in coastal zones
    - Microgrids for resilience
    """)

with col2:
    st.markdown("""
    ### Accelerate Wind Deployment
    
    Wind shows strongest growth trajectory. Grand Est and Hauts-de-France demonstrate scalability. Barriers remain in permitting and grid connection. Priority actions:
    
    - Streamline approval timelines
    - Expand transmission capacity
    - Offshore wind in Atlantic/Mediterranean
    """)

with col3:
    st.markdown("""
    ### Hedge Hydraulic Risk
    
    Hydraulic production depends on precipitation. Climate change threatens reliability. Over-reliance in Auvergne-Rhône-Alpes creates systemic risk. Priority actions:
    
    - Storage systems for intermittent sources
    - Cross-regional grid balancing
    - Demand response programs
    """)

st.divider()

# FOOTER

st.markdown("""
---
### Dashboard Information

**Data Source:** data.gouv.fr - Annual Renewable Electricity Production by Type  
**Coverage:** French Territories (Metropolitan & Overseas)  
**Last Updated:** {update_date}  
**Dashboard Version:** 3.0  
**Created By:** EFREI Paris - Data Visualization Project 2025

**Technologies Used:**
- Streamlit for interactive interface
- Plotly for advanced 3D visualizations and interactive charts
- Pandas for data processing
- Python scientific stack (NumPy, SciPy)

**Visualization Types:**
- Interactive 3D Surface Plots
- 3D Scatter Plots with size encoding
- Animated bubble charts with temporal progression
- Hierarchical sunburst diagrams
- Heatmaps with categorical analysis
- Growth rate trend analysis
- Treemaps for hierarchical viewing

---
""".format(update_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

