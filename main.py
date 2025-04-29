# main.py  – Strompreis-Dashboard
# --------------------------------
# • REST-Abruf der Day-Ahead-Spotpreise (aWATTar)
# • Datumsbereich + „Jetzt“-Button
# • Netto / Brutto (19 % MwSt) Umschalter
# • Interaktives Plotly-Liniendiagramm
# --------------------------------
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
from collections.abc import Sequence
import pytz
import plotly.express as px   # -> pip install plotly

# ------------------------------------------------------------------
# Grundeinstellungen
# ------------------------------------------------------------------
st.set_page_config(page_title="Strompreis-Dashboard", layout="wide")
st.title("💡 Strompreis-Dashboard")
st.caption("Day-Ahead Spotpreise · Quelle: aWATTar / EPEX Spot")

tz = pytz.timezone("Europe/Berlin")
today = date.today()
default_start = today
default_end   = today if datetime.now().hour < 14 else today + timedelta(days=1)

# ------------------------------------------------------------------
# 1) Zeitraum + „Jetzt“-Button
# ------------------------------------------------------------------
col_date, col_btn = st.columns([4, 1])

with col_date:
    raw_date = st.date_input(
        "Zeitraum auswählen",
        value=(default_start, default_end),
    )

with col_btn:
    jump_now = st.button("⏱ Jetzt", help="Aktuellen Zeitraum (heute / ggf. morgen) wählen")

# raw_date kann date, tuple oder list sein
if jump_now:
    start_date, end_date = default_start, default_end
else:
    if isinstance(raw_date, Sequence):
        if len(raw_date) == 1:
            start_date = end_date = raw_date[0]
        else:
            start_date, end_date = raw_date[0], raw_date[1]
    else:
        start_date = end_date = raw_date

# ------------------------------------------------------------------
# 2) Netto / Brutto-Schalter
# ------------------------------------------------------------------
add_vat   = st.toggle("Bruttopreise anzeigen (inkl. 19 % MwSt)", value=False)
vat_factor = 1.19 if add_vat else 1.00

# ------------------------------------------------------------------
# 3) API-Parameter (Epoch-Millis)
# ------------------------------------------------------------------
start_dt = tz.localize(datetime.combine(start_date, time.min))
end_dt   = tz.localize(datetime.combine(end_date + timedelta(days=1), time.min))
params   = {"start": int(start_dt.timestamp() * 1000),
            "end":   int(end_dt.timestamp()   * 1000)}

# ------------------------------------------------------------------
# 4) API-Abruf
# ------------------------------------------------------------------
API_URL = "https://api.awattar.de/v1/marketdata"
try:
    resp = requests.get(API_URL, params=params, timeout=10)
    resp.raise_for_status()
except Exception as e:
    st.error(f"Fehler beim Abruf der Preisdaten: {e}")
    st.stop()

data = resp.json().get("data", [])
if not data:
    st.warning("Keine Preisdaten für den gewählten Zeitraum verfügbar.")
    st.stop()

# ------------------------------------------------------------------
# 5) DataFrame aufbereiten
# ------------------------------------------------------------------
df = pd.DataFrame(data)
df["time"] = (
    pd.to_datetime(df["start_timestamp"], unit="ms", utc=True)
      .dt.tz_convert("Europe/Berlin")
      .dt.tz_localize(None)
)
# EUR/MWh → ct/kWh und ggf. MwSt
df["price_ct_per_kwh"] = (df["marketprice"] / 10.0) * vat_factor
df.sort_values("time", inplace=True, ignore_index=True)

# ------------------------------------------------------------------
# 6) Aktueller Preis (laufende Stunde)
# ------------------------------------------------------------------
now_local = datetime.now(tz).replace(tzinfo=None)
if df["time"].min() <= now_local <= df["time"].max():
    cur_row = df.loc[df[df["time"] <= now_local].index.max()]
    st.metric(
        "Aktueller Preis",
        f"{cur_row['price_ct_per_kwh']:.2f} ct/kWh",
        help=f"Gültig {cur_row['time']:%d.%m.%Y %H:%M}–"
             f"{(cur_row['time']+timedelta(hours=1)):%H:%M}",
    )

# ------------------------------------------------------------------
# 7) Diagramm
# ------------------------------------------------------------------
label_y = "Preis (ct/kWh) " + ("inkl. 19 % MwSt" if add_vat else "netto")
fig = px.line(
    df,
    x="time",
    y="price_ct_per_kwh",
    labels={"time": "Zeit", "price_ct_per_kwh": label_y},
    title="Strompreis-Zeitreihe",
)
fig.update_traces(mode="lines+markers")
fig.update_layout(hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------
# 8) Fußnote (Syntax gefixt)
# ------------------------------------------------------------------
footer_text = (
    "Bruttopreise inkl. 19 % MwSt · "
    if add_vat
    else "Nettopreise ohne MwSt · "
)
footer_text += "Werte für den Folgetag erscheinen täglich gegen 14 Uhr."
st.caption(footer_text)