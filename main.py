
import pandas as pd
import streamlit as st
import plotly.express as px
from io import BytesIO
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap
import openrouteservice

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Data-Logger | SUR Division",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== CUSTOM CSS ======================
st.markdown("""
<style>
    .dashboard-title {
        font-size: 2.85rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF9933, #003087);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        font-size: 1.4rem;
        color: #003087;
        text-align: center;
        font-weight: 500;
        margin-top: -0.4rem;
    }

    .section-header {
        font-size: 1.6rem;
        font-weight: 600;
        color: #003087;
        margin: 1.2rem 0 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ====================== CONFIG ======================
IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/testing/main/Central%20Railway%20Logo.png"

SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
USERS = st.secrets["users"]

# ====================== STATION COORDINATES ======================
station_coords = {
    "SUR": {"lat": 17.66461685325021, "lon": 75.8934378261056},
    "BALE": {"lat": 17.67603540641838, "lon": 75.84576721149409},
    "PK": {"lat": 17.725604941699864, "lon": 75.77920258081592},
    "MVE": {"lat": 17.742039265808994, "lon": 75.70628187232433},
    "MO": {"lat": 17.805775747199327, "lon": 75.67562640965197},
    "MKPT": {"lat": 17.876348021475454, "lon": 75.63508125440458},
    "AAG": {"lat": 17.928577532396076, "lon": 75.60830992499343},
    "WKA": {"lat": 17.98027395125776, "lon": 75.58849669615935},
    "MA": {"lat": 18.030290184953223, "lon": 75.54656926732524},
    "WDS": {"lat": 18.06648098233323, "lon": 75.4889207249956},
    "KWV": {"lat": 18.09222393527959, "lon": 75.41722014404814},
    "DHS": {"lat": 18.12955847910344, "lon": 75.33424703664774},
    "KEM": {"lat": 18.176853463202423, "lon": 75.27468572499728},
    "BLNI": {"lat": 18.210581627334815, "lon": 75.20717558551391},
    "JEUR": {"lat": 18.260861679574607, "lon": 75.16233780965912},
    "PPJ": {"lat": 18.291563656218496, "lon": 75.09802889616424},
    "WSB": {"lat": 18.280298357551207, "lon": 75.01623199616414},
    "KEU": {"lat": 18.290095464926527, "lon": 74.95250352348742},
    "JNTR": {"lat": 18.324947721792178, "lon": 74.8776102384951},
    "BGVN": {"lat": 18.316891480050153, "lon": 74.77494537837337},
    "MLM": {"lat": 18.368948833491366, "lon": 74.72444118537874},
    "BRB": {"lat": 18.407915112523582, "lon": 74.6490078310967},
    "DD": {"lat": 18.46377428753149, "lon": 74.57928783698621},
}

# ====================== ROAD ROUTE FUNCTION ======================
def get_road_route(start_coords, end_coords):

    try:

        client = openrouteservice.Client(
            key=st.secrets["ORS_API_KEY"]
        )

        coords = [
            [start_coords[1], start_coords[0]],
            [end_coords[1], end_coords[0]]
        ]

        route = client.directions(
            coordinates=coords,
            profile='driving-car',
            format='geojson'
        )

        geometry = route['features'][0]['geometry']['coordinates']

        decoded_route = [
            [coord[1], coord[0]]
            for coord in geometry
        ]

        summary = route['features'][0]['properties']['summary']

        distance_km = summary['distance'] / 1000
        duration_min = summary['duration'] / 60

        return decoded_route, distance_km, duration_min

    except Exception as e:

        st.error(f"Road Route Error: {e}")

        return None, None, None

# ====================== LOGIN ======================
def login_page():

    col1, col2, col3 = st.columns([3, 3, 3])

    with col2:

        st.subheader("🔐 Secure Login")

        with st.form("login_form", clear_on_submit=False):

            email = st.text_input(
                "Username / Email",
                placeholder="Enter your ID"
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter Password"
            )

            if st.form_submit_button(
                "Login",
                type="primary",
                use_container_width=True
            ):

                if email in USERS and password == USERS[email].get("password"):

                    st.session_state.logged_in = True
                    st.session_state.user_name = USERS[email].get("name")

                    st.success(
                        f"Welcome, {st.session_state.user_name}!"
                    )

                    st.rerun()

                else:
                    st.error("Invalid credentials!")

# ====================== LOAD DATA ======================
@st.cache_data(ttl=300)
def load_data_from_gsheet():

    try:

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"],
            scope
        )

        client = gspread.authorize(credentials)

        sheet = client.open_by_key(
            SHEET_ID
        ).worksheet(SHEET_NAME)

        df = pd.DataFrame(sheet.get_all_records())

        if df.empty:
            st.error("Google Sheet is empty!")
            st.stop()

        df.columns = df.columns.str.strip()

        if 'FCOUNT' in df.columns:
            df['FCOUNT'] = pd.to_numeric(
                df['FCOUNT'],
                errors='coerce'
            ).fillna(0).astype(int)

        if 'Date' in df.columns:

            df['Date'] = pd.to_datetime(
                df['Date'],
                errors='coerce'
            )

            df['Month'] = df['Date'].dt.strftime('%B')

        return df

    except Exception as e:

        st.error(f"Failed to load data: {e}")
        st.stop()

# ====================== REFRESH ======================
def refresh_data():

    st.cache_data.clear()

    st.success(
        "✅ Data refreshed successfully!"
    )

    st.rerun()

# ====================== SESSION ======================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ====================== LOGIN PAGE ======================
if not st.session_state.logged_in:

    login_page()

# ====================== MAIN APP ======================
else:

    # ====================== HEADER ======================
    col1, col2, col3 = st.columns([3, 3, 1])

    with col2:
        st.image(IR_LOGO_URL, width=220)

    st.markdown(
        '<h1 class="dashboard-title">DATA LOGGER EXCEPTIONAL REPORT</h1>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<p class="subtitle">Central Railway • Solapur Division • Safety Branch</p>',
        unsafe_allow_html=True
    )

    st.caption(
        f"**Logged in as:** {st.session_state.user_name}"
    )

    st.divider()

    # ====================== SIDEBAR ======================
    with st.sidebar:

        st.header("🔧 Controls")

        if st.button(
            "🔄 Refresh Data",
            type="primary",
            use_container_width=True
        ):
            refresh_data()

    # ====================== LOAD DATA ======================
    df_original = load_data_from_gsheet()

    # ====================== FILTERS ======================
    st.markdown("### 🔍 Live Filters")

    col_f1 = st.columns(4)

    with col_f1[0]:

        stations = sorted(
            df_original['STATION'].dropna().unique().tolist()
        )

        selected_stations = st.multiselect(
            "STATION",
            stations
        )

    with col_f1[1]:

        errors = sorted(
            df_original['Error'].dropna().unique().tolist()
        ) if 'Error' in df_original.columns else []

        selected_errors = st.multiselect(
            "Error",
            errors
        )

    with col_f1[2]:

        categories = sorted(
            df_original['Category'].dropna().unique().tolist()
        ) if 'Category' in df_original.columns else []

        selected_categories = st.multiselect(
            "Category",
            categories
        )

    with col_f1[3]:

        months = sorted(
            df_original['Month'].dropna().unique().tolist()
        ) if 'Month' in df_original.columns else []

        selected_months = st.multiselect(
            "Month",
            months
        )

    # ====================== DATE FILTER ======================
    col_date = st.columns(2)

    with col_date[0]:

        from_date = st.date_input(
            "From Date",
            value=df_original['Date'].min().date()
        )

    with col_date[1]:

        to_date = st.date_input(
            "To Date",
            value=df_original['Date'].max().date()
        )

    # ====================== APPLY FILTERS ======================
    filtered_df = df_original.copy()

    filtered_df = filtered_df[
        (filtered_df['Date'].dt.date >= from_date) &
        (filtered_df['Date'].dt.date <= to_date)
    ]

    if selected_stations:
        filtered_df = filtered_df[
            filtered_df['STATION'].isin(selected_stations)
        ]

    if selected_errors:
        filtered_df = filtered_df[
            filtered_df['Error'].isin(selected_errors)
        ]

    if selected_categories:
        filtered_df = filtered_df[
            filtered_df['Category'].isin(selected_categories)
        ]

    if selected_months:
        filtered_df = filtered_df[
            filtered_df['Month'].isin(selected_months)
        ]

    st.divider()

    # ====================== TABS ======================
    tab_overview, tab_map = st.tabs([
        "📊 Overview Dashboard",
        "🗺️ Map View"
    ])

    # ====================== OVERVIEW ======================
    with tab_overview:

        st.subheader("📊 Overview Dashboard")

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.metric(
                "Total Records",
                f"{len(filtered_df):,}"
            )

        with c2:
            st.metric(
                "Total FCOUNT",
                f"{filtered_df['FCOUNT'].sum():,}"
            )

        with c3:

            if not filtered_df.empty:

                top_row = filtered_df.loc[
                    filtered_df['FCOUNT'].idxmax()
                ]

                st.metric(
                    "Top Station",
                    top_row['STATION'],
                    f"{top_row['FCOUNT']:,}"
                )

        with c4:
            st.metric(
                "Max FCOUNT",
                f"{filtered_df['FCOUNT'].max():,}"
            )

    # ====================== MAP VIEW ======================
    with tab_map:

        st.subheader(
            "🗺️ Interactive Map View"
        )

        # ====================== MAP TYPE ======================
        map_type = st.radio(
            "🛰️ Select Map Mode",
            ["Normal", "Satellite"],
            horizontal=True
        )

        # ====================== MAP ======================
        if map_type == "Satellite":

            m = folium.Map(
                location=[17.85, 75.80],
                zoom_start=7,
                tiles=None
            )

            folium.TileLayer(
                tiles='https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google',
                name='Google Satellite',
                max_zoom=20,
                subdomains=['mt0', 'mt1', 'mt2', 'mt3']
            ).add_to(m)

        else:

            m = folium.Map(
                location=[17.85, 75.80],
                zoom_start=7,
                tiles="CartoDB positron"
            )

        MiniMap(toggle_display=True).add_to(m)

        # ====================== MAP MARKERS ======================
        if not filtered_df.empty:

            map_agg = filtered_df.groupby(
                'STATION'
            )['FCOUNT'].sum().reset_index()

            map_data = []

            for _, row in map_agg.iterrows():

                station_name = str(
                    row['STATION']
                ).strip().upper()

                if station_name in station_coords:

                    map_data.append({
                        'STATION': row['STATION'],
                        'FCOUNT': row['FCOUNT'],
                        'lat': station_coords[station_name]['lat'],
                        'lon': station_coords[station_name]['lon']
                    })

            map_df = pd.DataFrame(map_data)

            max_f = map_df['FCOUNT'].max() or 1

            for _, row in map_df.iterrows():

                intensity = row['FCOUNT'] / max_f

                color = (
                    "darkred"
                    if intensity > 0.7
                    else "red"
                    if intensity > 0.4
                    else "orange"
                )

                folium.CircleMarker(
                    location=[row['lat'], row['lon']],
                    radius=12 + intensity * 18,
                    popup=f"""
                    <h4>{row['STATION']}</h4>
                    <b>FCOUNT:</b> {int(row['FCOUNT']):,}
                    """,
                    tooltip=f"{row['STATION']} ({int(row['FCOUNT']):,})",
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.85
                ).add_to(m)

            folium.LayerControl().add_to(m)

            # ====================== INITIAL MAP RENDER ======================
            map_return = st_folium(
                m,
                width=1200,
                height=700,
                key="folium_key"
            )

            # ====================== CLICK EVENT ======================
            if map_return and map_return.get("last_object_clicked"):

                lat = map_return["last_object_clicked"]["lat"]
                lon = map_return["last_object_clicked"]["lng"]

                map_df['dist'] = (
                    (map_df['lat'] - lat) ** 2 +
                    (map_df['lon'] - lon) ** 2
                ) ** 0.5

                selected_station = map_df.loc[
                    map_df['dist'].idxmin(),
                    'STATION'
                ]

                st.success(
                    f"✅ Station Selected: {selected_station}"
                )

                filtered_df = filtered_df[
                    filtered_df['STATION'] == selected_station
                ]

                # ====================== ROAD CONNECTIVITY ======================
                selected_station_upper = str(
                    selected_station
                ).strip().upper()

                if selected_station_upper in station_coords:

                    sur_coords = (
                        station_coords["SUR"]["lat"],
                        station_coords["SUR"]["lon"]
                    )

                    destination_coords = (
                        station_coords[selected_station_upper]["lat"],
                        station_coords[selected_station_upper]["lon"]
                    )

                    road_route, distance_km, duration_min = get_road_route(
                        sur_coords,
                        destination_coords
                    )

                    if road_route:

                        folium.PolyLine(
                            locations=road_route,
                            color="blue",
                            weight=6,
                            opacity=0.85,
                            tooltip=f"SUR → {selected_station}"
                        ).add_to(m)

                        m.fit_bounds(road_route)

                        st.success(
                            f"""
🚗 ROAD CONNECTIVITY

FROM: SUR (Solapur)

TO: {selected_station}

📏 Distance: {distance_km:.1f} KM

⏱️ Approx Time: {duration_min:.0f} Minutes
                            """
                        )

                        # Re-render map with route
                        st_folium(
                            m,
                            width=1200,
                            height=700,
                            key="route_map"
                        )

        # ====================== DETAILED RECORDS ======================
        st.markdown("---")

        st.subheader("Detailed Records")

        if filtered_df.empty:

            st.warning("No records found.")

        else:

            display_df = filtered_df.copy()

            if 'Date' in display_df.columns:
                display_df['Date'] = display_df['Date'].dt.date

            st.dataframe(
                display_df.style.format({
                    "FCOUNT": "{:,}"
                }),
                use_container_width=True,
                hide_index=True
            )

            # ====================== DOWNLOAD ======================
            st.markdown("---")

            output = BytesIO()

            with pd.ExcelWriter(
                output,
                engine='xlsxwriter'
            ) as writer:

                display_df.to_excel(
                    writer,
                    index=False,
                    sheet_name='Filtered_Records'
                )

                station_summary = filtered_df.groupby(
                    'STATION'
                )['FCOUNT'].agg(
                    Total_FCOUNT='sum',
                    Record_Count='count'
                ).reset_index()

                station_summary.to_excel(
                    writer,
                    index=False,
                    sheet_name='Station_Summary'
                )

            output.seek(0)

            st.download_button(
                label="⬇️ Download Professional Excel Report",
                data=output.getvalue(),
                file_name=f"Datalogger_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True
            )

    st.caption(
        "🚄 Safety Branch | Central Railway, Solapur Division"
    )
