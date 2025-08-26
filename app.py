# streamlit run app.py
import os
import math
import requests
import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

# ---------- Config ----------
st.set_page_config(page_title="Mindat Mineral Finder (Personal)", layout="wide")
load_dotenv()  # load .env if present

API_BASE = os.getenv("MINDAT_API_BASE", "https://api.mindat.org/v1")
API_TOKEN = os.getenv("MINDAT_API_TOKEN", "").strip()

# ---------- Helpers ----------
class APIError(Exception):
    pass

def auth_headers():
    if not API_TOKEN:
        return {}
    # Try "Token" first; switch to "Bearer" if you get 401/403
    return {"Authorization": f"Token {API_TOKEN}"}

@retry(reraise=True, stop=stop_after_attempt(3),
       wait=wait_exponential(min=0.5, max=6),
       retry=retry_if_exception_type((requests.RequestException, APIError)))
def api_get(path: str, params: dict):
    url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
    r = requests.get(url, params=params, headers=auth_headers(), timeout=30)
    if r.status_code >= 400:
        raise APIError(f"API error {r.status_code}: {r.text[:200]}")
    return r.json()

@st.cache_data(show_spinner=False, ttl=3600)
def cached_query(params: dict, page: int, page_size: int):
    q = dict(params)
    q.update({"page": page, "page_size": page_size})
    return api_get("minerals", q)

def to_range_label(vmin, vmax, unit=""):
    if vmin is None and vmax is None:
        return "—"
    if vmin is None: return f"≤ {vmax}{unit}"
    if vmax is None: return f"≥ {vmin}{unit}"
    return f"{vmin}–{vmax}{unit}" if vmin != vmax else f"{vmin}{unit}"

# ---------- UI ----------
st.title("🔎 Mindat Mineral Finder (Personal Use)")

if not API_TOKEN:
    st.warning("Add your MINDAT_API_TOKEN as a secret in Streamlit Cloud or in a .env file locally.")

st.sidebar.header("Filters")
hardness = st.sidebar.slider("Mohs hardness", 0.0, 10.0, (0.0, 10.0))
sg = st.sidebar.slider("Specific gravity", 0.5, 8.0, (0.5, 8.0))
luster = st.sidebar.multiselect("Luster", ["adamantine","vitreous","resinous","pearly","silky","waxy","metallic","dull","earthy"])
streak = st.sidebar.multiselect("Streak", ["white","black","gray","brown","red","yellow","green","blue","purple"])
page_size = st.sidebar.selectbox("Page size", [10, 20, 50], index=0)
page = st.sidebar.number_input("Page", min_value=1, value=1)

params = {}
params["hardness_min"], params["hardness_max"] = hardness
params["sg_min"], params["sg_max"] = sg
if luster: params["luster__in"] = ",".join(luster)
if streak: params["streak__in"] = ",".join(streak)

with st.spinner("Querying Mindat…"):
    try:
        data = cached_query(params, page, page_size)
        results = data.get("results") or data.get("data") or []
        total = data.get("count") or len(results)
    except Exception as e:
        st.error(f"Request failed: {e}")
        results, total = [], 0

st.write(f"**Results:** {len(results)} shown (of {total})")

for item in results:
    name = item.get("name", "Unnamed")
    formula = item.get("formula", "")
    mohs_min, mohs_max = item.get("hardness_min"), item.get("hardness_max")
    sgmin, sgmax = item.get("sg_min"), item.get("sg_max")
    lstr = item.get("luster")
    mindat_url = item.get("url") or item.get("mindat_url")

    with st.container(border=True):
        st.subheader(name)
        if mindat_url:
            st.markdown(f"[Mindat page]({mindat_url})")
        if formula:
            st.markdown(f"**Formula:** `{formula}`")
        st.markdown(
            f"- **Mohs:** {to_range_label(mohs_min, mohs_max)}\n"
            f"- **Specific gravity:** {to_range_label(sgmin, sgmax)}\n"
            f"- **Luster:** {lstr or '—'}"
        )
