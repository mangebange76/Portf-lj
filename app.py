import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import gspread
from google.oauth2.service_account import Credentials
from forex_python.converter import CurrencyRates

# --- Autentisering mot Google Sheets ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

# --- Inställningar ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SmX-5TU1cPN2K8eLKGTGkCPeqj3J-89nuT9zKlI2_sY/edit"
SHEET_NAME = "Portfölj"

# --- Ladda arket ---
def load_data():
    spreadsheet = client.open_by_url(SHEET_URL)
    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows="1000", cols="20")
        worksheet.append_row(["Bolag", "Ticker", "Antal", "Valuta", "Kategori", "Målvikt (%)", "Tillväxt (%)", "P/S TTM"])
    data = worksheet.get_all_records()
    return pd.DataFrame(data), worksheet

# --- Hämta valutakurser ---
@st.cache_data(ttl=3600)
def get_exchange_rates():
    c = CurrencyRates()
    return {
        "USD": c.get_rate("USD", "SEK"),
        "NOK": c.get_rate("NOK", "SEK"),
        "CAD": c.get_rate("CAD", "SEK"),
        "SEK": 1.0
    }

# --- Hämta aktiekurser ---
@st.cache_data(ttl=600)
def get_price(ticker):
    try:
        info = yf.Ticker(ticker).info
        return info.get("regularMarketPrice", 0)
    except:
        return 0

# --- Hämta utdelningar ---
@st.cache_data(ttl=3600)
def get_dividends(ticker):
    try:
        div = yf.Ticker(ticker).dividends
        upcoming = div[div.index > datetime.datetime.now() - datetime.timedelta(days=5)]
        return upcoming
    except:
        return pd.Series()

# --- Räkna portfölj och köp-rek ---
def calculate(df, kapital, rates):
    total_value = 0
    bolag_data = []

    for _, row in df.iterrows():
        ticker, antal, valuta = row["Ticker"], row["Antal"], row["Valuta"]
        pris = get_price(ticker)
        kurs_sek = pris * rates.get(valuta, 1)
        värde = antal * kurs_sek
        total_value += värde
        bolag_data.append({**row, "Kurs SEK": kurs_sek, "Värde": värde})

    portfölj_df = pd.DataFrame(bolag_data)
    portfölj_df["Vikt (%)"] = (portfölj_df["Värde"] / total_value * 100).round(2)
    portfölj_df["Undervikt (%)"] = (portfölj_df["Målvikt (%)"] - portfölj_df["Vikt (%)"]).round(2)
    portfölj_df["Köp (SEK)"] = ((portfölj_df["Undervikt (%)"] / 100) * (total_value + kapital)).round(0)

    return portfölj_df, total_value

# --- Visa appen ---
def main():
    st.set_page_config(page_title="Portföljanalys", layout="centered")
    st.title("📊 Din Portföljöversikt")

    kapital = st.number_input("💰 Tillgängligt kapital (SEK):", min_value=0, step=100, value=1000, key="kapital")

    df, worksheet = load_data()
    rates = get_exchange_rates()
    portfölj_df, total_value = calculate(df, kapital, rates)

    st.subheader("📦 Totalt portföljvärde:")
    st.metric(label="Portföljvärde i SEK", value=f"{int(total_value):,} kr".replace(",", " "))

    st.subheader("🛍️ Investeringsförslag")
    köp_df = portfölj_df.sort_values("Undervikt (%)", ascending=False).head(5)
    st.dataframe(köp_df[["Bolag", "Ticker", "Undervikt (%)", "Köp (SEK)"]])

    st.subheader("📈 Portföljinnehav")
    st.dataframe(portfölj_df[["Bolag", "Ticker", "Antal", "Kurs SEK", "Värde", "Vikt (%)", "Målvikt (%)"]])

    st.subheader("💸 Utdelningsprognos (kommande)")
    total_div = 0
    for _, row in df.iterrows():
        ticker, antal = row["Ticker"], row["Antal"]
        div = get_dividends(ticker)
        if not div.empty:
            senaste = div.tail(1)
            if not senaste.empty:
                värde = senaste.values[0] * antal * rates.get(row["Valuta"], 1)
                total_div += värde
    st.write(f"📅 Bekräftade utdelningar denna månad: **{round(total_div)} kr**")

if __name__ == "__main__":
    main()
