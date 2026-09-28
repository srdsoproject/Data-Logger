
import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import gspread
import folium
from streamlit_folium import st_folium
from folium.plugins import Fullscreen

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except Exception:
    STATSMODELS_AVAILABLE = False

logger = logging.getLogger("data_logger")

# ====================== PAGE CONFIG ======================
st.set_page_config(
    page_title="Data-Logger | SUR Division",
    page_icon="🚄",
    layout="wide",
    initial_sidebar_state="expanded"
)


def _st_version():
    try:
        return tuple(int(p) for p in st.__version__.split(".")[:2])
    except Exception:
        return (1, 0)


# `use_container_width` is deprecated/removed in newer Streamlit; `width="stretch"` replaces it.
STRETCH = {"width": "stretch"} if _st_version() >= (1, 50) else {"use_container_width": True}

# ====================== PATHS / CONSTANTS ======================
BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
CACHE_DIR = BASE_DIR / ".offline_cache"
SNAPSHOT_FILE = CACHE_DIR / "snapshot.parquet"
META_FILE = CACHE_DIR / "snapshot_meta.json"

IR_LOGO_URL = "https://raw.githubusercontent.com/srdsoproject/testing/main/Central%20Railway%20Logo.png"
IST = "Asia/Kolkata"
CACHE_TTL_SECONDS = 600
REFRESH_COOLDOWN_SECONDS = 30
ONLINE_RETRY_SECONDS = 60
SESSION_TIMEOUT_SECONDS = 60 * 60
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCK_SECONDS = 60
MAX_DISPLAY_ROWS = 10000
REQUIRED_COLUMNS = ["DATE", "STATION"]
EXPECTED_COLUMNS = ["DATE", "STATION", "DEPARTMENT", "ERROR MAIN CATEGORY", "DL FAULT MESSAGE", "REMARKS GIVEN BY S&T"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# ====================== CUSTOM CSS ======================
CUSTOM_CSS = """
<style>
__FONT_SOURCE__

.stApp {
    background: linear-gradient(135deg, #e0f7fa 0%, #b3e5fc 40%, #e1f5fe 100%);
    color: #0d1b2a;
    font-family: 'Rajdhani', sans-serif;
}

.brand-line {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.5rem;
    color: #01579b;
    text-align: center;
    font-weight: 700;
    letter-spacing: 2.5px;
    margin: 0.6rem 0 0.2rem 0;
}

.train-emoji-container {
    text-align: center;
    margin: 8px 0 14px 0;
    overflow: hidden;
    height: 42px;
    position: relative;
    width: 100%;
}

.train-track {
    display: inline-block;
    white-space: nowrap;
    animation: moveTrainLine 12s linear infinite;
    font-size: 1.9rem;
    letter-spacing: 16px;
}

@keyframes moveTrainLine {
    0%   { transform: translateX(100vw); }
    100% { transform: translateX(-100%); }
}

@media (prefers-reduced-motion: reduce) {
    .train-track { animation: none; }
}

.section-header {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    color: #0277bd !important;
    margin: 1.4rem 0 0.6rem 0;
    border-left: 5px solid #0288d1;
    padding-left: 12px;
}

div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #ffffff, #e1f5fe);
    border: 1px solid #81d4fa;
    border-radius: 16px;
    padding: 18px 12px;
    box-shadow: 0 6px 18px rgba(2, 119, 189, 0.12);
    transition: all 0.3s ease;
}

div[data-testid="stMetric"]:hover {
    transform: translateY(-4px);
    border-color: #0288d1;
    box-shadow: 0 10px 25px rgba(2, 119, 189, 0.22);
}

div[data-testid="stMetric"] label {
    color: #0277bd !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
}

div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    color: #01579b !important;
    font-family: 'Orbitron', sans-serif !important;
    font-size: 1.8rem !important;
}

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: transparent;
}

.stTabs [data-baseweb="tab"] {
    background: #e1f5fe;
    border-radius: 12px 12px 0 0;
    color: #01579b;
    font-family: 'Rajdhani', sans-serif;
    font-weight: 700;
    font-size: 1.1rem;
    border: 1px solid #81d4fa;
    padding: 10px 22px;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg, #0288d1, #0277bd) !important;
    color: #ffffff !important;
    border-color: #0277bd !important;
    box-shadow: 0 0 15px rgba(2, 136, 209, 0.35);
}

.stButton > button {
    background: linear-gradient(90deg, #0288d1, #0277bd) !important;
    color: #ffffff !important;
    font-family: 'Orbitron', sans-serif !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.4rem !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 12px rgba(2, 136, 209, 0.3);
}

.stButton > button:hover {
    transform: scale(1.04);
    box-shadow: 0 6px 20px rgba(2, 136, 209, 0.45) !important;
}

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #e0f7fa 0%, #b3e5fc 100%);
    border-right: 1px solid #81d4fa;
}

section[data-testid="stSidebar"] .stMarkdown h2 {
    color: #01579b !important;
    font-family: 'Orbitron', sans-serif;
}

.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #81d4fa;
}

.watermark {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    opacity: 0.07;
    z-index: 0;
    pointer-events: none;
    width: 520px;
    max-width: 70vw;
}

.watermark img {
    width: 100%;
    height: auto;
}

::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}
::-webkit-scrollbar-track {
    background: #e0f7fa;
}
::-webkit-scrollbar-thumb {
    background: #0288d1;
    border-radius: 10px;
}
::-webkit-scrollbar-thumb:hover {
    background: #01579b;
}

.stCaption, .stMarkdown p {
    color: #37474f !important;
}

/* ===== DRISHTI Header Styles ===== */
.drishti-title {
    font-family: 'Orbitron', sans-serif !important;
    font-size: 3.8rem !important;
    font-weight: 900 !important;
    letter-spacing: 14px !important;
    background: linear-gradient(90deg, #01579b, #0277bd, #0288d1);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin: 0.8rem 0 0.3rem 0;
}

.drishti-fullform {
    font-family: 'Rajdhani', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
    color: #37474f;
    text-align: center;
    letter-spacing: 0.5px;
    margin-bottom: 0.8rem;
}

.drishti-fullform b {
    color: #01579b;
    font-weight: 800;
}

.drishti-line {
    width: 180px;
    height: 3px;
    margin: 0 auto 1rem auto;
    background: linear-gradient(90deg, transparent, #0288d1, #ffc107, #0288d1, transparent);
    border-radius: 10px;
}

/* ===== Offline status pills (new) ===== */
.status-pill { display: inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 700; font-size: 0.9rem; }
.status-live { background: #e8f5e9; color: #1b5e20; border: 1px solid #81c784; }
.status-off  { background: #fff3e0; color: #e65100; border: 1px solid #ffb74d; }
</style>
"""


def _font_source():
    """Uses local fonts from ./assets when present (works offline); otherwise falls back to Google Fonts."""
    faces, need_import = "", False
    for family, fname in [("Orbitron", "Orbitron.woff2"), ("Rajdhani", "Rajdhani.woff2")]:
        p = ASSETS_DIR / fname
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            faces += ("@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2');"
                      "font-weight:100 900;font-display:swap;}\n" % (family, b64))
        else:
            need_import = True
    imp = ("@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900"
           "&family=Rajdhani:wght@500;600;700&display=swap');\n") if need_import else ""
    return imp + faces  # @import must come first


st.markdown(CUSTOM_CSS.replace("__FONT_SOURCE__", _font_source()), unsafe_allow_html=True)

# ====================== CONFIG ======================
try:
    SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
    SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
    USERS = st.secrets["users"]
except Exception:
    st.error("⚠️ Secrets not configured properly. Please check .streamlit/secrets.toml")
    st.stop()

# ====================== STATION COORDINATES ======================
station_coords = {
    "WADI": {"lat": 17.05303569516522, "lon": 76.99204755925912},
    "SDB": {"lat": 17.12207211329687, "lon": 76.94370232393466},
    "MR": {"lat": 17.199884316888113, "lon": 76.90242140933267},
    "HQR": {"lat": 17.258329320477387, "lon": 76.87213360102963},
    "KLBG": {"lat": 17.31464128074813, "lon": 76.82539943154254},
    "TJSP": {"lat": 17.38155787142842, "lon": 76.83078651026582},
    "BBD": {"lat": 17.336940866375414, "lon": 76.7792743961494},
    "SVG": {"lat": 17.33968072788599, "lon": 76.71139619013732},
    "HHD": {"lat": 17.352700945672176, "lon": 76.64674999614954},
    "GUR": {"lat": 17.340847607132325, "lon": 76.5895995384797},
    "KUI": {"lat": 17.357481126320312, "lon": 76.47050033971526},
    "GDGN": {"lat": 17.336448211586035, "lon": 76.53065519174201},  
    "DUD": {"lat": 17.36262542350625, "lon": 76.38023255381961},
    "NGS": {"lat": 17.429201164736277, "lon": 76.18296853848099},
    "BOT": {"lat": 17.395116057678774, "lon": 76.25531964887394}, 
    "LC-66": {"lat": 17.44944879773562, "lon": 76.14255475945156},
    "AKOR": {"lat": 17.450540923674154, "lon": 76.13878780964653},  
    "LC-61": {"lat": 17.524768759370218, "lon": 76.04191908624352},
    "TLT": {"lat": 17.529150347297044, "lon": 76.03601785680922},
    "HG STN": {"lat": 17.565461287426693, "lon": 75.9894306025621},
    "HG-A": {"lat": 17.555916499098096, "lon": 76.00138432588585},
    "TKWD": {"lat": 17.615367249178764, "lon": 75.93344533709772},
    "SUR": {"lat": 17.66461685325021, "lon": 75.8934378261056},
    "BALE": {"lat": 17.67603540641838, "lon": 75.84576721149409},
    "PK": {"lat": 17.725604941699864, "lon": 75.77920258081592},
    "MVE": {"lat": 17.742039265808994, "lon": 75.70628187232433},
    "MO": {"lat": 17.805775747199327, "lon": 75.67562640965197},
    "MKPT": {"lat": 17.876348021475454, "lon": 75.63508125440458},
    "AAG": {"lat": 17.928577532396076, "lon": 75.60830992499343},
    "WKA": {"lat": 17.98027395125776, "lon": 75.58849669615935},
    "MA": {"lat": 18.030290184953223, "lon": 75.54656926732524},
    "LC-42": {"lat": 18.0329616455573, "lon": 75.54422812169551},
    "LC-40": {"lat": 18.0566490214818, "lon": 75.51302934386983},
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
    "LC-21": {"lat": 18.31768146580364, "lon": 74.77141415514863}, 
    "MLM": {"lat": 18.368948833491366, "lon": 74.72444118537874},
    "BRB": {"lat": 18.407915112523582, "lon": 74.6490078310967}, 
    "LC-19": {"lat": 18.453227979495832, "lon": 74.61747183741623},
    "MRJ": {"lat": 16.81963598398112, "lon": 74.63884656730691},
    "BLWD": {"lat": 16.816450353858315, "lon": 74.6848784309091},
    "BDK": {"lat": 16.82260514883158, "lon": 74.73242941035451},
    "ARAG": {"lat": 16.822915416337786, "lon": 74.78885649248846},
    "BLNK": {"lat": 16.851881572150898, "lon": 74.87035305369132},
    "SGRE": {"lat": 16.89299615360604, "lon": 74.90379065076426},
    "AGDl": {"lat": 16.95511622318343, "lon": 74.9217523566787},
    "KVK": {"lat": 16.993451321113707, "lon": 74.93640413701563},
    "LNP": {"lat": 17.08409186087585, "lon": 74.96648999614565},
    "DLGN": {"lat": 17.12248941189781, "lon": 74.99090321680957},
    "GLV": {"lat": 17.172780301899458, "lon": 75.05616359877327},
    "JTRD": {"lat": 17.218097953252496, "lon": 75.11167313571244},
    "MSDG": {"lat": 17.269767344711966, "lon": 75.13869487464056},
    "JVA": {"lat": 17.29927168818127, "lon": 75.15831072498368},
    "WSD": {"lat": 17.37772780658702, "lon": 75.14796632741995},
    "SGLA": {"lat": 17.436927805442046, "lon": 75.18841716855994},
    "BMNI": {"lat": 17.510679238270942, "lon": 75.23653144358765},
    "BHLI": {"lat": 17.588890463817744, "lon": 75.27444374355429},
    "PVR": {"lat": 17.66895109379127, "lon": 75.31975306090992},
    "BBV": {"lat": 17.76904752111648, "lon": 75.39791698431098},
    "AHI": {"lat": 17.845027674667048, "lon": 75.40338896837972},
    "MLB": {"lat": 17.91701602096594, "lon": 75.40538340426733},
    "PSS": {"lat": 18.000856885777456, "lon": 75.38989817631149},
    "LAUL": {"lat": 18.03355629204764, "lon": 75.39532863007801},
    "CNHL": {"lat": 18.099881017907574, "lon": 75.45785352269934},
    "MGO": {"lat": 18.1096021568062, "lon": 75.49542122315127},
    "SEI": {"lat": 18.149389148247096, "lon": 75.59026142499687},
    "UPI": {"lat": 18.179945557118465, "lon": 75.6356972899416},
    "BTW": {"lat": 18.240970610084844, "lon": 75.71804892625418},
    "KCB": {"lat": 18.279056755382747, "lon": 75.78166860372836},
    "PJR": {"lat": 18.283948752266966, "lon": 75.86723131577448},
    "DRSV": {"lat": 18.247878328931048, "lon": 76.02287892615388},
    "YSI": {"lat": 18.317606171075578, "lon": 75.97700896898456},
    "KRMD": {"lat": 18.371892606761342, "lon": 76.04928088248217},
    "DKY": {"lat": 18.353691655460597, "lon": 76.10311836170408},
    "TER": {"lat": 18.35266581335599, "lon": 76.15005236994277},
    "PCP": {"lat": 18.3584179274254, "lon": 76.19327000536276},
    "MRX": {"lat": 18.380274853550898, "lon": 76.25111538019095},
    "NEI": {"lat": 18.3873686007519, "lon": 76.31091170451272},
    "OSA": {"lat": 18.378479646870694, "lon": 76.40761212644625},
    "HGL": {"lat": 18.390199985034297, "lon": 76.49591856320265},
    "LUR": {"lat": 18.429426709423403, "lon": 76.5560806337212},
    "BANL": {"lat": 18.44605226022196, "lon": 76.67840203837198},
    "GANI": {"lat": 18.479267109518492, "lon": 76.76394964918596},
    "DD": {"lat": 18.46377428753149, "lon": 74.57928783698621},
    "HG": {"lat": 17.565461287426693, "lon": 75.9894306025621},
}

# ====================== JURISDICTION MAPPINGS ======================
ENGG_ADEN = {
    "WADI": "ADEN KLBG", "SDB": "ADEN KLBG", "MR": "ADEN KLBG", "HQR": "ADEN KLBG",
    "KLBG": "ADEN KLBG", "BBD": "ADEN KLBG", "SVG": "ADEN KLBG", "HHD": "ADEN KLBG",
    "GUR": "ADEN KLBG", "KUI": "ADEN KLBG", "TJSP": "ADEN KLBG", "GDGN": "ADEN KLBG",
    "SBD": "ADEN KLBG",
    "AKOR": "ADEN S SUR", "BOT": "ADEN S SUR", "DUD": "ADEN S SUR", "HG": "ADEN S SUR",
    "NGS": "ADEN S SUR", "TKWD": "ADEN S SUR", "TLT": "ADEN S SUR",
    "HG STN": "ADEN S SUR", "HG-A": "ADEN S SUR",
    "AAG": "Sr.ADEN N SUR", "BALE": "Sr.ADEN N SUR", "MA": "Sr.ADEN N SUR", "MKPT": "Sr.ADEN N SUR",
    "MO": "Sr.ADEN N SUR", "MVE": "Sr.ADEN N SUR", "PK": "Sr.ADEN N SUR", "SUR": "Sr.ADEN N SUR",
    "WDS": "Sr.ADEN N SUR", "WKA": "Sr.ADEN N SUR", "MOHOL": "Sr.ADEN N SUR", "PAKNI": "Sr.ADEN N SUR",
    "BGVN": "Sr.ADEN KWV BG", "BLNI": "Sr.ADEN KWV BG", "BRB": "Sr.ADEN KWV BG", "DHS": "Sr.ADEN KWV BG",
    "JEUR": "Sr.ADEN KWV BG", "JNTR": "Sr.ADEN KWV BG", "KEM": "Sr.ADEN KWV BG", "KWV": "Sr.ADEN KWV BG",
    "MLM": "Sr.ADEN KWV BG", "PPJ": "Sr.ADEN KWV BG", "WSB": "Sr.ADEN KWV BG", "KEU": "Sr.ADEN KWV BG",
    "WSD": "Sr.ADEN KWV BG", "DD": "Sr.ADEN KWV BG", "MADHA": "Sr.ADEN KWV BG",
    "PSS": "Sr.ADEN KWV BG", "LAUL": "Sr.ADEN KWV BG", "CNHL": "Sr.ADEN KWV BG", "MGO": "Sr.ADEN KWV BG",
    "ARAG": "ADEN/PVR", "DLGN": "ADEN/PVR", "JTRD": "ADEN/PVR", "KVK": "ADEN/PVR",
    "MLB": "ADEN/PVR", "PVR": "ADEN/PVR", "SGLA": "ADEN/PVR", "SGRE": "ADEN/PVR", "MRJ": "ADEN/PVR",
    "MSDG": "ADEN/PVR", "JVA": "ADEN/PVR", "GLV": "ADEN/PVR", "LNP": "ADEN/PVR", "AGDl": "ADEN/PVR",
    "BLWD": "ADEN/PVR", "BDK": "ADEN/PVR", "BLNK": "ADEN/PVR", "BBV": "ADEN/PVR",
    "AHI": "ADEN/PVR", "BMNI": "ADEN/PVR", "BHLI": "ADEN/PVR",
    "BTW": "ADEN/LUR", "DKY": "ADEN/LUR", "HGL": "ADEN/LUR", "LUR": "ADEN/LUR",
    "OSA": "ADEN/LUR", "PJR": "ADEN/LUR", "SEI": "ADEN/LUR", "YSI": "ADEN/LUR",
    "DRSV": "ADEN/LUR", "MRX": "ADEN/LUR", "LTRR": "ADEN/LUR", "UMD": "ADEN/LUR",
    "UPI": "ADEN/LUR", "KCB": "ADEN/LUR", "TER": "ADEN/LUR", "PCP": "ADEN/LUR",
    "NEI": "ADEN/LUR", "KRMD": "ADEN/LUR", "BANL": "ADEN/LUR", "GANI": "ADEN/LUR",
}

ELECT_G_SSE = {
    "KWV": "SSE/ELECT/KWV", "DHS": "SSE/ELECT/KWV", "KEM": "SSE/ELECT/KWV", "BLNI": "SSE/ELECT/KWV",
    "BTW": "SSE/ELECT/KWV", "SEI": "SSE/ELECT/KWV", "PPJ": "SSE/ELECT/KWV", "WSB": "SSE/ELECT/KWV",
    "KEU": "SSE/ELECT/KWV", "JNTR": "SSE/ELECT/KWV", "BGVN": "SSE/ELECT/KWV", "MLM": "SSE/ELECT/KWV",
    "BRB": "SSE/ELECT/KWV", "DD": "SSE/ELECT/KWV", "MLB": "SSE/ELECT/KWV", "PVR": "SSE/ELECT/KWV",
    "SGLA": "SSE/ELECT/KWV", "DLGN": "SSE/ELECT/KWV", "JTRD": "SSE/ELECT/KWV", "SGRE": "SSE/ELECT/KWV",
    "ARAG": "SSE/ELECT/KWV", "KVK": "SSE/ELECT/KWV", "MRJ": "SSE/ELECT/KWV", "MKPT": "SSE/ELECT/KWV",
    "AAG": "SSE/ELECT/KWV", "WKA": "SSE/ELECT/KWV", "MA": "SSE/ELECT/KWV", "WDS": "SSE/ELECT/KWV",
    "WSD": "SSE/ELECT/KWV", "MADHA": "SSE/ELECT/KWV", "PSS": "SSE/ELECT/KWV", "LAUL": "SSE/ELECT/KWV",
    "CNHL": "SSE/ELECT/KWV", "MGO": "SSE/ELECT/KWV", "MSDG": "SSE/ELECT/KWV", "JVA": "SSE/ELECT/KWV",
    "GLV": "SSE/ELECT/KWV", "LNP": "SSE/ELECT/KWV", "AGDl": "SSE/ELECT/KWV", "BLWD": "SSE/ELECT/KWV",
    "BDK": "SSE/ELECT/KWV", "BLNK": "SSE/ELECT/KWV", "BBV": "SSE/ELECT/KWV", "AHI": "SSE/ELECT/KWV",
    "BMNI": "SSE/ELECT/KWV", "BHLI": "SSE/ELECT/KWV",
    "DUD": "SSE/ELECT/SUR", "NGS": "SSE/ELECT/SUR", "BOT": "SSE/ELECT/SUR", "AKOR": "SSE/ELECT/SUR",
    "SUR": "SSE/ELECT/SUR", "JEUR": "SSE/ELECT/SUR", "PK": "SSE/ELECT/SUR", "BALE": "SSE/ELECT/SUR",
    "MVE": "SSE/ELECT/SUR", "MO": "SSE/ELECT/SUR", "TKWD": "SSE/ELECT/SUR", "HG": "SSE/ELECT/SUR",
    "TLT": "SSE/ELECT/SUR", "HG STN": "SSE/ELECT/SUR", "HG-A": "SSE/ELECT/SUR",
    "MOHOL": "SSE/ELECT/SUR", "PAKNI": "SSE/ELECT/SUR",
    "KUI": "SSE/ELECT/KLBG", "GDGN": "SSE/ELECT/KLBG", "GUR": "SSE/ELECT/KLBG", "SVG": "SSE/ELECT/KLBG",
    "BBD": "SSE/ELECT/KLBG", "KLBG": "SSE/ELECT/KLBG", "TJSP": "SSE/ELECT/KLBG", "HQR": "SSE/ELECT/KLBG",
    "MR": "SSE/ELECT/KLBG", "SDB": "SSE/ELECT/KLBG", "SBD": "SSE/ELECT/KLBG", "WADI": "SSE/ELECT/KLBG",
    "HHD": "SSE/ELECT/KLBG",
    "PJR": "SSE/ELECT/LUR", "YSI": "SSE/ELECT/LUR", "DKY": "SSE/ELECT/LUR", "OSA": "SSE/ELECT/LUR",
    "HGL": "SSE/ELECT/LUR", "LUR": "SSE/ELECT/LUR", "DRSV": "SSE/ELECT/LUR", "MRX": "SSE/ELECT/LUR",
    "LTRR": "SSE/ELECT/LUR", "UMD": "SSE/ELECT/LUR", "UPI": "SSE/ELECT/LUR", "KCB": "SSE/ELECT/LUR",
    "TER": "SSE/ELECT/LUR", "PCP": "SSE/ELECT/LUR", "NEI": "SSE/ELECT/LUR", "KRMD": "SSE/ELECT/LUR",
    "BANL": "SSE/ELECT/LUR", "GANI": "SSE/ELECT/LUR",
}

ELECT_TRD_SSE = {
    "SUR": "SSE/TRD/SUR", "TKWD": "SSE/TRD/SUR", "HG": "SSE/TRD/SUR", "TLT": "SSE/TRD/SUR",
    "AKOR": "SSE/TRD/SUR", "BALE": "SSE/TRD/SUR", "PK": "SSE/TRD/SUR", "MVE": "SSE/TRD/SUR",
    "MO": "SSE/TRD/SUR", "HG STN": "SSE/TRD/SUR", "HG-A": "SSE/TRD/SUR",
    "MOHOL": "SSE/TRD/SUR", "PAKNI": "SSE/TRD/SUR",
    "NGS": "SSE/TRD/DUD", "BOT": "SSE/TRD/DUD", "DUD": "SSE/TRD/DUD", "KUI": "SSE/TRD/DUD",
    "GUR": "SSE/TRD/DUD", "SVG": "SSE/TRD/DUD", "HHD": "SSE/TRD/DUD",
    "BBD": "JE/TRD/KLBG", "KLBG": "JE/TRD/KLBG", "TJSP": "JE/TRD/KLBG", "HQR": "JE/TRD/KLBG",
    "MR": "JE/TRD/KLBG", "SDB": "JE/TRD/KLBG", "SBD": "JE/TRD/KLBG", "GDGN": "JE/TRD/KLBG",
    "WADI": "JE/TRD/WADI",
    "MKPT": "SSE/TRD/KWV", "AAG": "SSE/TRD/KWV", "WKA": "SSE/TRD/KWV", "WDS": "SSE/TRD/KWV",
    "KWV": "SSE/TRD/KWV", "DHS": "SSE/TRD/KWV", "KEM": "SSE/TRD/KWV", "BLNI": "SSE/TRD/KWV",
    "WSD": "SSE/TRD/KWV", "MADHA": "SSE/TRD/KWV", "PSS": "SSE/TRD/KWV", "LAUL": "SSE/TRD/KWV",
    "JEUR": "SSE/TRD/KEU", "PPJ": "SSE/TRD/KEU", "WSB": "SSE/TRD/KEU", "KEU": "SSE/TRD/KEU",
    "JNTR": "SSE/TRD/KEU", "BGVN": "SSE/TRD/KEU", "MLM": "SSE/TRD/KEU", "BRB": "SSE/TRD/KEU", "DD": "SSE/TRD/KEU",
    "SEI": "SSE/TRD/BTW", "BTW": "SSE/TRD/BTW", "PJR": "SSE/TRD/BTW", "CNHL": "SSE/TRD/BTW",
    "MGO": "SSE/TRD/BTW", "UPI": "SSE/TRD/BTW", "KCB": "SSE/TRD/BTW",
    "DRSV": "SSE/TRD/DRSV", "YSI": "SSE/TRD/DRSV", "DKY": "SSE/TRD/DRSV", "KRMD": "SSE/TRD/DRSV",
    "OSA": "SSE/TRD/LUR", "HGL": "SSE/TRD/LUR", "LUR": "SSE/TRD/LUR", "MRX": "SSE/TRD/LUR",
    "LTRR": "SSE/TRD/LUR", "UMD": "SSE/TRD/LUR", "TER": "SSE/TRD/LUR", "PCP": "SSE/TRD/LUR",
    "NEI": "SSE/TRD/LUR", "BANL": "SSE/TRD/LUR", "GANI": "SSE/TRD/LUR",
    "MLB": "SSE/TRD/PVR", "PVR": "SSE/TRD/PVR", "BBV": "SSE/TRD/PVR", "AHI": "SSE/TRD/PVR",
    "SGLA": "SSE/TRD/SGLA", "JTRD": "SSE/TRD/SGLA", "DLGN": "SSE/TRD/SGLA",
    "MSDG": "SSE/TRD/SGLA", "JVA": "SSE/TRD/SGLA", "GLV": "SSE/TRD/SGLA", "BMNI": "SSE/TRD/SGLA", "BHLI": "SSE/TRD/SGLA",
    "KVK": "SSE/TRD/SGRE", "SGRE": "SSE/TRD/SGRE", "ARAG": "SSE/TRD/SGRE",
    "LNP": "SSE/TRD/SGRE", "AGDl": "SSE/TRD/SGRE", "BLNK": "SSE/TRD/SGRE",
    "BLWD": "SSE/TRD/KWV", "BDK": "SSE/TRD/KWV", "MRJ": "SSE/TRD/KWV",
}

OPERATING_TI = {
    "SUR": "TI/SUR/N", "BALE": "TI/SUR/N", "PK": "TI/SUR/N", "MVE": "TI/SUR/N", "MO": "TI/SUR/N",
    "MKPT": "TI/SUR/N", "AAG": "TI/SUR/N", "WKA": "TI/SUR/N", "MOHOL": "TI/SUR/N", "PAKNI": "TI/SUR/N",
    "TKWD": "TI/SUR/S", "HG": "TI/SUR/S", "TLT": "TI/SUR/S", "AKOR": "TI/SUR/S",
    "NGS": "TI/SUR/S", "BOT": "TI/SUR/S", "HG STN": "TI/SUR/S", "HG-A": "TI/SUR/S",
    "DUD": "TI/KLBG", "KUI": "TI/KLBG", "GUR": "TI/KLBG", "SVG": "TI/KLBG",
    "BBD": "TI/KLBG", "KLBG": "TI/KLBG", "TJSP": "TI/KLBG", "HHD": "TI/KLBG", "GDGN": "TI/KLBG",
    "HQR": "TI/WADI", "MR": "TI/WADI", "SDB": "TI/WADI", "WADI": "TI/WADI", "SBD": "TI/WADI",
    "WDS": "TI/KWV", "KWV": "TI/KWV", "DHS": "TI/KWV", "KEM": "TI/KWV",
    "BLNI": "TI/KWV", "JEUR": "TI/KWV", "WSD": "TI/KWV", "MADHA": "TI/KWV", "MA": "TI/KWV",
    "PSS": "TI/KWV", "LAUL": "TI/KWV",
    "PPJ": "TI/BGVN", "WSB": "TI/BGVN", "KEU": "TI/BGVN", "JNTR": "TI/BGVN",
    "BGVN": "TI/BGVN", "MLM": "TI/BGVN", "BRB": "TI/BGVN", "DD": "TI/BGVN",
    "SEI": "TI/LUR", "BTW": "TI/LUR", "PJR": "TI/LUR", "DRSV": "TI/LUR",
    "YSI": "TI/LUR", "DKY": "TI/LUR", "OSA": "TI/LUR", "HGL": "TI/LUR", "LUR": "TI/LUR",
    "MRX": "TI/LUR", "LTRR": "TI/LUR", "UMD": "TI/LUR", "CNHL": "TI/LUR", "MGO": "TI/LUR",
    "UPI": "TI/LUR", "KCB": "TI/LUR", "TER": "TI/LUR", "PCP": "TI/LUR",
    "NEI": "TI/LUR", "KRMD": "TI/LUR", "BANL": "TI/LUR", "GANI": "TI/LUR",
    "MLB": "TI/PVR", "PVR": "TI/PVR", "SGLA": "TI/PVR", "JTRD": "TI/PVR",
    "DLGN": "TI/PVR", "KVK": "TI/PVR", "SGRE": "TI/PVR", "ARAG": "TI/PVR", "MRJ": "TI/PVR",
    "MSDG": "TI/PVR", "JVA": "TI/PVR", "GLV": "TI/PVR", "LNP": "TI/PVR", "AGDl": "TI/PVR",
    "BLWD": "TI/PVR", "BDK": "TI/PVR", "BLNK": "TI/PVR", "BBV": "TI/PVR",
    "AHI": "TI/PVR", "BMNI": "TI/PVR", "BHLI": "TI/PVR",
}

SNT_ADSTE = {
    "WADI": "ADSTE/KLBG (WADI-HG)", "SDB": "ADSTE/KLBG (WADI-HG)", "MR": "ADSTE/KLBG (WADI-HG)",
    "HQR": "ADSTE/KLBG (WADI-HG)", "KLBG": "ADSTE/KLBG (WADI-HG)", "BBD": "ADSTE/KLBG (WADI-HG)",
    "SVG": "ADSTE/KLBG (WADI-HG)", "HHD": "ADSTE/KLBG (WADI-HG)", "GUR": "ADSTE/KLBG (WADI-HG)",
    "KUI": "ADSTE/KLBG (WADI-HG)", "DUD": "ADSTE/KLBG (WADI-HG)", "BOT": "ADSTE/KLBG (WADI-HG)",
    "AKOR": "ADSTE/KLBG (WADI-HG)", "TLT": "ADSTE/KLBG (WADI-HG)", "HG": "ADSTE/KLBG (WADI-HG)",
    "TJSP": "ADSTE/KLBG (WADI-HG)", "HG STN": "ADSTE/KLBG (WADI-HG)", "HG-A": "ADSTE/KLBG (WADI-HG)",
    "SBD": "ADSTE/KLBG (WADI-HG)", "GDGN": "ADSTE/KLBG (WADI-HG)", "NGS": "ADSTE/KLBG (WADI-HG)",
    "TKWD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SUR": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BALE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "PK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MVE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MO": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MKPT": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "AAG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "WKA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MLB": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "PVR": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SGLA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "JTRD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "DLGN": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "KVK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "SGRE": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "ARAG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MRJ": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "MA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MOHOL": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "PAKNI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "MSDG": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "JVA": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "GLV": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "LNP": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "AGDl": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BLWD": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BDK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BLNK": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BBV": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "AHI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)", "BMNI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "BHLI": "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)",
    "KWV": "ADSTE/KWV-I (KWV-BRB)", "DHS": "ADSTE/KWV-I (KWV-BRB)", "KEM": "ADSTE/KWV-I (KWV-BRB)",
    "BLNI": "ADSTE/KWV-I (KWV-BRB)", "JEUR": "ADSTE/KWV-I (KWV-BRB)", "PPJ": "ADSTE/KWV-I (KWV-BRB)",
    "WSB": "ADSTE/KWV-I (KWV-BRB)", "KEU": "ADSTE/KWV-I (KWV-BRB)", "JNTR": "ADSTE/KWV-I (KWV-BRB)",
    "BGVN": "ADSTE/KWV-I (KWV-BRB)", "MLM": "ADSTE/KWV-I (KWV-BRB)", "BRB": "ADSTE/KWV-I (KWV-BRB)",
    "WDS": "ADSTE/KWV-I (KWV-BRB)", "WSD": "ADSTE/KWV-I (KWV-BRB)", "DD": "ADSTE/KWV-I (KWV-BRB)",
    "MADHA": "ADSTE/KWV-I (KWV-BRB)", "PSS": "ADSTE/KWV-I (KWV-BRB)", "LAUL": "ADSTE/KWV-I (KWV-BRB)",
    "SEI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "BTW": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "PJR": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "YSI": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "MRX": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "OSA": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "HGL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "LUR": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "DRSV": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "DKY": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "LTRR": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "UMD": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "CNHL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "MGO": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "UPI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "KCB": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "TER": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "PCP": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "NEI": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "KRMD": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
    "BANL": "ADSTE/KWV-II (LC-34(DKY)-LUR)", "GANI": "ADSTE/KWV-II (LC-34(DKY)-LUR)",
}

# ------ Precompute a normalized (upper/no-space, HG-alias-collapsed) lookup
# for each jurisdiction table once, instead of re-normalizing per row. ------
def _normalize_key(k):
    k2 = str(k).strip().upper().replace(" ", "")
    if k2 in ["HGSTN", "HGA", "HG-A"]:
        k2 = "HG"
    if k2 == "AGDL":
        k2 = "AGDl"
    return k2

def _build_norm_map(d):
    out = {}
    for k, v in d.items():
        out[_normalize_key(k)] = v
        out[str(k).strip().upper()] = v
    return out

_ENGG_NORM = _build_norm_map(ENGG_ADEN)
_ELECT_G_NORM = _build_norm_map(ELECT_G_SSE)
_ELECT_TRD_NORM = _build_norm_map(ELECT_TRD_SSE)
_OPTG_NORM = _build_norm_map(OPERATING_TI)
_SNT_NORM = _build_norm_map(SNT_ADSTE)

JURISDICTION_TABLES = {
    "Engineering (ADEN)": _ENGG_NORM,
    "Electrical General": _ELECT_G_NORM,
    "Electrical TRD": _ELECT_TRD_NORM,
    "Operating (TI)": _OPTG_NORM,
    "S&T (ADSTE)": _SNT_NORM,
}

# A department that matches none of the words below is "Unclassified" (it used to be silently
# treated as S&T). If your sheet writes the S&T department differently, add the word here.
_SNT_PATTERN = r"S\s*&\s*T|SNT|SIGNAL|TELECOM|\bSIG\b|ADSTE"


def get_jurisdiction_vectorized(df):
    """Vectorized jurisdiction lookup (same precedence as before: OPTG > ENGG > TRD > ELECT > S&T)."""
    if 'STATION' not in df.columns or 'DEPARTMENT' not in df.columns:
        return pd.Series("Unclassified", index=df.index)

    stn_norm = df['STATION'].fillna("").apply(_normalize_key)
    dept_upper = df['DEPARTMENT'].fillna("").astype(str).str.strip().str.upper()

    is_snt = dept_upper.str.contains(_SNT_PATTERN, regex=True, na=False)
    is_optg = dept_upper.str.contains("OPTG|OPERATING", regex=True, na=False)
    is_engg = dept_upper.str.contains("ENGG|ENGINEERING|ADEN", regex=True, na=False)
    is_trd = dept_upper.str.contains("TRD|TRACTION|OHE", regex=True, na=False)
    is_elect = dept_upper.str.contains("ELECT|ELECTRICAL", regex=True, na=False)

    result = pd.Series("Unclassified", index=df.index, dtype=object)
    result = result.mask(is_snt, stn_norm.map(_SNT_NORM).fillna("Unclassified"))
    result = result.mask(is_elect, stn_norm.map(_ELECT_G_NORM).fillna("Unclassified"))
    result = result.mask(is_trd, stn_norm.map(_ELECT_TRD_NORM).fillna("Unclassified"))
    result = result.mask(is_engg, stn_norm.map(_ENGG_NORM).fillna("Unclassified"))
    result = result.mask(is_optg, stn_norm.map(_OPTG_NORM).fillna("Unclassified"))
    return result


# ------ Coordinates: exact match only. HG STN / HG-A / HG keep their own points. ------
def _coord_key(k):
    return re.sub(r"[\s\-]+", "", str(k).strip().upper())


_STATION_COORDS_NORM = {_coord_key(k): v for k, v in station_coords.items()}


def match_station_coords(station_name):
    """Exact match on the normalised code. Unknown stations return None (reported on the Map tab, never guessed)."""
    return _STATION_COORDS_NORM.get(_coord_key(station_name))

# ====================== FORECASTING ENGINE ======================
def now_ist():
    return pd.Timestamp.now(tz=IST).tz_localize(None)


def fmt_ist(iso):
    try:
        return pd.Timestamp(iso).strftime("%d %b %Y, %H:%M IST")
    except Exception:
        return str(iso)


def get_global_month_index(df):
    if df is None or df.empty or 'DATE' not in df.columns:
        return pd.DatetimeIndex([])
    d = df.dropna(subset=['DATE'])
    if d.empty:
        return pd.DatetimeIndex([])
    start = d['DATE'].min().to_period('M').to_timestamp()
    end = d['DATE'].max().to_period('M').to_timestamp()
    return pd.date_range(start, end, freq='MS')

def build_monthly_series(df, full_index=None):
    if df is None or df.empty or 'DATE' not in df.columns:
        return pd.Series(dtype=float)
    d = df.dropna(subset=['DATE'])
    if d.empty:
        return pd.Series(dtype=float)
    d = d.set_index('DATE').sort_index()
    series = d.resample('MS').size().astype(float)
    if full_index is not None and len(full_index) > 0:
        series = series.reindex(full_index, fill_value=0.0)
    return series

def trim_incomplete_current_month(series):
    """Drops the current month (IST, not server time) because it is still in progress."""
    if series.empty:
        return series
    now = now_ist()
    current_month_start = pd.Timestamp(year=now.year, month=now.month, day=1)
    if series.index[-1] == current_month_start:
        return series.iloc[:-1]
    return series

def write_styled_sheet(writer, df, sheet_name, header_color="#0277bd"):
    workbook = writer.book
    df.to_excel(writer, index=False, sheet_name=sheet_name, header=False, startrow=1)
    worksheet = writer.sheets[sheet_name]

    header_fmt = workbook.add_format({
        'bold': True, 'font_color': 'white', 'bg_color': header_color,
        'border': 1, 'align': 'center', 'valign': 'vcenter', 'text_wrap': True
    })
    text_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter'})
    number_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter', 'num_format': '#,##0'})
    date_fmt = workbook.add_format({'border': 1, 'valign': 'vcenter', 'num_format': 'dd-mmm-yyyy'})

    for col_idx, col_name in enumerate(df.columns):
        worksheet.write(0, col_idx, str(col_name), header_fmt)
        series = df[col_name]
        if pd.api.types.is_datetime64_any_dtype(series) or str(col_name).strip().upper() == 'DATE':
            cell_fmt = date_fmt
        elif pd.api.types.is_numeric_dtype(series):
            cell_fmt = number_fmt
        else:
            cell_fmt = text_fmt
        sample = series.head(1000).astype(str)  # width from a sample, not every row
        content_len = int(sample.map(len).max()) if len(sample) else 0
        width = min(max(max(content_len, len(str(col_name))) + 2, 10), 45)
        worksheet.set_column(col_idx, col_idx, width, cell_fmt)

    worksheet.set_row(0, 30)
    worksheet.freeze_panes(1, 0)
    if len(df) > 0:
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)
    return worksheet


@st.cache_data(show_spinner=False)
def build_excel_bytes(sheets):
    """sheets: tuple of (sheet_name, DataFrame). Cached so it is not rebuilt on every rerun.
    strings_to_formulas=False stops cell text starting with '=' from becoming an Excel formula."""
    out = BytesIO()
    opts = {"options": {"strings_to_formulas": False, "nan_inf_to_errors": True}}
    with pd.ExcelWriter(out, engine='xlsxwriter', engine_kwargs=opts) as writer:
        for name, sdf in sheets:
            if sdf is not None and not sdf.empty:
                write_styled_sheet(writer, sdf, str(name)[:31])
    return out.getvalue()


def _linear_forecast(series, periods):
    y = series.values.astype(float)
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    future_x = np.arange(len(y), len(y) + periods, dtype=float)
    vals = slope * future_x + intercept
    resid = float(np.std(y - fitted, ddof=0))
    return vals, "Linear trend regression", resid

@st.cache_data(show_spinner=False)
def forecast_series(series, periods=3):
    series = series.dropna().astype(float)
    n = len(series)
    if n == 0:
        return pd.Series(dtype=float), "No data", 0.0
    future_idx = pd.date_range(series.index[-1] + pd.DateOffset(months=1), periods=periods, freq='MS')
    if n < 4:
        vals = np.repeat(float(series.iloc[-1]), periods)
        method = "Naive (last observed month)"
        resid = float(series.std(ddof=0)) if n > 1 else 0.0
    elif STATSMODELS_AVAILABLE and n >= 24:
        try:
            model = ExponentialSmoothing(series, trend="add", seasonal="add", seasonal_periods=12, damped_trend=True, initialization_method="estimated").fit(optimized=True)
            vals = np.asarray(model.forecast(periods), dtype=float)
            resid = float(np.std(series.values - np.asarray(model.fittedvalues, dtype=float), ddof=0))
            method = "Holt-Winters (damped trend + seasonality)"
        except Exception:
            vals, method, resid = _linear_forecast(series, periods)
    elif STATSMODELS_AVAILABLE and n >= 6:
        try:
            model = ExponentialSmoothing(series, trend="add", damped_trend=True, initialization_method="estimated").fit(optimized=True)
            vals = np.asarray(model.forecast(periods), dtype=float)
            resid = float(np.std(series.values - np.asarray(model.fittedvalues, dtype=float), ddof=0))
            method = "Holt exponential smoothing"
        except Exception:
            vals, method, resid = _linear_forecast(series, periods)
    else:
        vals, method, resid = _linear_forecast(series, periods)
    vals = np.clip(np.round(vals), 0, None)
    return pd.Series(vals, index=future_idx), method, resid

def backtest_wape(series, horizon=3):
    """WAPE = total absolute error / total actual. Unlike MAPE it stays valid when a month has 0 cases."""
    series = series.dropna().astype(float)
    if len(series) < horizon + 4:
        return None
    train, test = series.iloc[:-horizon], series.iloc[-horizon:]
    pred, _, _ = forecast_series(train, horizon)
    if pred.empty:
        return None
    actual = test.values
    denom = float(np.sum(actual))
    if denom <= 0:
        return None
    return float(np.sum(np.abs(actual - pred.values[:len(actual)])) / denom * 100)

def forecast_by_group(df, group_col, horizon, top_n=10, full_index=None):
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()
    ranking = df.groupby(group_col).size()
    rows = []
    for g in ranking.sort_values(ascending=False).head(top_n).index:
        s = build_monthly_series(df[df[group_col] == g], full_index=full_index)
        s = trim_incomplete_current_month(s)
        if s.empty:
            continue
        fc, method, _ = forecast_series(s, horizon)
        row = {group_col: g, "Last month (actual)": int(s.iloc[-1])}
        for dt, v in fc.items():
            row[dt.strftime('%b %Y')] = int(v)
        row["Forecast total"] = int(fc.sum()) if not fc.empty else 0
        row["Model"] = method
        rows.append(row)
    return pd.DataFrame(rows)

# ====================== SHARED / DEDUPLICATED UI HELPERS ======================
def compute_station_summary(df):
    """Single source of truth for the STATION x Cases table, used in 3 places."""
    if df.empty or 'STATION' not in df.columns:
        return pd.DataFrame(columns=['STATION', 'Cases'])
    return df.groupby('STATION').size().reset_index(name='Cases').sort_values('Cases', ascending=False)


def render_station_summary_table(station_summary_df):
    styler = station_summary_df.style.format({"Cases": "{:,}"})
    try:
        styler = styler.background_gradient(subset=['Cases'], cmap='YlOrRd')  # needs matplotlib
    except Exception:
        pass
    st.dataframe(styler, hide_index=True, **STRETCH)


PREFERRED_ORDER = ['DATE', 'STATION', 'DEPARTMENT', 'JURISDICTION', 'ERROR MAIN CATEGORY',
                   'DL FAULT MESSAGE', 'REMARKS GIVEN BY S&T']


def order_columns(df):
    cols = [c for c in PREFERRED_ORDER if c in df.columns] + [c for c in df.columns if c not in PREFERRED_ORDER]
    return df[cols]


def build_display_df(filtered_df):
    display_df = order_columns(filtered_df.copy())
    if 'DATE' in display_df.columns:
        display_df['DATE'] = display_df['DATE'].dt.date
    return display_df, list(display_df.columns)


def render_detailed_records_section(filtered_df, extra_sheets=None, file_prefix="DRISHTI_Report", button_label="⬇️ Download Report", button_key=None):
    """
    Shared 'Detailed Records table + Excel export' block.
    extra_sheets: list of (sheet_name, dataframe) tuples to add to the workbook.
    """
    st.markdown('<p class="section-header">Detailed Records</p>', unsafe_allow_html=True)
    if filtered_df.empty:
        st.warning("No records found.")
        return

    display_df, cols = build_display_df(filtered_df)
    st.dataframe(display_df.head(MAX_DISPLAY_ROWS), hide_index=True, **STRETCH)
    if len(display_df) > MAX_DISPLAY_ROWS:
        st.caption(f"Showing the first {MAX_DISPLAY_ROWS:,} of {len(display_df):,} rows. The Excel download contains all rows.")

    st.markdown("---")
    col_btn1, col_btn2, col_btn3 = st.columns([1, 3, 1])
    with col_btn2:
        sheets = (("Filtered_Records", order_columns(filtered_df)),) + tuple(extra_sheets or [])
        st.download_button(
            label=button_label,
            data=build_excel_bytes(sheets),
            file_name=f"{file_prefix}_{now_ist().strftime('%Y%m%d_%H%M')}.xlsx",
            mime=XLSX_MIME,
            type="primary",
            key=button_key,
            **STRETCH
        )

# ====================== DATA LOADING + OFFLINE SNAPSHOT ======================
def parse_dates(series):
    """ISO dates (2026-04-03) stay ISO; everything else is read day-first (Indian dd/mm/yyyy)."""
    def _to_dt(x, dayfirst):
        try:
            return pd.to_datetime(x, errors="coerce", dayfirst=dayfirst, format="mixed")
        except (TypeError, ValueError):
            return pd.to_datetime(x, errors="coerce", dayfirst=dayfirst)

    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    txt = series.astype(str).str.strip()
    iso = txt.str.match(r"^\d{4}-\d{1,2}-\d{1,2}")
    out = pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns]")
    if iso.any():
        out[iso] = _to_dt(txt[iso], False)
    if (~iso).any():
        out[~iso] = _to_dt(txt[~iso], True)
    return out


def clean_dataframe(df):
    """Returns (clean_df, info). Raises ValueError if DATE or STATION are missing."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.lower().str.replace('.', '', regex=False).str.contains(r'^(?:sl|sr)\s*no', regex=True)]
    missing_required = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_required:
        raise ValueError(f"Required column(s) missing in sheet: {', '.join(missing_required)}")
    missing_optional = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    for c in missing_optional:
        df[c] = np.nan

    # Trim text, blank -> NaN; upper-case codes so 'sur ' and 'SUR' are one station.
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})
    for c in ("STATION", "DEPARTMENT"):
        df[c] = df[c].str.upper()

    raw_dates = df['DATE']
    df['DATE'] = parse_dates(raw_dates)
    had_text = raw_dates.notna() & raw_dates.astype(str).str.strip().ne("")
    bad_dates = int((df['DATE'].isna() & had_text).sum())
    blank_dates = int((df['DATE'].isna() & ~had_text).sum())

    df['MONTH'] = df['DATE'].dt.strftime('%B %Y')          # now includes the year
    df['YEAR_MONTH'] = df['DATE'].dt.strftime('%Y-%m')      # used to sort months chronologically
    df['JURISDICTION'] = get_jurisdiction_vectorized(df)
    return df, {"bad_dates": bad_dates, "blank_dates": blank_dates, "missing_columns": missing_optional}


def save_snapshot(df, meta):
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        out = df.copy()
        for c in out.columns:
            if out[c].dtype == object:
                out[c] = out[c].astype("string")
        tmp = CACHE_DIR / "snapshot.tmp"
        out.to_parquet(tmp, index=False)
        tmp.replace(SNAPSHOT_FILE)
        META_FILE.write_text(json.dumps(meta), encoding="utf-8")
    except Exception:
        logger.exception("Could not save offline snapshot")


def load_snapshot():
    try:
        if not SNAPSHOT_FILE.exists():
            return None, None
        df = pd.read_parquet(SNAPSHOT_FILE)
        for c in df.columns:
            if str(df[c].dtype) == "string":
                df[c] = df[c].astype(object).where(df[c].notna(), np.nan)
        meta = json.loads(META_FILE.read_text(encoding="utf-8")) if META_FILE.exists() else {}
        return df, meta
    except Exception:
        logger.exception("Could not read offline snapshot")
        return None, None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading latest data from Google Sheets...")
def fetch_online(sheet_id, sheet_name):
    """Raises on any failure (Streamlit never caches exceptions). Saves an offline snapshot on success."""
    info = dict(st.secrets["gcp_service_account"])
    last_err, records = None, None
    for scopes in (["https://www.googleapis.com/auth/spreadsheets.readonly"], None):  # read-only first
        try:
            client = (gspread.service_account_from_dict(info, scopes=scopes) if scopes
                      else gspread.service_account_from_dict(info))
            try:
                client.set_timeout(20)
            except Exception:
                pass
            records = client.open_by_key(sheet_id).worksheet(sheet_name).get_all_records()
            break
        except Exception as e:
            last_err = e
    if records is None:
        raise last_err
    raw = pd.DataFrame(records)
    if raw.empty:
        raise ValueError("Google Sheet is empty")
    df, meta = clean_dataframe(raw)
    meta["loaded_at"] = pd.Timestamp.now(tz=IST).isoformat()
    meta["rows"] = int(len(df))
    save_snapshot(df, meta)
    return {"df": df, "meta": meta}


def load_data(force_offline):
    """Returns (df, status). status['mode'] is 'live', 'offline' or 'none'."""
    reason = "forced" if force_offline else None
    if not force_offline:
        if time.time() >= st.session_state.get("_online_retry_at", 0):
            try:
                res = fetch_online(SHEET_ID, SHEET_NAME)
                st.session_state.pop("_online_retry_at", None)
                return res["df"], {"mode": "live", **res["meta"]}
            except Exception:
                logger.exception("Live data load failed; falling back to offline snapshot")
                st.session_state["_online_retry_at"] = time.time() + ONLINE_RETRY_SECONDS
        reason = "unreachable"
    df, meta = load_snapshot()
    if df is not None:
        return df, {"mode": "offline", "reason": reason, **(meta or {})}
    return None, {"mode": "none", "reason": reason}


@st.cache_resource(ttl=3600, show_spinner=False)
def get_logo_bytes():
    """Logo from ./assets/logo.png; downloaded once (when online) and kept on disk for offline use."""
    local = ASSETS_DIR / "logo.png"
    if local.exists():
        return local.read_bytes()
    try:
        req = Request(IR_LOGO_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=4) as resp:
            data = resp.read()
        ASSETS_DIR.mkdir(exist_ok=True)
        local.write_bytes(data)
        return data
    except Exception:
        return None

# ====================== FILTER HELPERS ======================
FILTER_KEYS = ["stn_key", "err_key", "cat_key", "month_key", "fault_key", "remark_key", "jur_key"]


def month_options(df):
    if 'MONTH' not in df.columns or 'YEAR_MONTH' not in df.columns:
        return []
    d = df.dropna(subset=['DATE']).drop_duplicates('YEAR_MONTH').sort_values('YEAR_MONTH')
    return d['MONTH'].tolist()  # chronological, with the year


def prune_selection(key, options):
    """Drops selected values that no longer exist (e.g. after a data refresh)."""
    if key in st.session_state:
        st.session_state[key] = [v for v in st.session_state[key] if v in options]


def sync_date_bounds(data_min, data_max):
    """Keeps the date pickers valid when data changes: they follow the new min/max unless the user narrowed them."""
    prev = st.session_state.get("_bounds")
    cur = (data_min, data_max)
    if prev != cur or "from_date_key" not in st.session_state:
        f = st.session_state.get("from_date_key")
        t = st.session_state.get("to_date_key")
        if prev is None or f is None or f == prev[0]:
            f = data_min
        if prev is None or t is None or t == prev[1]:
            t = data_max
        st.session_state["from_date_key"] = min(max(f, data_min), data_max)
        st.session_state["to_date_key"] = min(max(t, data_min), data_max)
        st.session_state["_bounds"] = cur


def reset_filters():
    for k in FILTER_KEYS:
        st.session_state[k] = []
    if "_bounds" in st.session_state:
        st.session_state["from_date_key"], st.session_state["to_date_key"] = st.session_state["_bounds"]
    st.session_state.map_selected_station = None
    st.session_state["_last_map_click"] = None
    st.session_state["_map_epoch"] += 1

# ====================== AUTH ======================
def verify_password(stored, supplied):
    """Supports 'pbkdf2_sha256$iters$salt_hex$digest' hashes and (legacy) plain text. Constant-time compare."""
    supplied = str(supplied or "")
    if not stored:
        hmac.compare_digest(b"x", b"y")
        return False
    stored = str(stored)
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iters, salt_hex, digest = stored.split("$")
            calc = hashlib.pbkdf2_hmac("sha256", supplied.encode(), bytes.fromhex(salt_hex), int(iters)).hex()
            return hmac.compare_digest(calc, digest)
        except Exception:
            return False
    return hmac.compare_digest(stored.encode(), supplied.encode())


# ====================== SESSION STATE ======================
for _k, _v in {"logged_in": False, "user_name": "", "map_selected_station": None, "_map_epoch": 0,
               "_last_map_click": None, "_fail_count": 0, "_locked_until": 0.0,
               "_last_active": time.time(), "_last_refresh": 0.0, "_prepared": {}}.items():
    st.session_state.setdefault(_k, _v)

# ====================== LOGIN ======================
def login_page():
    col1, col2, col3 = st.columns([3, 3, 3])
    with col2:
        st.subheader("🔐 Secure Login")
        remaining = st.session_state["_locked_until"] - time.time()
        if remaining > 0:
            st.error(f"Too many failed attempts. Try again in {int(remaining) + 1} seconds.")
            return
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Username / Email", placeholder="Enter your ID").strip()
            password = st.text_input("Password", type="password", placeholder="Enter Password")
            if st.form_submit_button("Login", type="primary", **STRETCH):
                stored = USERS[email].get("password") if email in USERS else None
                if verify_password(stored, password):
                    st.session_state.logged_in = True
                    st.session_state.user_name = USERS[email].get("name", email)
                    st.session_state["_fail_count"] = 0
                    st.session_state["_last_active"] = time.time()
                    logger.info("Login OK: %s", email)
                    st.rerun()
                else:
                    st.session_state["_fail_count"] += 1
                    logger.warning("Login failed for '%s'", email)
                    if st.session_state["_fail_count"] >= MAX_LOGIN_ATTEMPTS:
                        st.session_state["_locked_until"] = time.time() + LOGIN_LOCK_SECONDS
                        st.session_state["_fail_count"] = 0
                    st.error("Invalid credentials!")


def logout():
    for k in ("logged_in", "user_name", "map_selected_station", "_prepared"):
        st.session_state.pop(k, None)
    st.rerun()


def refresh_data():
    if time.time() - st.session_state["_last_refresh"] < REFRESH_COOLDOWN_SECONDS:
        st.sidebar.warning("Please wait a few seconds before refreshing again.")
        return
    st.session_state["_last_refresh"] = time.time()
    st.cache_data.clear()
    st.session_state.pop("_online_retry_at", None)
    st.session_state.map_selected_station = None
    st.session_state["_last_map_click"] = None
    st.rerun()

# ====================== OFFLINE HTML DASHBOARD ======================
def build_offline_html(df, station_summary, cat_sum, error_sum, jur_sum, status, user):
    """One self-contained .html (Plotly.js embedded once). Opens with no internet and no server."""
    def _style(fig, **kw):
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a', **kw)
        return fig

    figs = []
    hist = build_monthly_series(df)
    if not hist.empty:
        f = go.Figure(go.Scatter(x=hist.index, y=hist.values, mode='lines+markers', line=dict(color='#0277bd', width=3)))
        figs.append(_style(f, height=380, title="Monthly cases", xaxis_title="Month", yaxis_title="Cases"))
    if not station_summary.empty:
        f = px.bar(station_summary.head(15), x='STATION', y='Cases', text='Cases', color='Cases', color_continuous_scale='RdYlGn_r')
        figs.append(_style(f, height=420, title="Top 15 stations", xaxis_tickangle=45))
        pts = []
        for _, r in station_summary.iterrows():
            c = match_station_coords(r['STATION'])
            if c:
                pts.append({'STATION': r['STATION'], 'Cases': int(r['Cases']), 'lat': c['lat'], 'lon': c['lon']})
        if pts:
            f = px.scatter(pd.DataFrame(pts), x='lon', y='lat', size='Cases', color='Cases', hover_name='STATION',
                           color_continuous_scale='RdYlGn_r', size_max=35)
            f.update_yaxes(scaleanchor="x", scaleratio=1)
            figs.append(_style(f, height=520, title="Station map (schematic, no map tiles needed)"))
    for summary, col, scale, title in [(cat_sum, 'DEPARTMENT', 'Blues', "Department-wise"),
                                       (error_sum, 'ERROR MAIN CATEGORY', 'Oranges', "Error main category"),
                                       (jur_sum, 'JURISDICTION', 'Teal', "Jurisdiction-wise")]:
        if not summary.empty:
            plot = summary.head(12).sort_values('Cases', ascending=True)
            f = px.bar(plot, x='Cases', y=col, orientation='h', text='Cases', color='Cases', color_continuous_scale=scale)
            f.update_traces(textposition='outside', cliponaxis=False)
            figs.append(_style(f, height=420, title=title, showlegend=False, coloraxis_showscale=False,
                               yaxis_title="", margin=dict(t=50, b=30, l=20, r=50)))

    cfg = {"displaylogo": False, "responsive": True}
    chart_html = "".join(
        f'<div class="card">{f.to_html(full_html=False, include_plotlyjs=(i == 0), config=cfg)}</div>'
        for i, f in enumerate(figs))
    rec = build_display_df(df)[0].head(MAX_DISPLAY_ROWS)
    rec_html = rec.to_html(index=False, escape=True, classes="tbl", table_id="rec", na_rep="")
    stn_html = station_summary.to_html(index=False, escape=True, classes="tbl")
    top = station_summary.iloc[0] if not station_summary.empty else None
    kpis = [("Total cases", f"{len(df):,}"),
            ("Top station", html_lib.escape(str(top['STATION'])) if top is not None else "N/A"),
            ("Top station cases", f"{int(top['Cases']):,}" if top is not None else "0"),
            ("Unique stations", f"{df['STATION'].nunique():,}")]
    kpi_html = "".join(f'<div class="kpi"><span>{k}</span><b>{v}</b></div>' for k, v in kpis)
    loaded = fmt_ist(status.get("loaded_at")) if status.get("loaded_at") else "unknown"
    note = "" if len(df) <= MAX_DISPLAY_ROWS else f" (first {MAX_DISPLAY_ROWS:,} of {len(df):,} rows)"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data-Logger Offline Report</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#e1f5fe;color:#0d1b2a;margin:0;padding:20px;}}
h1{{color:#01579b;margin:0 0 4px 0}} h2{{color:#0277bd;border-left:5px solid #0288d1;padding-left:10px}}
.sub{{color:#37474f;margin-bottom:16px}} .kpis{{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}}
.kpi{{background:#fff;border:1px solid #81d4fa;border-radius:14px;padding:12px 18px;min-width:150px}}
.kpi span{{display:block;color:#0277bd;font-weight:600;font-size:.9rem}} .kpi b{{font-size:1.6rem;color:#01579b}}
.card{{background:#fff;border:1px solid #81d4fa;border-radius:14px;padding:8px;margin:14px 0}}
.wrap{{overflow:auto;max-height:520px;background:#fff;border:1px solid #81d4fa;border-radius:12px}}
.tbl{{border-collapse:collapse;width:100%;font-size:.88rem}} .tbl th{{position:sticky;top:0;background:#0277bd;color:#fff;padding:6px 8px;text-align:left}}
.tbl td{{border-bottom:1px solid #e0e0e0;padding:5px 8px}} input{{padding:8px;width:min(420px,100%);margin:8px 0;border:1px solid #81d4fa;border-radius:8px}}
</style></head><body>
<h1>🚄 Data-Logger Exceptional Report</h1>
<div class="sub">Central Railway • Solapur Division • Safety Branch<br>
Generated {html_lib.escape(now_ist().strftime('%d %b %Y, %H:%M IST'))} by {html_lib.escape(str(user))} •
data as of {html_lib.escape(loaded)} • static snapshot — works offline</div>
<div class="kpis">{kpi_html}</div>
{chart_html}
<h2>Station summary</h2><div class="wrap">{stn_html}</div>
<h2>Detailed records{note}</h2>
<input id="q" placeholder="Search records...">
<div class="wrap">{rec_html}</div>
<script>document.getElementById('q').addEventListener('input',function(e){{var v=e.target.value.toLowerCase();
document.querySelectorAll('#rec tbody tr').forEach(function(r){{r.style.display=r.textContent.toLowerCase().indexOf(v)>-1?'':'none';}});}});</script>
</body></html>""".encode("utf-8")


# ====================== ANIMATION FIGURE ======================
def build_anim_fig(monthly, frame_duration, transition_duration):
    """Bars are RANKED per month (#1 = highest on the left), so the order really changes every frame."""
    fig = px.bar(
        monthly, x='Rank', y='Value', color='Value',
        animation_frame='Month', animation_group='STATION',
        category_orders={'Month': monthly['Month'].drop_duplicates().tolist()},
        range_y=[0, max(1, monthly['Value'].max()) * 1.18],
        range_x=[0.4, monthly['Rank'].max() + 0.6],
        color_continuous_scale='RdYlGn_r',
        labels={'Value': 'Cases', 'Rank': 'Rank (highest → lowest)'},
        hover_name='STATION', hover_data={'Rank': True, 'Value': ':,'},
        title="Monthly Cases by Station — Highest → Lowest (changes every month)",
        text='Label'
    )
    fig.update_traces(textposition='outside', cliponaxis=False)
    fig.update_layout(
        height=600, coloraxis_showscale=False, margin=dict(t=70, b=60), title_x=0.5,
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a',
        xaxis=dict(tickmode='linear', dtick=1)
    )
    try:
        args = fig.layout.updatemenus[0].buttons[0].args[1]
        args['frame']['duration'] = frame_duration
        args['transition']['duration'] = transition_duration
    except Exception:
        pass
    return fig


@st.cache_data(show_spinner=False)
def anim_html_bytes(monthly, frame_duration, transition_duration):
    fig = build_anim_fig(monthly, frame_duration, transition_duration)
    # include_plotlyjs=True embeds the library, so the downloaded file also works offline
    return fig.to_html(full_html=True, include_plotlyjs=True, config={'displaylogo': False, 'responsive': True}).encode('utf-8')

# ====================== MAIN APP ======================
if not st.session_state.logged_in:
    login_page()
else:
    if time.time() - st.session_state["_last_active"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["_last_active"] = time.time()
        logout()
    st.session_state["_last_active"] = time.time()

    with st.sidebar:
        st.header("🔧 Controls")
        force_offline = st.toggle("📴 Work offline (use saved snapshot)", key="force_offline")

    df_original, status = load_data(force_offline)
    if df_original is None:
        st.error("Could not load data, and no offline snapshot exists yet. Connect to the internet once so a snapshot can be saved.")
        st.stop()

    logo_bytes = get_logo_bytes()
    logo_src = ("data:image/png;base64," + base64.b64encode(logo_bytes).decode()) if logo_bytes else IR_LOGO_URL

    # Watermark
    st.markdown(f"""
    <div class="watermark">
        <img src="{logo_src}" alt="Central Railway Logo Watermark">
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([3, 3, 1])
    with col2:
        if logo_bytes:
            st.image(logo_bytes, width=220)
        elif status["mode"] == "live":
            st.image(IR_LOGO_URL, width=220)

    # ===== CLEAN AESTHETIC DRISHTI HEADER =====
    st.markdown('<div class="drishti-title">Data-Logger</div>', unsafe_allow_html=True)
    st.markdown('<div class="drishti-line"></div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="drishti-fullform">
        <b>Data-Logger Exceptional Report</b>
    </div>
    """, unsafe_allow_html=True)

    # Moving trains
    st.markdown("""
    <div class="train-emoji-container">
        <div class="train-track">
            🚄 🚄 🚄 🚄
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        '<p class="brand-line">Central Railway &nbsp;•&nbsp; Solapur Division &nbsp;•&nbsp; Safety Branch</p>',
        unsafe_allow_html=True
    )
    st.caption(f"**Logged in as:** {st.session_state.user_name}")
    st.divider()

    with st.sidebar:
        if status["mode"] == "live":
            st.markdown('<span class="status-pill status-live">🟢 Live data</span>', unsafe_allow_html=True)
            st.caption(f"Updated {fmt_ist(status.get('loaded_at'))} • {len(df_original):,} rows")
        else:
            why = "by choice" if status.get("reason") == "forced" else "— could not reach Google Sheets"
            st.markdown('<span class="status-pill status-off">🟠 Offline snapshot</span>', unsafe_allow_html=True)
            st.caption(f"Saved {fmt_ist(status.get('loaded_at'))} {why} • {len(df_original):,} rows")
            if status.get("reason") == "unreachable":
                st.caption("Retrying automatically every minute.")
        if st.button("🔄 Refresh Data", type="primary", disabled=force_offline, **STRETCH):
            refresh_data()
        use_tiles = st.checkbox("Load online map tiles", value=(status["mode"] == "live"),
                                help="Turn off when there is no internet; station markers still work.")
        st.divider()
        if st.button("🚪 Logout", **STRETCH):
            logout()

    # ====================== LIVE FILTERS ======================
    def _opts(col):
        return sorted(df_original[col].dropna().astype(str).unique().tolist()) if col in df_original.columns else []

    st.markdown("### 🔍 Live Filters")
    col_f1 = st.columns([2, 2, 2, 2])
    with col_f1[0]:
        stations = _opts('STATION')
        prune_selection("stn_key", stations)
        selected_stations = st.multiselect("STATION", options=stations, key="stn_key")
    with col_f1[1]:
        errors = _opts('ERROR MAIN CATEGORY')
        prune_selection("err_key", errors)
        selected_errors = st.multiselect("ERROR MAIN CATEGORY", options=errors, key="err_key")
    with col_f1[2]:
        categories = _opts('DEPARTMENT')
        prune_selection("cat_key", categories)
        selected_categories = st.multiselect("DEPARTMENT", options=categories, key="cat_key")
    with col_f1[3]:
        months = month_options(df_original)
        prune_selection("month_key", months)
        selected_months = st.multiselect("MONTH", options=months, key="month_key")

    col_f2 = st.columns([2, 2, 2])
    with col_f2[0]:
        fault_list = _opts('DL FAULT MESSAGE')
        prune_selection("fault_key", fault_list)
        selected_fault = st.multiselect("DL FAULT MESSAGE", options=fault_list, key="fault_key")
    with col_f2[1]:
        remark_list = _opts('REMARKS GIVEN BY S&T')
        prune_selection("remark_key", remark_list)
        selected_remark = st.multiselect("REMARKS GIVEN BY S&T", options=remark_list, key="remark_key")
    with col_f2[2]:
        jurisdictions = _opts('JURISDICTION')
        prune_selection("jur_key", jurisdictions)
        selected_jurisdictions = st.multiselect("JURISDICTION", options=jurisdictions, key="jur_key")

    valid_dates = df_original['DATE'].dropna()
    data_min = valid_dates.min().date() if not valid_dates.empty else now_ist().date()
    data_max = valid_dates.max().date() if not valid_dates.empty else now_ist().date()
    sync_date_bounds(data_min, data_max)

    col_date = st.columns([2, 2, 1])
    with col_date[0]:
        from_date = st.date_input("FROM DATE", key="from_date_key", min_value=data_min, max_value=data_max)
    with col_date[1]:
        to_date = st.date_input("TO DATE", key="to_date_key", min_value=data_min, max_value=data_max)
    with col_date[2]:
        st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
        st.button("↺ Reset filters", on_click=reset_filters, **STRETCH)
    if from_date > to_date:
        st.warning("FROM DATE is after TO DATE — the two dates were swapped.")
        from_date, to_date = to_date, from_date

    if st.session_state.map_selected_station:
        b1, b2 = st.columns([5, 1])
        with b1:
            st.info(f"📍 Map station filter is active: **{st.session_state.map_selected_station}** — it applies to every tab.")
        with b2:
            if st.button("Clear", key="clear_map_top", **STRETCH):
                st.session_state.map_selected_station = None
                st.session_state["_last_map_click"] = None
                st.session_state["_map_epoch"] += 1
                st.rerun()

    st.divider()

    def apply_category_filters(df, include_map_selection=True):
        out = df
        if selected_stations and 'STATION' in out.columns:
            out = out[out['STATION'].isin(selected_stations)]
        if selected_errors and 'ERROR MAIN CATEGORY' in out.columns:
            out = out[out['ERROR MAIN CATEGORY'].isin(selected_errors)]
        if selected_categories and 'DEPARTMENT' in out.columns:
            out = out[out['DEPARTMENT'].isin(selected_categories)]
        if selected_fault and 'DL FAULT MESSAGE' in out.columns:
            out = out[out['DL FAULT MESSAGE'].isin(selected_fault)]
        if selected_remark and 'REMARKS GIVEN BY S&T' in out.columns:
            out = out[out['REMARKS GIVEN BY S&T'].isin(selected_remark)]
        if selected_jurisdictions and 'JURISDICTION' in out.columns:
            out = out[out['JURISDICTION'].isin(selected_jurisdictions)]
        if include_map_selection and st.session_state.map_selected_station and 'STATION' in out.columns:
            out = out[out['STATION'] == st.session_state.map_selected_station]
        return out

    def apply_date_month_filters(df):
        lo = pd.Timestamp(from_date)
        hi = pd.Timestamp(to_date) + pd.Timedelta(days=1)
        out = df[(df['DATE'] >= lo) & (df['DATE'] < hi)]
        if selected_months and 'MONTH' in out.columns:
            out = out[out['MONTH'].isin(selected_months)]
        return out

    forecast_base_df = apply_category_filters(df_original)
    filtered_df = apply_date_month_filters(forecast_base_df)
    # The map itself is built WITHOUT the clicked-station filter, so every station stays visible/clickable.
    filtered_for_map = apply_date_month_filters(apply_category_filters(df_original, include_map_selection=False))
    map_station_summary = compute_station_summary(filtered_for_map)

    # ---- Computed ONCE and reused everywhere below ----
    station_summary = compute_station_summary(filtered_df)

    cat_sum = pd.DataFrame()
    error_sum = pd.DataFrame()
    jur_sum = pd.DataFrame()
    if not filtered_df.empty:
        if 'DEPARTMENT' in filtered_df.columns:
            cat_sum = filtered_df.groupby('DEPARTMENT').size().reset_index(name='Cases').sort_values('Cases', ascending=False)
        if 'ERROR MAIN CATEGORY' in filtered_df.columns:
            error_sum = filtered_df.groupby('ERROR MAIN CATEGORY').size().reset_index(name='Cases').sort_values('Cases', ascending=False)
        if 'JURISDICTION' in filtered_df.columns:
            jur_sum = filtered_df.groupby('JURISDICTION').size().reset_index(name='Cases').sort_values('Cases', ascending=False)

    filter_sig = repr((selected_stations, selected_errors, selected_categories, selected_months, selected_fault,
                       selected_remark, selected_jurisdictions, str(from_date), str(to_date),
                       st.session_state.map_selected_station, len(filtered_df), status.get("loaded_at")))

    st.divider()

    tab_overview, tab_forecast, tab_map = st.tabs(["📊 Overview Dashboard", "🔮 Forecast (3 Months)", "🗺️ Map View"])

    # ====================== OVERVIEW TAB ======================
    with tab_overview:
        st.subheader("📊 Overview Dashboard")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Cases", f"{len(filtered_df):,}")
        with c2:
            top_station = station_summary.iloc[0]['STATION'] if not station_summary.empty else "N/A"
            st.metric("⚠️ Top Station", top_station)
        with c3:
            top_cases = int(station_summary.iloc[0]['Cases']) if not station_summary.empty else 0
            st.metric("Top Station Cases", f"{top_cases:,}")
        with c4:
            st.metric("Unique Stations", f"{filtered_df['STATION'].nunique() if 'STATION' in filtered_df.columns else 0}")

        st.markdown("---")

        col_g1, col_g2 = st.columns([3, 2])
        with col_g1:
            st.markdown('<p class="section-header">Top 15 Stations by Cases</p>', unsafe_allow_html=True)
            if not station_summary.empty:
                top15 = station_summary.head(15)
                fig = px.bar(top15, x='STATION', y='Cases', text='Cases', color='Cases', color_continuous_scale='RdYlGn_r')
                fig.update_layout(height=480, xaxis_tickangle=45, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
                st.plotly_chart(fig, **STRETCH)
        with col_g2:
            st.markdown('<p class="section-header">Station Summary</p>', unsafe_allow_html=True)
            if not station_summary.empty:
                render_station_summary_table(station_summary)

        st.markdown("---")
        st.markdown('<p class="section-header">📊 Distribution Charts</p>', unsafe_allow_html=True)

        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            st.markdown("**Department-wise**")
            if not cat_sum.empty:
                dept_plot = cat_sum.sort_values('Cases', ascending=True)
                fig_dept = px.bar(dept_plot, x='Cases', y='DEPARTMENT', orientation='h', text='Cases', color='Cases', color_continuous_scale='Blues')
                fig_dept.update_traces(textposition='outside', cliponaxis=False)
                fig_dept.update_layout(height=400, showlegend=False, coloraxis_showscale=False, xaxis_title="Cases", yaxis_title="", margin=dict(t=30, b=30, l=20, r=50), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
                st.plotly_chart(fig_dept, **STRETCH)
            else:
                st.info("No Department data")
        with col_c2:
            st.markdown("**Error Main Category**")
            if not error_sum.empty:
                err_plot = error_sum.head(12).sort_values('Cases', ascending=True)
                fig_err = px.bar(err_plot, x='Cases', y='ERROR MAIN CATEGORY', orientation='h', text='Cases', color='Cases', color_continuous_scale='Oranges')
                fig_err.update_traces(textposition='outside', cliponaxis=False)
                fig_err.update_layout(height=400, showlegend=False, coloraxis_showscale=False, xaxis_title="Cases", yaxis_title="", margin=dict(t=30, b=30, l=20, r=50), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
                st.plotly_chart(fig_err, **STRETCH)
            else:
                st.info("No Error data")
        with col_c3:
            st.markdown("**Jurisdiction-wise**")
            if not jur_sum.empty:
                jur_plot = jur_sum.head(12).sort_values('Cases', ascending=True)
                fig_jur = px.bar(jur_plot, x='Cases', y='JURISDICTION', orientation='h', text='Cases', color='Cases', color_continuous_scale='Teal')
                fig_jur.update_traces(textposition='outside', cliponaxis=False)
                fig_jur.update_layout(height=400, showlegend=False, coloraxis_showscale=False, xaxis_title="Cases", yaxis_title="", margin=dict(t=30, b=30, l=20, r=50), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
                st.plotly_chart(fig_jur, **STRETCH)
            else:
                st.info("No Jurisdiction data")

        # ====================== ANIMATED TIME SERIES ======================
        st.markdown("---")
        st.markdown('<p class="section-header">🎬 Animated Monthly Cases by Station (Highest → Lowest every month)</p>', unsafe_allow_html=True)

        if filtered_df.empty or 'STATION' not in filtered_df.columns or 'DATE' not in filtered_df.columns:
            st.warning("Not enough data for animation.")
        else:
            anim_df = filtered_df.dropna(subset=['DATE', 'STATION']).copy()

            col_anim1, col_anim2 = st.columns([2, 2])
            with col_anim1:
                top_n_anim = st.slider("Show Top N stations", 5, 25, 12, key="anim_topn")
            with col_anim2:
                anim_speed = st.select_slider("Animation Speed", options=["Very Slow", "Slow", "Normal", "Fast"], value="Slow", key="anim_speed")

            speed_map = {"Very Slow": 1800, "Slow": 1400, "Normal": 1000, "Fast": 700}
            frame_duration = speed_map[anim_speed]
            transition_duration = int(frame_duration * 0.55)

            monthly = anim_df.groupby(['STATION', pd.Grouper(key='DATE', freq='MS')]).size().reset_index(name='Value')
            top_stations = (
                monthly.groupby('STATION')['Value']
                .sum()
                .sort_values(ascending=False)
                .head(top_n_anim)
                .index
                .tolist()
            )
            if not top_stations or monthly.empty:
                st.info("No data available for animation.")
            else:
                all_months = pd.date_range(anim_df['DATE'].min().to_period('M').to_timestamp(),
                                           anim_df['DATE'].max().to_period('M').to_timestamp(), freq='MS')
                grid = pd.MultiIndex.from_product([top_stations, all_months], names=['STATION', 'DATE'])
                # zero-filled grid: stations no longer pop in/out of the chart in months with no cases
                monthly = monthly.set_index(['STATION', 'DATE'])['Value'].reindex(grid, fill_value=0).reset_index()
                monthly['Month'] = monthly['DATE'].dt.strftime('%b %Y')
                monthly = monthly.sort_values(['DATE', 'Value', 'STATION'], ascending=[True, False, True])
                monthly['Rank'] = monthly.groupby('DATE').cumcount() + 1
                monthly['Label'] = monthly['STATION'] + "<br>" + monthly['Value'].map("{:,}".format)
                monthly = monthly[['STATION', 'DATE', 'Month', 'Value', 'Rank', 'Label']]

                fig_anim = build_anim_fig(monthly, frame_duration, transition_duration)
                st.plotly_chart(fig_anim, config={'displaylogo': False}, **STRETCH)
                st.caption(f"Current speed: **{anim_speed}** • Bars are ranked Highest → Lowest every month (station name shown on each bar)")

                st.markdown("")
                col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
                with col_dl2:
                    st.download_button(
                        label="⬇️ Download Animation (Interactive HTML)",
                        data=anim_html_bytes(monthly, frame_duration, transition_duration),
                        file_name=f"DRISHTI_Animation_{now_ist().strftime('%Y%m%d_%H%M')}.html",
                        mime="text/html",
                        type="primary",
                        key="anim_download",
                        **STRETCH
                    )

        # ====================== SUMMARY TABLES ======================
        st.markdown("---")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            if not cat_sum.empty:
                st.markdown('<p class="section-header">DEPARTMENT</p>', unsafe_allow_html=True)
                st.dataframe(cat_sum.style.format({"Cases": "{:,}"}), hide_index=True, **STRETCH)
        with col_s2:
            if not error_sum.empty:
                st.markdown('<p class="section-header">ERROR MAIN CATEGORY</p>', unsafe_allow_html=True)
                st.dataframe(error_sum.style.format({"Cases": "{:,}"}), hide_index=True, **STRETCH)
        with col_s3:
            if not jur_sum.empty:
                st.markdown('<p class="section-header">JURISDICTION</p>', unsafe_allow_html=True)
                st.dataframe(jur_sum.style.format({"Cases": "{:,}"}), hide_index=True, **STRETCH)

        # ====================== OFFLINE DASHBOARD (NEW) ======================
        st.markdown("---")
        st.markdown('<p class="section-header">📴 Offline Dashboard</p>', unsafe_allow_html=True)
        st.caption("One HTML file with the charts, tables and a search box. Open it in any browser — no internet, no server.")
        col_o1, col_o2, col_o3 = st.columns([1, 3, 1])
        with col_o2:
            if st.button("⚙️ Prepare offline dashboard (HTML)", key="prep_offline_html", **STRETCH):
                with st.spinner("Building offline dashboard..."):
                    st.session_state["_prepared"]["offline_html"] = (
                        build_offline_html(filtered_df, station_summary, cat_sum, error_sum, jur_sum, status, st.session_state.user_name),
                        filter_sig)
            prepared = st.session_state["_prepared"].get("offline_html")
            if prepared:
                if prepared[1] == filter_sig:
                    st.download_button("⬇️ Download Offline Dashboard (HTML)", data=prepared[0],
                                       file_name=f"DataLogger_Offline_{now_ist().strftime('%Y%m%d_%H%M')}.html",
                                       mime="text/html", type="primary", key="dl_offline_html", **STRETCH)
                else:
                    st.info("Filters changed since this file was prepared — click Prepare again.")

        # Detailed Records + Export (shared helper)
        st.markdown("---")
        render_detailed_records_section(
            filtered_df,
            extra_sheets=[
                ('Station_Summary', station_summary),
                ('Error_Summary', error_sum),
                ('Category_Summary', cat_sum),
                ('Jurisdiction_Summary', jur_sum),
            ],
            file_prefix="DRISHTI_Report",
            button_label="⬇️ Download Professional Excel Report",
            button_key="overview_download"
        )

        # ====================== DATA QUALITY (NEW) ======================
        with st.expander("🩺 Data Quality Check"):
            all_stations = sorted(df_original['STATION'].dropna().unique().tolist())
            no_coords = [s for s in all_stations if match_station_coords(s) is None]
            unclassified = df_original[df_original['JURISDICTION'] == "Unclassified"]
            q1, q2, q3, q4 = st.columns(4)
            q1.metric("Rows loaded", f"{len(df_original):,}")
            q2.metric("Rows with bad/blank DATE", f"{status.get('bad_dates', 0) + status.get('blank_dates', 0):,}")
            q3.metric("Unclassified rows", f"{len(unclassified):,}")
            q4.metric("Stations without coordinates", f"{len(no_coords)}")
            if status.get("missing_columns"):
                st.warning("Columns missing in the sheet (treated as empty): " + ", ".join(status["missing_columns"]))
            if status.get("bad_dates"):
                st.warning(f"{status['bad_dates']} row(s) have a DATE that could not be read (dates are read day-first, dd/mm/yyyy); "
                           "they are excluded from date-based views.")
            if status.get("blank_dates"):
                st.info(f"{status['blank_dates']} row(s) have no DATE and are excluded from date-based views.")
            if no_coords:
                st.markdown("**Stations missing from the coordinate table (not shown on the map):** " + ", ".join(no_coords))
            if not unclassified.empty:
                st.markdown("**Unclassified station / department combinations**")
                combos = unclassified.groupby(['STATION', 'DEPARTMENT'], dropna=False).size().reset_index(name='Rows').sort_values('Rows', ascending=False)
                st.dataframe(combos.fillna("(blank)"), hide_index=True, **STRETCH)
            gaps = []
            for s in all_stations:
                key_norm = _normalize_key(s)
                missing = [name for name, mp in JURISDICTION_TABLES.items() if key_norm not in mp]
                if missing:
                    gaps.append({"STATION": s, "Not in jurisdiction table(s)": ", ".join(missing)})
            if gaps:
                st.markdown("**Stations missing from jurisdiction tables**")
                st.dataframe(pd.DataFrame(gaps), hide_index=True, **STRETCH)
            if not (no_coords or len(unclassified) or gaps or status.get("bad_dates")):
                st.success("No data-quality problems found.")

    # ====================== FORECAST TAB ======================
    with tab_forecast:
        st.subheader("🔮 Forecast — next 1 to 3 months (Number of Cases)")
        st.caption("Uses complete history. All other filters apply.")

        fc1, fc2, fc3 = st.columns([2, 2, 2])
        with fc1:
            horizon = st.slider("Months ahead", min_value=1, max_value=3, value=3, key="fc_horizon")
        with fc2:
            level = st.selectbox("Break-up by", ["Division total (no break-up)", "Station", "Department", "Jurisdiction", "Error Main Category"], key="fc_level")
        with fc3:
            top_n = st.number_input("Top N groups", min_value=3, max_value=25, value=10, step=1, key="fc_topn")

        global_month_index = get_global_month_index(forecast_base_df)
        hist_raw = build_monthly_series(forecast_base_df, full_index=global_month_index)
        hist = trim_incomplete_current_month(hist_raw)
        trimmed_partial_month = len(hist) < len(hist_raw)

        if hist.empty:
            st.warning("Not enough dated records to build a forecast.")
        else:
            if trimmed_partial_month:
                st.caption(f"ℹ️ **{hist_raw.index[-1].strftime('%B %Y')}** is still in progress, so it's excluded from training.")
            fc, method, resid = forecast_series(hist, horizon)
            wape = backtest_wape(hist, horizon=min(3, max(1, len(hist) // 4)))

            k1, k2, k3, k4 = st.columns(4)
            with k1:
                st.metric("Months of history", f"{len(hist)}")
            with k2:
                st.metric("Last month Cases", f"{int(hist.iloc[-1]):,}")
            with k3:
                st.metric(f"Next {horizon} months (predicted)", f"{int(fc.sum()):,}")
            with k4:
                change = ((fc.mean() - hist.iloc[-1]) / hist.iloc[-1] * 100) if hist.iloc[-1] else 0
                st.metric("vs last month", f"{change:+.1f}%")

            st.info(f"**Model used:** {method}" + (f"  •  **Back-test WAPE:** {wape:.1f}%" if wape is not None else ""))

            anchor_x = [hist.index[-1]] + list(fc.index)
            anchor_y = [float(hist.iloc[-1])] + [float(v) for v in fc.values]
            margins = [0.0] + [1.96 * resid * np.sqrt(i + 1) for i in range(len(fc))]
            upper = [y + m for y, m in zip(anchor_y, margins)]
            lower = [max(0.0, y - m) for y, m in zip(anchor_y, margins)]

            fig_fc = go.Figure()
            fig_fc.add_trace(go.Scatter(x=list(anchor_x) + list(anchor_x)[::-1], y=upper + lower[::-1], fill='toself', fillcolor='rgba(2, 136, 209, 0.18)', line=dict(color='rgba(0,0,0,0)'), hoverinfo='skip', name='≈95% range'))
            fig_fc.add_trace(go.Scatter(x=hist.index, y=hist.values, mode='lines+markers', name='Actual', line=dict(color='#0277bd', width=3), marker=dict(size=8)))
            fig_fc.add_trace(go.Scatter(x=anchor_x, y=anchor_y, mode='lines+markers+text', name='Forecast', line=dict(color='#0288d1', width=3, dash='dash'), marker=dict(size=10), text=[""] + [f"{int(v):,}" for v in fc.values], textposition='top center'))
            fig_fc.update_layout(height=470, hovermode='x unified', xaxis_title="Month", yaxis_title="Monthly Cases", legend=dict(orientation='h', y=1.12), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
            st.plotly_chart(fig_fc, **STRETCH)

            fc_table = pd.DataFrame({
                "Month": [d.strftime('%B %Y') for d in fc.index],
                "Predicted Cases": [int(v) for v in fc.values],
                "Lower estimate": [int(max(0, v - 1.96 * resid * np.sqrt(i + 1))) for i, v in enumerate(fc.values)],
                "Upper estimate": [int(v + 1.96 * resid * np.sqrt(i + 1)) for i, v in enumerate(fc.values)],
            })
            st.markdown('<p class="section-header">Predicted values</p>', unsafe_allow_html=True)
            st.dataframe(fc_table.style.format({"Predicted Cases": "{:,}", "Lower estimate": "{:,}", "Upper estimate": "{:,}"}), hide_index=True, **STRETCH)
            st.caption("The range is an approximation based on past fit errors — a guide, not a guarantee.")

            group_map = {"Station": "STATION", "Department": "DEPARTMENT", "Jurisdiction": "JURISDICTION", "Error Main Category": "ERROR MAIN CATEGORY"}
            group_table = pd.DataFrame()
            if level in group_map:
                gcol = group_map[level]
                st.markdown("---")
                st.markdown(f'<p class="section-header">Forecast by {level} (top {int(top_n)})</p>', unsafe_allow_html=True)
                with st.spinner("Fitting models..."):
                    group_table = forecast_by_group(forecast_base_df, gcol, horizon, int(top_n), full_index=global_month_index)
                if group_table.empty:
                    st.info("Not enough history for group-wise forecast.")
                else:
                    num_cols = [c for c in group_table.columns if c not in (gcol, "Model")]
                    gstyler = group_table.style.format({c: "{:,}" for c in num_cols})
                    try:
                        gstyler = gstyler.background_gradient(subset=["Forecast total"], cmap='YlOrRd')
                    except Exception:
                        pass
                    st.dataframe(gstyler, hide_index=True, **STRETCH)
                    plot_df = group_table.sort_values("Forecast total", ascending=True)
                    fig_grp = px.bar(plot_df, x="Forecast total", y=gcol, orientation='h', text="Forecast total", color="Forecast total", color_continuous_scale='RdYlGn_r')
                    fig_grp.update_traces(textposition='outside', cliponaxis=False)
                    fig_grp.update_layout(height=480, coloraxis_showscale=False, xaxis_title=f"Predicted Cases (next {horizon} months)", yaxis_title="", margin=dict(t=30, b=30, l=20, r=60), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='#0d1b2a')
                    st.plotly_chart(fig_grp, **STRETCH)

            st.markdown("---")
            col_fb1, col_fb2, col_fb3 = st.columns([1, 3, 1])
            with col_fb2:
                monthly_history_df = pd.DataFrame({"Month": hist.index.strftime('%b %Y'), "Cases": hist.values.astype(int)})
                st.download_button(
                    label="⬇️ Download Forecast Report",
                    data=build_excel_bytes((("Division_Forecast", fc_table), ("Monthly_History", monthly_history_df), ("Group_Forecast", group_table))),
                    file_name=f"DRISHTI_Forecast_{now_ist().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime=XLSX_MIME,
                    type="primary",
                    key="forecast_download",
                    **STRETCH
                )

    # ====================== MAP TAB ======================
    with tab_map:
        st.subheader("🗺️ Interactive Map View - Click on Station to Filter")

        if st.session_state.map_selected_station:
            col_clear1, col_clear2 = st.columns([1, 5])
            with col_clear1:
                if st.button("🔄 Clear Station Selection", type="secondary", key="clear_map_tab", **STRETCH):
                    st.session_state.map_selected_station = None
                    st.session_state["_last_map_click"] = None
                    st.session_state["_map_epoch"] += 1   # remount the map so its old 'last click' is forgotten
                    st.rerun()
            st.success(f"📍 Currently viewing: **{st.session_state.map_selected_station}**")

        st.markdown("<br>", unsafe_allow_html=True)
        col_m1, col_m2 = st.columns([3, 2])

        with col_m1:
            if filtered_for_map.empty or 'STATION' not in filtered_for_map.columns:
                st.warning("No data available.")
            else:
                map_data, unmatched = [], []
                for _, row in map_station_summary.iterrows():
                    coords = match_station_coords(row['STATION'])
                    if coords:
                        map_data.append({'STATION': row['STATION'], 'Cases': row['Cases'], 'lat': coords['lat'], 'lon': coords['lon']})
                    else:
                        unmatched.append(row['STATION'])
                map_df = pd.DataFrame(map_data)
                if unmatched:
                    st.warning(f"{len(unmatched)} station(s) have no coordinates and are not on the map: {', '.join(unmatched)}")

                if not map_df.empty:
                    with st.spinner("Rendering map..."):
                        m = folium.Map(location=[17.85, 75.80], zoom_start=7.2, tiles=None, control_scale=True)
                        if use_tiles:
                            try:
                                carto_key = st.secrets["carto"]["api_key"]
                            except Exception:
                                carto_key = None   # falls back to OpenStreetMap instead of crashing the tab
                            if carto_key:
                                folium.TileLayer(tiles=f"https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png?key={carto_key}", name="🗺️ Light Base", attr='© OpenStreetMap © CARTO', control=True, subdomains="abcd", max_zoom=20).add_to(m)
                            folium.TileLayer("OpenStreetMap", name="🌍 OpenStreetMap", control=True, show=not carto_key).add_to(m)
                            folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", attr="Esri", name="🌐 Satellite", control=True, show=False).add_to(m)
                            folium.LayerControl(position="topright", collapsed=False).add_to(m)
                        else:
                            st.caption("📴 Offline map: station markers only (no base-map tiles).")
                        Fullscreen().add_to(m)

                        selected_now = st.session_state.map_selected_station
                        for _, row in map_df.iterrows():
                            cases = int(row['Cases'])
                            color = "green" if cases < 50 else "orange" if cases <= 150 else "darkred"
                            radius = 8 + min(cases / 10, 25)
                            folium.CircleMarker(location=[row['lat'], row['lon']], radius=radius, popup=f"<h4>{html_lib.escape(str(row['STATION']))}</h4><b>Total Cases:</b> {cases:,}", tooltip=f"{row['STATION']} ({cases:,})", color=color, fill=True, fill_color=color, fill_opacity=0.85, weight=2).add_to(m)
                            if row['STATION'] == selected_now:   # highlight ring on the selected station
                                folium.CircleMarker(location=[row['lat'], row['lon']], radius=radius + 6, color="#0d47a1", weight=4, fill=False, interactive=False).add_to(m)

                        m.get_root().html.add_child(folium.Element(
                            "<div style='position:fixed;bottom:24px;left:24px;z-index:9999;background:#fff;padding:8px 12px;"
                            "border:1px solid #81d4fa;border-radius:8px;font:13px sans-serif'><b>Cases</b><br>"
                            "<span style='color:green'>●</span> &lt; 50 &nbsp;<span style='color:orange'>●</span> 50–150 &nbsp;"
                            "<span style='color:darkred'>●</span> &gt; 150</div>"))

                        # Stable key: the map keeps its zoom/position. Station is identified from the clicked
                        # marker's tooltip (not "nearest station to the click point").
                        map_return = st_folium(m, height=680, key=f"folium_map_{st.session_state['_map_epoch']}",
                                               returned_objects=["last_object_clicked_tooltip"], use_container_width=True)
                        tip = (map_return or {}).get("last_object_clicked_tooltip")
                        if tip and tip != st.session_state["_last_map_click"]:
                            st.session_state["_last_map_click"] = tip
                            name = str(tip).rsplit(" (", 1)[0].strip()
                            if name in set(map_df['STATION']) and st.session_state.map_selected_station != name:
                                st.session_state.map_selected_station = name
                                st.rerun()

        with col_m2:
            st.subheader("Station Summary")
            if not map_station_summary.empty:
                render_station_summary_table(map_station_summary)
            st.markdown("---")
            st.subheader("Jurisdiction Summary")
            if not jur_sum.empty:
                st.dataframe(jur_sum.style.format({"Cases": "{:,}"}), hide_index=True, **STRETCH)

        st.markdown("---")
        render_detailed_records_section(
            filtered_df,
            extra_sheets=[('Jurisdiction_Summary', jur_sum)],
            file_prefix="DRISHTI_Map_Report",
            button_label="⬇️ Download Map Filtered Report",
            button_key="map_download"
        )

    st.caption("🚄 Data-Logger | Safety Branch | Central Railway, Solapur Division")
