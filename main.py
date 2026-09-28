
import base64
import hashlib
import hmac
import html as html_lib
import json
import logging
import re
import time
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

import folium
import gspread
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Fullscreen
from streamlit_folium import st_folium

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
    initial_sidebar_state="expanded",
)


def _st_version():
    try:
        return tuple(int(p) for p in st.__version__.split(".")[:2])
    except Exception:
        return (1, 0)


# `use_container_width` is deprecated in newer Streamlit; `width="stretch"` replaces it.
STRETCH = {"width": "stretch"} if _st_version() >= (1, 50) else {"use_container_width": True}

# ====================== CONSTANTS ======================
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
MAX_DISPLAY_ROWS = 5000

COL_DATE = "DATE"
COL_STATION = "STATION"
COL_DEPT = "DEPARTMENT"
COL_ERROR = "ERROR MAIN CATEGORY"
COL_FAULT = "DL FAULT MESSAGE"
COL_REMARK = "REMARKS GIVEN BY S&T"
COL_JUR = "JURISDICTION"
COL_MONTH = "MONTH"
COL_YM = "YEAR_MONTH"
REQUIRED_COLUMNS = [COL_DATE, COL_STATION]
EXPECTED_COLUMNS = [COL_DATE, COL_STATION, COL_DEPT, COL_ERROR, COL_FAULT, COL_REMARK]

PREFERRED_ORDER = [COL_DATE, COL_STATION, COL_DEPT, COL_JUR, COL_ERROR, COL_FAULT, COL_REMARK]

# ====================== SECRETS ======================
try:
    SHEET_ID = st.secrets["google_sheets"]["sheet_id"]
    SHEET_NAME = st.secrets["google_sheets"]["sheet_name"]
    USERS = st.secrets["users"]
except Exception:
    st.error("⚠️ Secrets not configured properly. Please check .streamlit/secrets.toml")
    st.stop()

# ====================== STATION COORDINATES ======================
STATION_COORDS = {
    "WADI": (17.05304, 76.99205), "SDB": (17.12207, 76.94370), "MR": (17.19988, 76.90242),
    "HQR": (17.25833, 76.87213), "KLBG": (17.31464, 76.82540), "TJSP": (17.38156, 76.83079),
    "BBD": (17.33694, 76.77927), "SVG": (17.33968, 76.71140), "HHD": (17.35270, 76.64675),
    "GUR": (17.34085, 76.58960), "KUI": (17.35748, 76.47050), "DUD": (17.36263, 76.38023),
    "NGS": (17.42920, 76.18297), "BOT": (17.39512, 76.25532), "AKOR": (17.45054, 76.13879),
    "TLT": (17.52915, 76.03602), "HG STN": (17.56546, 75.98943), "HG-A": (17.55592, 76.00138),
    "HG": (17.56546, 75.98943), "TKWD": (17.61537, 75.93345), "SUR": (17.66462, 75.89344),
    "BALE": (17.67604, 75.84577), "PK": (17.72560, 75.77920), "MVE": (17.74204, 75.70628),
    "MO": (17.80578, 75.67563), "MKPT": (17.87635, 75.63508), "AAG": (17.92858, 75.60831),
    "WKA": (17.98027, 75.58850), "MA": (18.03029, 75.54657), "WDS": (18.06648, 75.48892),
    "KWV": (18.09222, 75.41722), "DHS": (18.12956, 75.33425), "KEM": (18.17685, 75.27469),
    "BLNI": (18.21058, 75.20718), "JEUR": (18.26086, 75.16234), "PPJ": (18.29156, 75.09803),
    "WSB": (18.28030, 75.01623), "KEU": (18.29010, 74.95250), "JNTR": (18.32495, 74.87761),
    "BGVN": (18.31689, 74.77495), "MLM": (18.36895, 74.72444), "BRB": (18.40792, 74.64901),
    "MRJ": (16.81964, 74.63885), "BLWD": (16.81645, 74.68488), "BDK": (16.82261, 74.73243),
    "ARAG": (16.82292, 74.78886), "BLNK": (16.85188, 74.87035), "SGRE": (16.89300, 74.90379),
    "AGDL": (16.95512, 74.92175), "KVK": (16.99345, 74.93640), "LNP": (17.08409, 74.96649),
    "DLGN": (17.12249, 74.99090), "GLV": (17.17278, 75.05616), "JTRD": (17.21810, 75.11167),
    "MSDG": (17.26977, 75.13869), "JVA": (17.29927, 75.15831), "WSD": (17.37773, 75.14797),
    "SGLA": (17.43693, 75.18842), "BMNI": (17.51068, 75.23653), "BHLI": (17.58889, 75.27444),
    "PVR": (17.66895, 75.31975), "BBV": (17.76905, 75.39792), "AHI": (17.84503, 75.40339),
    "MLB": (17.91702, 75.40538), "PSS": (18.00086, 75.38990), "LAUL": (18.03356, 75.39533),
    "CNHL": (18.09988, 75.45785), "MGO": (18.10960, 75.49542), "SEI": (18.14939, 75.59026),
    "UPI": (18.17995, 75.63570), "BTW": (18.24097, 75.71805), "KCB": (18.27906, 75.78167),
    "PJR": (18.28395, 75.86723), "DRSV": (18.24788, 76.02288), "YSI": (18.31761, 75.97701),
    "KRMD": (18.37189, 76.04928), "DKY": (18.35369, 76.10312), "TER": (18.35267, 76.15005),
    "PCP": (18.35842, 76.19327), "MRX": (18.38027, 76.25112), "NEI": (18.38737, 76.31091),
    "OSA": (18.37848, 76.40761), "HGL": (18.39020, 76.49592), "LUR": (18.42943, 76.55608),
    "BANL": (18.44605, 76.67840), "GANI": (18.47927, 76.76395), "DD": (18.46377, 74.57929),
}

# ====================== JURISDICTION MAPPINGS ======================
# Written as {jurisdiction: [stations]} (easier to maintain), then inverted below.
_ENGG_GROUPS = {
    "ADEN KLBG": ["WADI", "SDB", "MR", "HQR", "KLBG", "BBD", "SVG", "HHD", "GUR", "KUI", "TJSP", "GDGN", "SBD"],
    "ADEN S SUR": ["AKOR", "BOT", "DUD", "HG", "NGS", "TKWD", "TLT", "HG STN", "HG-A"],
    "Sr.ADEN N SUR": ["AAG", "BALE", "MA", "MKPT", "MO", "MVE", "PK", "SUR", "WDS", "WKA", "MOHOL", "PAKNI"],
    "Sr.ADEN KWV BG": ["BGVN", "BLNI", "BRB", "DHS", "JEUR", "JNTR", "KEM", "KWV", "MLM", "PPJ", "WSB", "KEU",
                       "WSD", "DD", "MADHA", "PSS", "LAUL", "CNHL", "MGO"],
    "ADEN/PVR": ["ARAG", "DLGN", "JTRD", "KVK", "MLB", "PVR", "SGLA", "SGRE", "MRJ", "MSDG", "JVA", "GLV", "LNP",
                 "AGDL", "BLWD", "BDK", "BLNK", "BBV", "AHI", "BMNI", "BHLI"],
    "ADEN/LUR": ["BTW", "DKY", "HGL", "LUR", "OSA", "PJR", "SEI", "YSI", "DRSV", "MRX", "LTRR", "UMD", "UPI", "KCB",
                 "TER", "PCP", "NEI", "KRMD", "BANL", "GANI"],
}
_ELECT_G_GROUPS = {
    "SSE/ELECT/KWV": ["KWV", "DHS", "KEM", "BLNI", "BTW", "SEI", "PPJ", "WSB", "KEU", "JNTR", "BGVN", "MLM", "BRB",
                      "DD", "MLB", "PVR", "SGLA", "DLGN", "JTRD", "SGRE", "ARAG", "KVK", "MRJ", "MKPT", "AAG", "WKA",
                      "MA", "WDS", "WSD", "MADHA", "PSS", "LAUL", "CNHL", "MGO", "MSDG", "JVA", "GLV", "LNP", "AGDL",
                      "BLWD", "BDK", "BLNK", "BBV", "AHI", "BMNI", "BHLI"],
    "SSE/ELECT/SUR": ["DUD", "NGS", "BOT", "AKOR", "SUR", "JEUR", "PK", "BALE", "MVE", "MO", "TKWD", "HG", "TLT",
                      "HG STN", "HG-A", "MOHOL", "PAKNI"],
    "SSE/ELECT/KLBG": ["KUI", "GDGN", "GUR", "SVG", "BBD", "KLBG", "TJSP", "HQR", "MR", "SDB", "SBD", "WADI", "HHD"],
    "SSE/ELECT/LUR": ["PJR", "YSI", "DKY", "OSA", "HGL", "LUR", "DRSV", "MRX", "LTRR", "UMD", "UPI", "KCB", "TER",
                      "PCP", "NEI", "KRMD", "BANL", "GANI"],
}
_ELECT_TRD_GROUPS = {
    "SSE/TRD/SUR": ["SUR", "TKWD", "HG", "TLT", "AKOR", "BALE", "PK", "MVE", "MO", "HG STN", "HG-A", "MOHOL", "PAKNI"],
    "SSE/TRD/DUD": ["NGS", "BOT", "DUD", "KUI", "GUR", "SVG", "HHD"],
    "JE/TRD/KLBG": ["BBD", "KLBG", "TJSP", "HQR", "MR", "SDB", "SBD", "GDGN"],
    "JE/TRD/WADI": ["WADI"],
    "SSE/TRD/KWV": ["MKPT", "AAG", "WKA", "WDS", "KWV", "DHS", "KEM", "BLNI", "WSD", "MADHA", "PSS", "LAUL",
                    "BLWD", "BDK", "MRJ"],
    "SSE/TRD/KEU": ["JEUR", "PPJ", "WSB", "KEU", "JNTR", "BGVN", "MLM", "BRB", "DD"],
    "SSE/TRD/BTW": ["SEI", "BTW", "PJR", "CNHL", "MGO", "UPI", "KCB"],
    "SSE/TRD/DRSV": ["DRSV", "YSI", "DKY", "KRMD"],
    "SSE/TRD/LUR": ["OSA", "HGL", "LUR", "MRX", "LTRR", "UMD", "TER", "PCP", "NEI", "BANL", "GANI"],
    "SSE/TRD/PVR": ["MLB", "PVR", "BBV", "AHI"],
    "SSE/TRD/SGLA": ["SGLA", "JTRD", "DLGN", "MSDG", "JVA", "GLV", "BMNI", "BHLI"],
    "SSE/TRD/SGRE": ["KVK", "SGRE", "ARAG", "LNP", "AGDL", "BLNK"],
}
_OPERATING_GROUPS = {
    "TI/SUR/N": ["SUR", "BALE", "PK", "MVE", "MO", "MKPT", "AAG", "WKA", "MOHOL", "PAKNI"],
    "TI/SUR/S": ["TKWD", "HG", "TLT", "AKOR", "NGS", "BOT", "HG STN", "HG-A"],
    "TI/KLBG": ["DUD", "KUI", "GUR", "SVG", "BBD", "KLBG", "TJSP", "HHD", "GDGN"],
    "TI/WADI": ["HQR", "MR", "SDB", "WADI", "SBD"],
    "TI/KWV": ["WDS", "KWV", "DHS", "KEM", "BLNI", "JEUR", "WSD", "MADHA", "MA", "PSS", "LAUL"],
    "TI/BGVN": ["PPJ", "WSB", "KEU", "JNTR", "BGVN", "MLM", "BRB", "DD"],
    "TI/LUR": ["SEI", "BTW", "PJR", "DRSV", "YSI", "DKY", "OSA", "HGL", "LUR", "MRX", "LTRR", "UMD", "CNHL", "MGO",
               "UPI", "KCB", "TER", "PCP", "NEI", "KRMD", "BANL", "GANI"],
    "TI/PVR": ["MLB", "PVR", "SGLA", "JTRD", "DLGN", "KVK", "SGRE", "ARAG", "MRJ", "MSDG", "JVA", "GLV", "LNP",
               "AGDL", "BLWD", "BDK", "BLNK", "BBV", "AHI", "BMNI", "BHLI"],
}
_SNT_GROUPS = {
    "ADSTE/KLBG (WADI-HG)": ["WADI", "SDB", "MR", "HQR", "KLBG", "BBD", "SVG", "HHD", "GUR", "KUI", "DUD", "BOT",
                             "AKOR", "TLT", "HG", "TJSP", "HG STN", "HG-A", "SBD", "GDGN", "NGS"],
    "ADSTE/SUR (TKWD-MKPT & MLB-MRJ)": ["TKWD", "SUR", "BALE", "PK", "MVE", "MO", "MKPT", "AAG", "WKA", "MLB", "PVR",
                                        "SGLA", "JTRD", "DLGN", "KVK", "SGRE", "ARAG", "MRJ", "MA", "MOHOL", "PAKNI",
                                        "MSDG", "JVA", "GLV", "LNP", "AGDL", "BLWD", "BDK", "BLNK", "BBV", "AHI",
                                        "BMNI", "BHLI"],
    "ADSTE/KWV-I (KWV-BRB)": ["KWV", "DHS", "KEM", "BLNI", "JEUR", "PPJ", "WSB", "KEU", "JNTR", "BGVN", "MLM", "BRB",
                              "WDS", "WSD", "DD", "MADHA", "PSS", "LAUL"],
    "ADSTE/KWV-II (LC-34(DKY)-LUR)": ["SEI", "BTW", "PJR", "YSI", "MRX", "OSA", "HGL", "LUR", "DRSV", "DKY", "LTRR",
                                      "UMD", "CNHL", "MGO", "UPI", "KCB", "TER", "PCP", "NEI", "KRMD", "BANL", "GANI"],
}


def _key(value):
    """Normalise a station code: upper-case, no spaces/hyphens. 'HG STN' -> 'HGSTN', 'HG-A' -> 'HGA'."""
    return re.sub(r"[\s\-]+", "", str(value).strip().upper())


def _invert(groups):
    out = {}
    for jurisdiction, stations in groups.items():
        for s in stations:
            out[_key(s)] = jurisdiction
    return out


ENGG_MAP = _invert(_ENGG_GROUPS)
ELECT_G_MAP = _invert(_ELECT_G_GROUPS)
ELECT_TRD_MAP = _invert(_ELECT_TRD_GROUPS)
OPTG_MAP = _invert(_OPERATING_GROUPS)
SNT_MAP = _invert(_SNT_GROUPS)
COORDS_MAP = {_key(k): v for k, v in STATION_COORDS.items()}

# Department keyword rules. Later rules override earlier ones (OPTG has highest priority).
# A department matching NONE of these is "Unclassified" (it is no longer silently treated as S&T).
# If your sheet writes the S&T department differently, add the word to _SNT_PATTERN.
_SNT_PATTERN = r"S\s*&\s*T|SNT|SIGNAL|TELECOM|\bSIG\b|ADSTE"
JURISDICTION_RULES = [
    (_SNT_PATTERN, SNT_MAP),
    (r"ELECT", ELECT_G_MAP),
    (r"TRD|TRACTION|OHE", ELECT_TRD_MAP),
    (r"ENGG|ENGINEERING|ADEN", ENGG_MAP),
    (r"OPTG|OPERATING", OPTG_MAP),
]
JURISDICTION_TABLES = {
    "Engineering (ADEN)": ENGG_MAP,
    "Electrical General": ELECT_G_MAP,
    "Electrical TRD": ELECT_TRD_MAP,
    "Operating (TI)": OPTG_MAP,
    "S&T (ADSTE)": SNT_MAP,
}


def classify_jurisdiction(df):
    """Vectorised jurisdiction lookup from STATION + DEPARTMENT."""
    stn = df[COL_STATION].fillna("").map(_key)
    dept = df[COL_DEPT].fillna("").astype(str).str.upper()
    result = pd.Series("Unclassified", index=df.index, dtype=object)
    for pattern, mapping in JURISDICTION_RULES:
        mask = dept.str.contains(pattern, regex=True, na=False)
        result = result.mask(mask, stn.map(mapping).fillna("Unclassified"))
    return result


def match_station_coords(station_name):
    """Exact match only. Unknown stations return None (they are reported, never guessed)."""
    return COORDS_MAP.get(_key(station_name))


# ====================== ASSETS (LOCAL, OFFLINE-SAFE) ======================
@st.cache_resource(ttl=3600, show_spinner=False)
def get_logo_bytes():
    """Logo from ./assets/logo.png; downloaded once (when online) and kept on disk."""
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


def _font_face_css():
    """Embeds ./assets/Orbitron.woff2 and ./assets/Rajdhani.woff2 if present; otherwise system fonts are used."""
    css = ""
    for family, fname in [("Orbitron", "Orbitron.woff2"), ("Rajdhani", "Rajdhani.woff2")]:
        p = ASSETS_DIR / fname
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            css += ("@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2');"
                    "font-weight:100 900;font-display:swap;}\n" % (family, b64))
    return css


CUSTOM_CSS = """
<style>
__FONT_FACES__
:root { --display: 'Orbitron', 'Segoe UI', system-ui, sans-serif; --body: 'Rajdhani', 'Segoe UI', system-ui, sans-serif; }
.stApp { background: linear-gradient(135deg, #e0f7fa 0%, #b3e5fc 40%, #e1f5fe 100%); color: #0d1b2a; font-family: var(--body); }
.brand-line { font-family: var(--body); font-size: 1.3rem; color: #01579b; text-align: center; font-weight: 700; letter-spacing: 2px; margin: 0.2rem 0; }
.train-emoji-container { text-align: center; margin: 4px 0 8px 0; overflow: hidden; height: 38px; position: relative; width: 100%; }
.train-track { display: inline-block; white-space: nowrap; animation: moveTrainLine 12s linear infinite; font-size: 1.7rem; letter-spacing: 16px; }
@keyframes moveTrainLine { 0% { transform: translateX(100vw); } 100% { transform: translateX(-100%); } }
@media (prefers-reduced-motion: reduce) { .train-track { animation: none; } div[data-testid="stMetric"] { transition: none !important; } }
.section-header { font-family: var(--display) !important; font-size: 1.3rem !important; font-weight: 700 !important; color: #0277bd !important; margin: 1.2rem 0 0.6rem 0; border-left: 5px solid #0288d1; padding-left: 12px; }
div[data-testid="stMetric"] { background: linear-gradient(145deg, #ffffff, #e1f5fe); border: 1px solid #81d4fa; border-radius: 16px; padding: 16px 12px; box-shadow: 0 6px 18px rgba(2,119,189,0.12); transition: all 0.3s ease; }
div[data-testid="stMetric"]:hover { transform: translateY(-3px); border-color: #0288d1; }
div[data-testid="stMetric"] label { color: #0277bd !important; font-weight: 600 !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] { color: #01579b !important; font-family: var(--display) !important; font-size: 1.6rem !important; }
.stTabs [data-baseweb="tab-list"] { gap: 8px; background: transparent; }
.stTabs [data-baseweb="tab"] { background: #e1f5fe; border-radius: 12px 12px 0 0; color: #01579b; font-family: var(--body); font-weight: 700; font-size: 1.05rem; border: 1px solid #81d4fa; padding: 10px 20px; }
.stTabs [aria-selected="true"] { background: linear-gradient(90deg, #0288d1, #0277bd) !important; color: #ffffff !important; border-color: #0277bd !important; }
.stButton > button { font-family: var(--display) !important; font-weight: 700 !important; border-radius: 10px !important; }
section[data-testid="stSidebar"] { background: linear-gradient(180deg, #e0f7fa 0%, #b3e5fc 100%); border-right: 1px solid #81d4fa; }
.stDataFrame { border-radius: 12px; overflow: hidden; border: 1px solid #81d4fa; }
.watermark { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); opacity: 0.07; z-index: 0; pointer-events: none; width: 520px; max-width: 70vw; }
.watermark img { width: 100%; height: auto; }
.stCaption, .stMarkdown p { color: #37474f !important; }
.drishti-title { font-family: var(--display) !important; font-size: 3rem !important; font-weight: 900 !important; letter-spacing: 10px !important; background: linear-gradient(90deg, #01579b, #0277bd, #0288d1); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin: 0.2rem 0; }
.drishti-fullform { font-family: var(--body); font-size: 1.1rem; font-weight: 600; color: #01579b; text-align: center; }
.drishti-line { width: 180px; height: 3px; margin: 0 auto 0.6rem auto; background: linear-gradient(90deg, transparent, #0288d1, #ffc107, #0288d1, transparent); border-radius: 10px; }
.status-pill { display:inline-block; padding: 4px 12px; border-radius: 999px; font-weight: 700; font-size: 0.9rem; }
.status-live { background:#e8f5e9; color:#1b5e20; border:1px solid #81c784; }
.status-off  { background:#fff3e0; color:#e65100; border:1px solid #ffb74d; }
</style>
"""

# ====================== SMALL UI HELPERS ======================
def section(title):
    st.markdown(f'<p class="section-header">{html_lib.escape(title)}</p>', unsafe_allow_html=True)


def style_fig(fig, **layout):
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#0d1b2a", **layout)
    return fig


def summarize(df, col):
    if df.empty or col not in df.columns:
        return pd.DataFrame(columns=[col, "Cases"])
    return df.groupby(col).size().reset_index(name="Cases").sort_values("Cases", ascending=False)


def hbar(summary, col, scale, top=12, height=400):
    plot = summary.head(top).sort_values("Cases", ascending=True)
    fig = px.bar(plot, x="Cases", y=col, orientation="h", text="Cases", color="Cases", color_continuous_scale=scale)
    fig.update_traces(textposition="outside", cliponaxis=False)
    style_fig(fig, height=height, showlegend=False, coloraxis_showscale=False, xaxis_title="Cases", yaxis_title="",
              margin=dict(t=30, b=30, l=20, r=50))
    return fig


def show_summary_table(summary, gradient=False):
    styler = summary.style.format({"Cases": "{:,}"})
    if gradient:
        try:
            styler = styler.background_gradient(subset=["Cases"], cmap="YlOrRd")  # needs matplotlib
        except Exception:
            pass
    st.dataframe(styler, hide_index=True, **STRETCH)


def now_ist():
    return pd.Timestamp.now(tz=IST).tz_localize(None)


def fmt_ist(iso):
    try:
        return pd.Timestamp(iso).strftime("%d %b %Y, %H:%M IST")
    except Exception:
        return str(iso)


# ====================== FORECASTING ENGINE ======================
def get_global_month_index(df):
    if df is None or df.empty or COL_DATE not in df.columns:
        return pd.DatetimeIndex([])
    d = df.dropna(subset=[COL_DATE])
    if d.empty:
        return pd.DatetimeIndex([])
    start = d[COL_DATE].min().to_period("M").to_timestamp()
    end = d[COL_DATE].max().to_period("M").to_timestamp()
    return pd.date_range(start, end, freq="MS")


def build_monthly_series(df, full_index=None):
    if df is None or df.empty or COL_DATE not in df.columns:
        return pd.Series(dtype=float)
    d = df.dropna(subset=[COL_DATE])
    if d.empty:
        return pd.Series(dtype=float)
    series = d.set_index(COL_DATE).sort_index().resample("MS").size().astype(float)
    if full_index is not None and len(full_index) > 0:
        series = series.reindex(full_index, fill_value=0.0)
    return series


def trim_incomplete_current_month(series):
    """Drops the current month (in IST, not server time) because it is still in progress."""
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
    ws = writer.sheets[sheet_name]
    header_fmt = workbook.add_format({"bold": True, "font_color": "white", "bg_color": header_color, "border": 1,
                                      "align": "center", "valign": "vcenter", "text_wrap": True})
    text_fmt = workbook.add_format({"border": 1, "valign": "vcenter"})
    number_fmt = workbook.add_format({"border": 1, "valign": "vcenter", "num_format": "#,##0"})
    date_fmt = workbook.add_format({"border": 1, "valign": "vcenter", "num_format": "dd-mmm-yyyy"})
    for i, name in enumerate(df.columns):
        ws.write(0, i, str(name), header_fmt)
        col = df[name]
        if pd.api.types.is_datetime64_any_dtype(col) or str(name).strip().upper() == "DATE":
            fmt = date_fmt
        elif pd.api.types.is_numeric_dtype(col):
            fmt = number_fmt
        else:
            fmt = text_fmt
        sample = col.head(1000).astype(str)
        content_len = int(sample.map(len).max()) if len(sample) else 0
        ws.set_column(i, i, min(max(max(content_len, len(str(name))) + 2, 10), 45), fmt)
    ws.set_row(0, 30)
    ws.freeze_panes(1, 0)
    if len(df) > 0:
        ws.autofilter(0, 0, len(df), len(df.columns) - 1)


def build_excel(sheets):
    """sheets: list of (sheet_name, DataFrame). strings_to_formulas=False stops '=...' text becoming a formula."""
    out = BytesIO()
    opts = {"options": {"strings_to_formulas": False, "nan_inf_to_errors": True}}
    with pd.ExcelWriter(out, engine="xlsxwriter", engine_kwargs=opts) as writer:
        for name, sdf in sheets:
            if sdf is not None and not sdf.empty:
                write_styled_sheet(writer, sdf, name[:31])
    return out.getvalue()


@dataclass
class ForecastResult:
    forecast: pd.Series
    method: str
    resid: float
    wape: Optional[float]
    pooled: bool  # True: resid comes from back-test errors; False: rough estimate


def _require(y, n):
    if len(y) < n:
        raise ValueError("series too short")


def _m_naive(y, h):
    return np.repeat(y[-1], h)


def _m_mean3(y, h):
    _require(y, 3)
    return np.repeat(y[-3:].mean(), h)


def _m_linear(y, h):
    _require(y, 4)
    slope, intercept = np.polyfit(np.arange(len(y), dtype=float), y, 1)
    return slope * np.arange(len(y), len(y) + h, dtype=float) + intercept


def _m_seasonal_naive(y, h):
    _require(y, 13)
    last = y[-12:]
    return np.array([last[i % 12] for i in range(h)], dtype=float)


def _m_holt(y, h):
    _require(y, 6)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(y, trend="add", damped_trend=True, initialization_method="estimated").fit(optimized=True)
        return np.asarray(fit.forecast(h), dtype=float)


def _m_holt_winters(y, h):
    _require(y, 24)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = ExponentialSmoothing(y, trend="add", seasonal="add", seasonal_periods=12, damped_trend=True,
                                   initialization_method="estimated").fit(optimized=True)
        return np.asarray(fit.forecast(h), dtype=float)


FORECAST_MODELS = {
    "Naive (last month)": _m_naive,
    "3-month average": _m_mean3,
    "Linear trend": _m_linear,
    "Seasonal naive (same month last year)": _m_seasonal_naive,
}
if STATSMODELS_AVAILABLE:
    FORECAST_MODELS["Holt exponential smoothing"] = _m_holt
    FORECAST_MODELS["Holt-Winters (damped trend + seasonality)"] = _m_holt_winters


def _backtest(y, fn, h, folds, min_train=5):
    """Rolling-origin back-test. Returns WAPE and RMSE, or None if the model can't run."""
    actual, pred = [], []
    for k in range(folds):
        cut = len(y) - h * (k + 1)
        if cut < min_train:
            break
        try:
            p = np.clip(np.asarray(fn(y[:cut], h), dtype=float), 0, None)
        except Exception:
            return None
        actual.append(y[cut:cut + h])
        pred.append(p)
    if not actual:
        return None
    a, p = np.concatenate(actual), np.concatenate(pred)
    den = float(a.sum())
    wape = float(np.abs(a - p).sum() / den * 100) if den > 0 else float("nan")
    return {"wape": wape, "rmse": float(np.sqrt(np.mean((a - p) ** 2)))}


@st.cache_data(show_spinner=False)
def forecast_series(series, periods=3):
    """Picks the best model per series by rolling back-test WAPE (count data: MAPE breaks at zero)."""
    series = series.dropna().astype(float)
    n = len(series)
    if n == 0:
        return ForecastResult(pd.Series(dtype=float), "No data", 0.0, None, False)
    y = series.values
    future_idx = pd.date_range(series.index[-1] + pd.DateOffset(months=1), periods=periods, freq="MS")

    scores = {}
    if n >= 8:
        folds = 3 if n >= 14 else 2
        for name, fn in FORECAST_MODELS.items():
            r = _backtest(y, fn, periods, folds)
            if r is not None:
                scores[name] = r

    if scores:
        best = min(scores, key=lambda k: scores[k]["wape"] if not np.isnan(scores[k]["wape"]) else np.inf)
        wape = scores[best]["wape"]
        resid, pooled = scores[best]["rmse"], True
    else:
        best = "Naive (last month)" if n < 4 else "Linear trend"
        wape = None
        resid = float(np.std(np.diff(y))) if n > 1 else 0.0
        pooled = False

    try:
        vals = FORECAST_MODELS[best](y, periods)
    except Exception:
        best, vals = "Naive (last month)", _m_naive(y, periods)
    vals = np.clip(np.round(vals), 0, None)
    return ForecastResult(pd.Series(vals, index=future_idx), best, resid, wape, pooled)


def interval_bounds(res):
    steps = np.arange(1, len(res.forecast) + 1, dtype=float)
    scale = np.ones_like(steps) if res.pooled else np.sqrt(steps)
    margin = 1.96 * res.resid * scale
    v = res.forecast.values.astype(float)
    return np.clip(v - margin, 0, None), v + margin


def forecast_by_group(df, group_col, horizon, top_n=10, full_index=None):
    if df.empty or group_col not in df.columns:
        return pd.DataFrame()
    ranking = df.groupby(group_col).size().sort_values(ascending=False).head(top_n)
    rows = []
    for g in ranking.index:
        s = trim_incomplete_current_month(build_monthly_series(df[df[group_col] == g], full_index=full_index))
        if s.empty:
            continue
        res = forecast_series(s, horizon)
        row = {group_col: g, "Last month (actual)": int(s.iloc[-1])}
        for dt, v in res.forecast.items():
            row[dt.strftime("%b %Y")] = int(v)
        row["Forecast total"] = int(res.forecast.sum())
        row["Model"] = res.method
        rows.append(row)
    return pd.DataFrame(rows)


# ====================== DATA LOADING + OFFLINE SNAPSHOT ======================
def parse_dates(series):
    """ISO dates stay ISO (year-month-day); everything else is read day-first (Indian dd/mm/yyyy)."""
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
    """Returns (clean_df, info). Raises ValueError if required columns are missing."""
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    df = df.loc[:, ~df.columns.str.lower().str.replace(".", "", regex=False).str.contains(r"^(?:sl|sr)\s*no", regex=True)]
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
    for c in (COL_STATION, COL_DEPT):
        df[c] = df[c].str.upper()

    raw_dates = df[COL_DATE]
    df[COL_DATE] = parse_dates(raw_dates)
    had_text = raw_dates.notna() & raw_dates.astype(str).str.strip().ne("")
    bad_dates = int((df[COL_DATE].isna() & had_text).sum())
    blank_dates = int((df[COL_DATE].isna() & ~had_text).sum())

    df[COL_YM] = df[COL_DATE].dt.strftime("%Y-%m")
    df[COL_MONTH] = df[COL_DATE].dt.strftime("%b %Y")  # includes the year, sorted chronologically in the filter
    df[COL_JUR] = classify_jurisdiction(df)
    info = {"bad_dates": bad_dates, "blank_dates": blank_dates, "missing_columns": missing_optional}
    return df, info


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
    last_err = None
    client = None
    for scopes in (["https://www.googleapis.com/auth/spreadsheets.readonly"], None):  # read-only first
        try:
            client = (gspread.service_account_from_dict(info, scopes=scopes) if scopes
                      else gspread.service_account_from_dict(info))
            try:
                client.set_timeout(20)
            except Exception:
                pass
            worksheet = client.open_by_key(sheet_id).worksheet(sheet_name)
            records = worksheet.get_all_records()
            break
        except Exception as e:  # try the wider scope once
            last_err = e
            client = None
    if client is None:
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
    """Returns (df, status). status['mode'] is 'live' or 'offline'."""
    reason = "forced" if force_offline else None
    if not force_offline and time.time() >= st.session_state.get("_online_retry_at", 0):
        try:
            res = fetch_online(SHEET_ID, SHEET_NAME)
            st.session_state.pop("_online_retry_at", None)
            return res["df"], {"mode": "live", **res["meta"]}
        except Exception:
            logger.exception("Live data load failed; falling back to offline snapshot")
            st.session_state["_online_retry_at"] = time.time() + ONLINE_RETRY_SECONDS
            reason = "unreachable"
    elif not force_offline:
        reason = "unreachable"
    df, meta = load_snapshot()
    if df is not None:
        return df, {"mode": "offline", "reason": reason, **(meta or {})}
    return None, {"mode": "none", "reason": reason}


# ====================== AUTH ======================
def verify_password(stored, supplied):
    """Supports 'pbkdf2_sha256$iters$salt_hex$digest' hashes and (legacy) plain text. Constant-time."""
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


def login_page():
    _, mid, _ = st.columns([2, 3, 2])
    with mid:
        st.subheader("🔐 Secure Login")
        remaining = st.session_state["_locked_until"] - time.time()
        if remaining > 0:
            st.error(f"Too many failed attempts. Try again in {int(remaining) + 1} seconds.")
            return
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Username / Email", placeholder="Enter your ID").strip()
            password = st.text_input("Password", type="password", placeholder="Enter Password")
            submitted = st.form_submit_button("Login", type="primary", **STRETCH)
        if submitted:
            stored = USERS[email].get("password") if email in USERS else None
            if verify_password(stored, password):
                st.session_state.update(logged_in=True, user_name=USERS[email].get("name", email),
                                        _fail_count=0, _last_active=time.time())
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


# ====================== FILTERS ======================
FILTER_SPECS = [  # (column, label, session key)
    (COL_STATION, "STATION", "stn_key"),
    (COL_ERROR, "ERROR MAIN CATEGORY", "err_key"),
    (COL_DEPT, "DEPARTMENT", "cat_key"),
    (COL_MONTH, "MONTH", "month_key"),
    (COL_FAULT, "DL FAULT MESSAGE", "fault_key"),
    (COL_REMARK, "REMARKS GIVEN BY S&T", "remark_key"),
    (COL_JUR, "JURISDICTION", "jur_key"),
]


def reset_filters():
    for _, _, key in FILTER_SPECS:
        st.session_state[key] = []
    if "_bounds" in st.session_state:
        st.session_state["from_date_key"], st.session_state["to_date_key"] = st.session_state["_bounds"]
    st.session_state["map_selected_station"] = None


def sync_date_bounds(data_min, data_max):
    """Keeps date pickers valid when data changes (e.g. after refresh): follows new min/max unless the user narrowed them."""
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


def month_options(df):
    d = df.dropna(subset=[COL_DATE]).drop_duplicates(COL_YM).sort_values(COL_YM)
    return d[COL_MONTH].tolist()  # chronological, with year


def render_filters(df):
    """Sidebar filters. Returns (selections dict, from_date, to_date)."""
    selections = {}
    st.markdown("### 🔍 Filters")
    for col, label, key in FILTER_SPECS:
        options = month_options(df) if col == COL_MONTH else sorted(df[col].dropna().astype(str).unique().tolist())
        if key in st.session_state:  # drop selections that no longer exist after a data refresh
            st.session_state[key] = [v for v in st.session_state[key] if v in options]
        selections[col] = st.multiselect(label, options=options, key=key)

    valid = df[COL_DATE].dropna()
    today = now_ist().date()
    data_min = valid.min().date() if not valid.empty else today
    data_max = valid.max().date() if not valid.empty else today
    sync_date_bounds(data_min, data_max)
    from_date = st.date_input("FROM DATE", key="from_date_key", min_value=data_min, max_value=data_max)
    to_date = st.date_input("TO DATE", key="to_date_key", min_value=data_min, max_value=data_max)
    if from_date > to_date:
        st.warning("FROM is after TO — the dates were swapped.")
        from_date, to_date = to_date, from_date
    st.button("↺ Reset filters", on_click=reset_filters, **STRETCH)
    return selections, from_date, to_date


def apply_category_filters(df, selections):
    out = df
    for col, sel in selections.items():
        if col == COL_MONTH or not sel:
            continue
        out = out[out[col].isin(sel)]
    return out


def apply_date_month_filters(df, selections, from_date, to_date):
    lo = pd.Timestamp(from_date)
    hi = pd.Timestamp(to_date) + pd.Timedelta(days=1)
    out = df[(df[COL_DATE] >= lo) & (df[COL_DATE] < hi)]
    if selections.get(COL_MONTH):
        out = out[out[COL_MONTH].isin(selections[COL_MONTH])]
    return out


# ====================== DOWNLOAD HELPERS ======================
def prepared_download(label, key, builder, file_name, mime, sig):
    """Two-step download: files are built only when clicked (not on every rerun) and
    are offered only while the filters still match the ones used to build them."""
    store = st.session_state.setdefault("_prepared", {})
    if st.button(f"⚙️ Prepare: {label}", key=f"prep_{key}", **STRETCH):
        with st.spinner("Building file..."):
            store[key] = (builder(), sig)
    if key in store:
        data, built_sig = store[key]
        if built_sig == sig:
            st.download_button(label=f"⬇️ {label}", data=data, file_name=file_name, mime=mime,
                               key=f"dl_{key}", type="primary", **STRETCH)
        else:
            st.info("Filters changed since this file was prepared — click Prepare again.")


def stamp():
    return now_ist().strftime("%Y%m%d_%H%M")


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def build_display_df(df):
    d = df.copy()
    d[COL_DATE] = d[COL_DATE].dt.date
    cols = [c for c in PREFERRED_ORDER if c in d.columns] + [c for c in d.columns if c not in PREFERRED_ORDER + [COL_MONTH, COL_YM]]
    return d[cols]


def render_detailed_records(df, extra_sheets, file_prefix, label, key, sig):
    section("Detailed Records")
    if df.empty:
        st.warning("No records found.")
        return
    display_df = build_display_df(df)
    st.dataframe(display_df.head(MAX_DISPLAY_ROWS), hide_index=True, **STRETCH)
    if len(display_df) > MAX_DISPLAY_ROWS:
        st.caption(f"Showing the first {MAX_DISPLAY_ROWS:,} of {len(display_df):,} rows. The Excel download contains all rows.")
    st.markdown("---")
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        prepared_download(label, key,
                          lambda: build_excel([("Filtered_Records", display_df)] + list(extra_sheets)),
                          f"{file_prefix}_{stamp()}.xlsx", XLSX_MIME, sig)


# ====================== OFFLINE HTML DASHBOARD ======================
def build_offline_html(df, station_summary, cat_sum, error_sum, jur_sum, status, user):
    """One self-contained .html (Plotly.js embedded once). Opens with no internet and no server."""
    figs = []
    hist = build_monthly_series(df)
    if not hist.empty:
        f = go.Figure(go.Scatter(x=hist.index, y=hist.values, mode="lines+markers", line=dict(color="#0277bd", width=3)))
        style_fig(f, height=380, title="Monthly cases", xaxis_title="Month", yaxis_title="Cases")
        figs.append(f)
    if not station_summary.empty:
        f = px.bar(station_summary.head(15), x=COL_STATION, y="Cases", text="Cases", color="Cases",
                   color_continuous_scale="RdYlGn_r")
        style_fig(f, height=420, title="Top 15 stations", xaxis_tickangle=45)
        figs.append(f)
        pts = []
        for _, r in station_summary.iterrows():
            c = match_station_coords(r[COL_STATION])
            if c:
                pts.append({"STATION": r[COL_STATION], "Cases": int(r["Cases"]), "lat": c[0], "lon": c[1]})
        if pts:
            f = px.scatter(pd.DataFrame(pts), x="lon", y="lat", size="Cases", color="Cases", hover_name="STATION",
                           color_continuous_scale="RdYlGn_r", size_max=35)
            f.update_yaxes(scaleanchor="x", scaleratio=1)
            style_fig(f, height=520, title="Station map (schematic, no map tiles needed)")
            figs.append(f)
    for summary, col, scale, title in [(cat_sum, COL_DEPT, "Blues", "Department-wise"),
                                       (error_sum, COL_ERROR, "Oranges", "Error main category"),
                                       (jur_sum, COL_JUR, "Teal", "Jurisdiction-wise")]:
        if not summary.empty:
            f = hbar(summary, col, scale, height=420)
            f.update_layout(title=title)
            figs.append(f)

    cfg = {"displaylogo": False, "responsive": True}
    chart_html = "".join(
        f'<div class="card">{f.to_html(full_html=False, include_plotlyjs=(i == 0), config=cfg)}</div>'
        for i, f in enumerate(figs)
    )
    rec = build_display_df(df).head(MAX_DISPLAY_ROWS)
    rec_html = rec.to_html(index=False, escape=True, classes="tbl", table_id="rec", na_rep="")
    stn_html = station_summary.to_html(index=False, escape=True, classes="tbl")
    top = station_summary.iloc[0] if not station_summary.empty else None
    kpis = [("Total cases", f"{len(df):,}"),
            ("Top station", html_lib.escape(str(top[COL_STATION])) if top is not None else "N/A"),
            ("Top station cases", f"{int(top['Cases']):,}" if top is not None else "0"),
            ("Unique stations", f"{df[COL_STATION].nunique():,}")]
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


# ====================== TABS ======================
def render_animation(filtered_df, sig):
    section("🎬 Animated Monthly Cases by Station")
    if not st.toggle("Show animated chart (slower to render)", value=False, key="anim_toggle"):
        return
    anim_df = filtered_df.dropna(subset=[COL_DATE, COL_STATION])
    if anim_df.empty:
        st.warning("Not enough data for animation.")
        return
    c1, c2 = st.columns(2)
    with c1:
        top_n_anim = st.slider("Show Top N stations", 5, 25, 12, key="anim_topn")
    with c2:
        anim_speed = st.select_slider("Animation Speed", options=["Very Slow", "Slow", "Normal", "Fast"], value="Slow", key="anim_speed")
    frame_ms = {"Very Slow": 1800, "Slow": 1400, "Normal": 1000, "Fast": 700}[anim_speed]

    monthly = anim_df.groupby([COL_STATION, pd.Grouper(key=COL_DATE, freq="MS")]).size().rename("Value").reset_index()
    top_stations = monthly.groupby(COL_STATION)["Value"].sum().sort_values(ascending=False).head(top_n_anim).index.tolist()
    months = pd.date_range(anim_df[COL_DATE].min().to_period("M").to_timestamp(),
                           anim_df[COL_DATE].max().to_period("M").to_timestamp(), freq="MS")
    grid = pd.MultiIndex.from_product([top_stations, months], names=[COL_STATION, COL_DATE])  # zero-filled: no bars popping in/out
    monthly = (monthly.set_index([COL_STATION, COL_DATE])["Value"].reindex(grid, fill_value=0).reset_index())
    monthly["Month"] = monthly[COL_DATE].dt.strftime("%b %Y")
    labels = [m.strftime("%b %Y") for m in months]

    fig = px.bar(monthly, x=COL_STATION, y="Value", color="Value", animation_frame="Month", animation_group=COL_STATION,
                 category_orders={"Month": labels, COL_STATION: top_stations},
                 range_y=[0, max(1, monthly["Value"].max()) * 1.18], color_continuous_scale="RdYlGn_r",
                 labels={"Value": "Cases", COL_STATION: "Station"}, title="Monthly Cases by Station", text="Value")
    fig.update_traces(texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
    style_fig(fig, height=600, xaxis_tickangle=-45, coloraxis_showscale=False, margin=dict(t=70, b=120), title_x=0.5)
    try:
        args = fig.layout.updatemenus[0].buttons[0].args[1]
        args["frame"]["duration"] = frame_ms
        args["transition"]["duration"] = int(frame_ms * 0.55)
    except Exception:
        pass
    st.plotly_chart(fig, config={"displaylogo": False}, **STRETCH)
    st.caption(f"Speed: **{anim_speed}** • Stations are ordered by their total over the whole period.")
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        prepared_download("Animation (interactive HTML, works offline)", "anim",
                          lambda: fig.to_html(full_html=True, include_plotlyjs=True,
                                              config={"displaylogo": False, "responsive": True}).encode("utf-8"),
                          f"DRISHTI_Animation_{stamp()}.html", "text/html", sig)


def render_overview(filtered_df, station_summary, cat_sum, error_sum, jur_sum, sig, status, user):
    st.subheader("📊 Overview Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    top_station = station_summary.iloc[0][COL_STATION] if not station_summary.empty else "N/A"
    top_cases = int(station_summary.iloc[0]["Cases"]) if not station_summary.empty else 0
    c1.metric("Total Cases", f"{len(filtered_df):,}")
    c2.metric("⚠️ Top Station", top_station)
    c3.metric("Top Station Cases", f"{top_cases:,}")
    c4.metric("Unique Stations", f"{filtered_df[COL_STATION].nunique()}")
    st.markdown("---")

    g1, g2 = st.columns([3, 2])
    with g1:
        section("Top 15 Stations by Cases")
        if not station_summary.empty:
            fig = px.bar(station_summary.head(15), x=COL_STATION, y="Cases", text="Cases", color="Cases", color_continuous_scale="RdYlGn_r")
            style_fig(fig, height=480, xaxis_tickangle=45)
            st.plotly_chart(fig, **STRETCH)
    with g2:
        section("Station Summary")
        if not station_summary.empty:
            show_summary_table(station_summary, gradient=True)

    st.markdown("---")
    section("📊 Distribution Charts")
    cols = st.columns(3)
    for c, title, summary, col, scale in [(cols[0], "Department-wise", cat_sum, COL_DEPT, "Blues"),
                                          (cols[1], "Error Main Category", error_sum, COL_ERROR, "Oranges"),
                                          (cols[2], "Jurisdiction-wise", jur_sum, COL_JUR, "Teal")]:
        with c:
            st.markdown(f"**{title}**")
            if not summary.empty:
                st.plotly_chart(hbar(summary, col, scale), **STRETCH)
            else:
                st.info(f"No {title.split('-')[0]} data")

    st.markdown("---")
    render_animation(filtered_df, sig)

    st.markdown("---")
    s1, s2, s3 = st.columns(3)
    for c, title, summary in [(s1, "DEPARTMENT", cat_sum), (s2, "ERROR MAIN CATEGORY", error_sum), (s3, "JURISDICTION", jur_sum)]:
        with c:
            if not summary.empty:
                section(title)
                show_summary_table(summary)

    st.markdown("---")
    section("📴 Offline Dashboard")
    st.caption("A single HTML file with charts, tables and search. Open it in any browser — no internet, no server.")
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        prepared_download("Offline dashboard (HTML)", "offline_html",
                          lambda: build_offline_html(filtered_df, station_summary, cat_sum, error_sum, jur_sum, status, user),
                          f"DataLogger_Offline_{stamp()}.html", "text/html", sig)

    st.markdown("---")
    render_detailed_records(
        filtered_df,
        [("Station_Summary", station_summary), ("Error_Summary", error_sum),
         ("Category_Summary", cat_sum), ("Jurisdiction_Summary", jur_sum)],
        "DRISHTI_Report", "Professional Excel Report", "overview_download", sig)


def render_forecast(forecast_base_df, sig):
    st.subheader("🔮 Forecast — next 1 to 3 months (Number of Cases)")
    st.caption("Uses the complete history (the date range filter is ignored); the other filters apply.")
    f1, f2, f3 = st.columns(3)
    with f1:
        horizon = st.slider("Months ahead", 1, 3, 3, key="fc_horizon")
    with f2:
        level = st.selectbox("Break-up by", ["Division total (no break-up)", "Station", "Department", "Jurisdiction", "Error Main Category"], key="fc_level")
    with f3:
        top_n = st.number_input("Top N groups", min_value=3, max_value=25, value=10, step=1, key="fc_topn")

    full_index = get_global_month_index(forecast_base_df)
    hist_raw = build_monthly_series(forecast_base_df, full_index=full_index)
    hist = trim_incomplete_current_month(hist_raw)
    if hist.empty:
        st.warning("Not enough dated records to build a forecast.")
        return
    if len(hist) < len(hist_raw):
        st.caption(f"ℹ️ **{hist_raw.index[-1].strftime('%B %Y')}** is still in progress, so it is excluded from training.")

    res = forecast_series(hist, horizon)
    fc = res.forecast
    lower, upper = interval_bounds(res)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Months of history", f"{len(hist)}")
    k2.metric("Last month Cases", f"{int(hist.iloc[-1]):,}")
    k3.metric(f"Next {horizon} months (predicted)", f"{int(fc.sum()):,}")
    last = float(hist.iloc[-1])
    k4.metric("vs last month", f"{((fc.mean() - last) / last * 100):+.1f}%" if last else "n/a")
    st.info(f"**Model used (best on back-test):** {res.method}"
            + (f"  •  **Back-test WAPE:** {res.wape:.1f}%" if res.wape is not None and not np.isnan(res.wape) else "  •  too little history to back-test"))

    ax = [hist.index[-1]] + list(fc.index)
    ay = [last] + [float(v) for v in fc.values]
    up = [last] + list(upper)
    lo = [last] + list(lower)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ax + ax[::-1], y=up + lo[::-1], fill="toself", fillcolor="rgba(2,136,209,0.18)",
                             line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", name="≈95% range"))
    fig.add_trace(go.Scatter(x=hist.index, y=hist.values, mode="lines+markers", name="Actual", line=dict(color="#0277bd", width=3), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=ax, y=ay, mode="lines+markers+text", name="Forecast", line=dict(color="#0288d1", width=3, dash="dash"),
                             marker=dict(size=10), text=[""] + [f"{int(v):,}" for v in fc.values], textposition="top center"))
    style_fig(fig, height=470, hovermode="x unified", xaxis_title="Month", yaxis_title="Monthly Cases", legend=dict(orientation="h", y=1.12))
    st.plotly_chart(fig, **STRETCH)

    fc_table = pd.DataFrame({"Month": [d.strftime("%B %Y") for d in fc.index], "Predicted Cases": fc.values.astype(int),
                             "Lower estimate": lower.astype(int), "Upper estimate": upper.astype(int)})
    section("Predicted values")
    st.dataframe(fc_table.style.format({c: "{:,}" for c in fc_table.columns if c != "Month"}), hide_index=True, **STRETCH)
    st.caption("The range is an approximation based on back-test errors; treat it as a guide, not a guarantee.")

    group_map = {"Station": COL_STATION, "Department": COL_DEPT, "Jurisdiction": COL_JUR, "Error Main Category": COL_ERROR}
    group_table = pd.DataFrame()
    if level in group_map:
        gcol = group_map[level]
        st.markdown("---")
        section(f"Forecast by {level} (top {int(top_n)})")
        with st.spinner("Fitting models..."):
            group_table = forecast_by_group(forecast_base_df, gcol, horizon, int(top_n), full_index=full_index)
        if group_table.empty:
            st.info("Not enough history for group-wise forecast.")
        else:
            num_cols = [c for c in group_table.columns if c not in (gcol, "Model")]
            styler = group_table.style.format({c: "{:,}" for c in num_cols})
            try:
                styler = styler.background_gradient(subset=["Forecast total"], cmap="YlOrRd")
            except Exception:
                pass
            st.dataframe(styler, hide_index=True, **STRETCH)
            plot_df = group_table.sort_values("Forecast total", ascending=True)
            fg = px.bar(plot_df, x="Forecast total", y=gcol, orientation="h", text="Forecast total", color="Forecast total", color_continuous_scale="RdYlGn_r")
            fg.update_traces(textposition="outside", cliponaxis=False)
            style_fig(fg, height=480, coloraxis_showscale=False, xaxis_title=f"Predicted Cases (next {horizon} months)", yaxis_title="", margin=dict(t=30, b=30, l=20, r=60))
            st.plotly_chart(fg, **STRETCH)

    st.markdown("---")
    history_df = pd.DataFrame({"Month": hist.index.strftime("%b %Y"), "Cases": hist.values.astype(int)})
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        prepared_download("Forecast Report", "forecast_download",
                          lambda: build_excel([("Division_Forecast", fc_table), ("Monthly_History", history_df), ("Group_Forecast", group_table)]),
                          f"DRISHTI_Forecast_{stamp()}.xlsx", XLSX_MIME, sig + f"|{horizon}|{level}|{top_n}")


def render_map(filtered_df, station_summary, jur_sum, use_tiles, sig):
    st.subheader("🗺️ Interactive Map View — click a station to see only its records")
    selected = st.session_state.map_selected_station
    if selected:
        c1, _ = st.columns([1, 5])
        with c1:
            if st.button("🔄 Clear Station Selection", **STRETCH):
                st.session_state.map_selected_station = None
                st.session_state["_last_map_click"] = None
                st.session_state["_map_epoch"] += 1  # remount the map so its old 'last click' is forgotten
                st.rerun()
        st.success(f"📍 Showing records for: **{selected}** (this selection affects the Map tab only)")

    m1, m2 = st.columns([3, 2])
    with m1:
        if filtered_df.empty or station_summary.empty:
            st.warning("No data available.")
        else:
            rows, unmatched = [], []
            for _, r in station_summary.iterrows():
                c = match_station_coords(r[COL_STATION])
                if c:
                    rows.append({COL_STATION: r[COL_STATION], "Cases": int(r["Cases"]), "lat": c[0], "lon": c[1]})
                else:
                    unmatched.append(r[COL_STATION])
            map_df = pd.DataFrame(rows)
            if unmatched:
                st.warning(f"{len(unmatched)} station(s) have no coordinates and are not on the map: {', '.join(unmatched)}")
            if map_df.empty:
                st.info("No stations with known coordinates.")
            else:
                m = folium.Map(location=[17.85, 75.80], zoom_start=8, tiles=None, control_scale=True)
                if use_tiles:
                    try:
                        carto_key = st.secrets["carto"]["api_key"]
                    except Exception:
                        carto_key = None
                    if carto_key:
                        folium.TileLayer(tiles=f"https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}.png?key={carto_key}",
                                         name="🗺️ Light Base", attr="© OpenStreetMap © CARTO", subdomains="abcd", max_zoom=20).add_to(m)
                    folium.TileLayer("OpenStreetMap", name="🌍 OpenStreetMap", show=not carto_key).add_to(m)
                    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                                     attr="Esri", name="🌐 Satellite", show=False).add_to(m)
                    folium.LayerControl(position="topright", collapsed=True).add_to(m)
                else:
                    st.caption("📴 Offline map: station markers only (no base map tiles).")
                Fullscreen().add_to(m)

                lo_t, hi_t = np.percentile(map_df["Cases"], [33, 66])  # adaptive colour thresholds
                for _, r in map_df.iterrows():
                    cases = int(r["Cases"])
                    color = "green" if cases <= lo_t else "orange" if cases <= hi_t else "darkred"
                    radius = 8 + min(cases / max(map_df["Cases"].max(), 1) * 22, 25)
                    folium.CircleMarker(location=[r["lat"], r["lon"]], radius=radius,
                                        popup=f"<h4>{html_lib.escape(r[COL_STATION])}</h4><b>Total Cases:</b> {cases:,}",
                                        tooltip=f"{r[COL_STATION]} — {cases:,} cases", color=color, fill=True,
                                        fill_color=color, fill_opacity=0.85, weight=2).add_to(m)
                    if r[COL_STATION] == selected:
                        folium.CircleMarker(location=[r["lat"], r["lon"]], radius=radius + 6, color="#0d47a1",
                                            weight=4, fill=False, interactive=False).add_to(m)
                m.fit_bounds([[map_df["lat"].min(), map_df["lon"].min()], [map_df["lat"].max(), map_df["lon"].max()]], padding=(30, 30))
                m.get_root().html.add_child(folium.Element(
                    "<div style='position:fixed;bottom:24px;left:24px;z-index:9999;background:#fff;padding:8px 12px;"
                    "border:1px solid #81d4fa;border-radius:8px;font:13px sans-serif'>"
                    "<b>Cases (by tercile)</b><br><span style='color:green'>●</span> Low &nbsp;"
                    "<span style='color:orange'>●</span> Medium &nbsp;<span style='color:darkred'>●</span> High</div>"))

                ret = st_folium(m, height=680, use_container_width=True, key=f"sur_map_{st.session_state['_map_epoch']}",
                                returned_objects=["last_object_clicked_tooltip"])
                tip = (ret or {}).get("last_object_clicked_tooltip")
                if tip and tip != st.session_state["_last_map_click"]:
                    st.session_state["_last_map_click"] = tip
                    name = str(tip).split(" — ")[0].strip()
                    if name in set(map_df[COL_STATION]) and name != st.session_state.map_selected_station:
                        st.session_state.map_selected_station = name
                        st.rerun()

    with m2:
        st.subheader("Station Summary")
        if not station_summary.empty:
            show_summary_table(station_summary, gradient=True)
        st.markdown("---")
        st.subheader("Jurisdiction Summary")
        if not jur_sum.empty:
            show_summary_table(jur_sum)

    st.markdown("---")
    map_records = filtered_df[filtered_df[COL_STATION] == selected] if selected else filtered_df
    render_detailed_records(map_records, [("Jurisdiction_Summary", jur_sum)], "DRISHTI_Map_Report",
                            "Map Filtered Report", "map_download", sig + f"|{selected}")


def render_quality(df_original, status):
    st.subheader("🩺 Data Quality")
    stations = sorted(df_original[COL_STATION].dropna().unique().tolist())
    no_coords = [s for s in stations if match_station_coords(s) is None]
    unclassified = df_original[df_original[COL_JUR] == "Unclassified"]
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Rows loaded", f"{len(df_original):,}")
    q2.metric("Rows with bad/blank DATE", f"{status.get('bad_dates', 0) + status.get('blank_dates', 0):,}")
    q3.metric("Unclassified rows", f"{len(unclassified):,}")
    q4.metric("Stations without coordinates", f"{len(no_coords)}")

    if status.get("missing_columns"):
        st.warning("Columns missing in the sheet (filled empty): " + ", ".join(status["missing_columns"]))
    if status.get("bad_dates"):
        st.warning(f"{status['bad_dates']} row(s) have a DATE that could not be read (dates are read day-first, dd/mm/yyyy). "
                   "They are excluded from date-based views.")
    if status.get("blank_dates"):
        st.info(f"{status['blank_dates']} row(s) have no DATE and are excluded from date-based views.")

    if no_coords:
        section("Stations missing from the coordinate table")
        st.write(", ".join(no_coords))
    if not unclassified.empty:
        section("Unclassified station / department combinations")
        combos = unclassified.groupby([COL_STATION, COL_DEPT], dropna=False).size().reset_index(name="Rows").sort_values("Rows", ascending=False)
        st.dataframe(combos.fillna("(blank)"), hide_index=True, **STRETCH)
    gaps = []
    for s in stations:
        missing = [name for name, mp in JURISDICTION_TABLES.items() if _key(s) not in mp]
        if missing:
            gaps.append({"STATION": s, "Not in jurisdiction table(s)": ", ".join(missing)})
    if gaps:
        section("Stations missing from jurisdiction tables")
        st.dataframe(pd.DataFrame(gaps), hide_index=True, **STRETCH)
    if not (no_coords or len(unclassified) or gaps or status.get("bad_dates")):
        st.success("No data-quality problems found.")


# ====================== SESSION STATE ======================
for _k, _v in {"logged_in": False, "user_name": "", "map_selected_station": None, "_map_epoch": 0,
               "_last_map_click": None, "_fail_count": 0, "_locked_until": 0.0,
               "_last_active": time.time(), "_last_refresh": 0.0}.items():
    st.session_state.setdefault(_k, _v)


# ====================== MAIN ======================
def main():
    css = CUSTOM_CSS.replace("__FONT_FACES__", _font_face_css())
    st.markdown(css, unsafe_allow_html=True)

    if not st.session_state.logged_in:
        login_page()
        return
    if time.time() - st.session_state["_last_active"] > SESSION_TIMEOUT_SECONDS:
        st.session_state["_last_active"] = time.time()
        logout()
        return
    st.session_state["_last_active"] = time.time()

    logo = get_logo_bytes()
    if logo:
        b64 = base64.b64encode(logo).decode()
        st.markdown(f'<div class="watermark"><img src="data:image/png;base64,{b64}" alt=""></div>', unsafe_allow_html=True)
        _, c2, _ = st.columns([3, 2, 3])
        with c2:
            st.image(logo, width=150)
    st.markdown('<div class="drishti-title">Data-Logger</div><div class="drishti-line"></div>'
                '<div class="drishti-fullform">Data-Logger Exceptional Report</div>', unsafe_allow_html=True)
    st.markdown('<div class="train-emoji-container"><div class="train-track">🚄 🚄 🚄 🚄</div></div>', unsafe_allow_html=True)
    st.markdown('<p class="brand-line">Central Railway &nbsp;•&nbsp; Solapur Division &nbsp;•&nbsp; Safety Branch</p>', unsafe_allow_html=True)
    st.caption(f"**Logged in as:** {st.session_state.user_name}")

    # ---- sidebar: data source + controls ----
    with st.sidebar:
        st.header("🔧 Controls")
        force_offline = st.toggle("📴 Work offline (use saved snapshot)", key="force_offline")

    df_original, status = load_data(force_offline)
    if df_original is None:
        st.error("Could not load data, and no offline snapshot exists yet. Connect to the internet once so a snapshot can be saved.")
        st.stop()

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
            if time.time() - st.session_state["_last_refresh"] < REFRESH_COOLDOWN_SECONDS:
                st.warning("Please wait a few seconds before refreshing again.")
            else:
                st.session_state["_last_refresh"] = time.time()
                st.cache_data.clear()
                st.session_state.pop("_online_retry_at", None)
                st.session_state.map_selected_station = None
                st.rerun()
        use_tiles = st.checkbox("Load online map tiles", value=(status["mode"] == "live"),
                                help="Turn off when there is no internet; markers still work.")
        st.divider()
        selections, from_date, to_date = render_filters(df_original)
        st.divider()
        if st.button("🚪 Logout", **STRETCH):
            logout()

    forecast_base_df = apply_category_filters(df_original, selections)
    filtered_df = apply_date_month_filters(forecast_base_df, selections, from_date, to_date)
    sig = repr((sorted((k, tuple(v)) for k, v in selections.items()), str(from_date), str(to_date), len(filtered_df), status.get("loaded_at")))

    station_summary = summarize(filtered_df, COL_STATION)
    cat_sum = summarize(filtered_df, COL_DEPT)
    error_sum = summarize(filtered_df, COL_ERROR)
    jur_sum = summarize(filtered_df, COL_JUR)

    tab_overview, tab_forecast, tab_map, tab_quality = st.tabs(
        ["📊 Overview Dashboard", "🔮 Forecast (3 Months)", "🗺️ Map View", "🩺 Data Quality"])
    with tab_overview:
        render_overview(filtered_df, station_summary, cat_sum, error_sum, jur_sum, sig, status, st.session_state.user_name)
    with tab_forecast:
        render_forecast(forecast_base_df, sig)
    with tab_map:
        render_map(filtered_df, station_summary, jur_sum, use_tiles, sig)
    with tab_quality:
        render_quality(df_original, status)

    st.caption("🚄 Data-Logger | Safety Branch | Central Railway, Solapur Division")


main()
