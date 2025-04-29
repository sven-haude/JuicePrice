# main.py – Strompreis-Dashboard 2025  (FINAL)
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, date, time, timedelta
from collections.abc import Sequence
import pytz
import plotly
import plotly.express as px

# ------------------------------------------------------------
st.set_page_config(page_title="Strompreis-Dashboard", layout="wide")
st.title("💡 Strompreis-Dashboard")
st.caption("Spotmarkt Day-Ahead · Quelle: aWATTar / EPEX Spot")

tz = pytz.timezone("Europe/Berlin")
today = date.today()
default_start = today
default_end   = today if datetime.now().hour < 14 else today + timedelta(days=1)

# ------------------------------------------------------------
# Zeitraumwahl + „Jetzt“-Button
# ------------------------------------------------------------
col_date, col_btn = st.columns([4, 1])
with col_date:
    raw_date = st.date_input("Zeitraum auswählen",
                             value=(default_start, default_end))
with col_btn:
    jump_now = st.button("⏱ Jetzt", help="Aktuellen Zeitraum wählen")

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

# ------------------------------------------------------------
# Netto/Brutto-Schalter
# ------------------------------------------------------------
add_brutto  = st.toggle("Bruttopreise (inkl. aller Steuern & Abgaben)", value=False)

STROMSTEUER = 2.05
KONZ_ABGABE = 1.667
KWK_UMLAGE  = 0.277
PAR19_NE    = 1.558
OFFSHORE    = 0.816
SUM_ABGABEN = STROMSTEUER + KONZ_ABGABE + KWK_UMLAGE + PAR19_NE + OFFSHORE
MWST        = 1.19

# ------------------------------------------------------------
# API-Abruf
# ------------------------------------------------------------
start_dt = tz.localize(datetime.combine(start_date, time.min))
end_dt   = tz.localize(datetime.combine(end_date + timedelta(days=1), time.min))
params   = {"start": int(start_dt.timestamp() * 1000),
            "end":   int(end_dt.timestamp()   * 1000)}

API_URL = "https://api.awattar.de/v1/marketdata"
try:
    data = requests.get(API_URL, params=params, timeout=10).json()["data"]
except Exception as e:
    st.error(f"REST-Fehler: {e}")
    st.stop()
if not data:
    st.warning("Keine Daten für diesen Zeitraum.")
    st.stop()

# ------------------------------------------------------------
# DataFrame
# ------------------------------------------------------------
df = pd.DataFrame(data)
df["time"] = (pd.to_datetime(df["start_timestamp"], unit="ms", utc=True)
              .dt.tz_convert("Europe/Berlin")
              .dt.tz_localize(None))
df["net_ct_per_kwh"]   = df["marketprice"] / 10.0
df["gross_ct_per_kwh"] = (df["net_ct_per_kwh"] + SUM_ABGABEN) * MWST
df.sort_values("time", inplace=True, ignore_index=True)

# ------------------------------------------------------------
# Aktueller Preis + Marker-Zeit
# ------------------------------------------------------------
now_local   = datetime.now(tz).replace(tzinfo=None)
marker_time = None
if df["time"].min() <= now_local <= df["time"].max():
    marker_time = df.loc[df[df["time"] <= now_local].index.max(), "time"]
    col_price   = "gross_ct_per_kwh" if add_brutto else "net_ct_per_kwh"
    cur_val     = df.loc[df["time"] == marker_time, col_price].iat[0]
    st.metric("Aktueller Preis", f"{cur_val:.2f} ct/kWh",
              help=f"Gültig {marker_time:%d.%m.%Y %H:%M}–"
                   f"{(marker_time+timedelta(hours=1)):%H:%M}")

# ------------------------------------------------------------
# Plotly-Chart
# ------------------------------------------------------------
y_col = "gross_ct_per_kwh" if add_brutto else "net_ct_per_kwh"
y_lab = "Preis (ct/kWh) " + ("brutto" if add_brutto else "netto")

fig = px.line(df, x="time", y=y_col,
              labels={"time": "Zeit", y_col: y_lab},
              title="Strompreis-Zeitreihe")
fig.update_traces(mode="lines+markers")

# Stunden-Ticks HH:MM
fig.update_xaxes(dtick=3600000, tickformat="%H:%M", ticklabelmode="period")

# Marker-Linie – jetzt als ISO-String
if marker_time is not None:
    fig.add_vline(
        x=marker_time.isoformat(),
        line_color="red", line_dash="dot", line_width=2,
        annotation_text="Jetzt", annotation_position="top"
    )

# Interaktion fixieren
fig.update_layout(
    hovermode="x unified",
    xaxis_fixedrange=True,
    yaxis_fixedrange=True,
    autosize=True
)

st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# Fußnote
# ------------------------------------------------------------
footer = ("Bruttopreise inkl. MwSt & Abgaben"
          if add_brutto else "Nettopreise (Spotmarkt)")
footer += " · Folgetags-Daten täglich gegen 14 Uhr."
st.caption(footer)