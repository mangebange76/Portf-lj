import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

# --- AUTENTISERING ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope
)
client = gspread.authorize(credentials)

SHEET_URL = st.secrets["SHEET_URL"]

# --- HÄMTA & SPARA DATA ---
def load_data():
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)

    if df.empty:
        df = pd.DataFrame(columns=["Ticker", "Antal", "Kurs", "Valuta", "Kategori"])

    return df, worksheet

def save_data(df, worksheet):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# --- HÄMTA VALUTAKURSER ---
@st.cache_data(ttl=3600)
def get_exchange_rates():
    try:
        response = requests.get("https://api.exchangerate.host/latest?base=USD")
        if response.status_code == 200:
            data = response.json()
            return {
                "USD": 1.0,
                "SEK": data["rates"].get("SEK", 10.0),
                "EUR": data["rates"].get("EUR", 0.9)
            }
    except:
        pass
    return {"USD": 1.0, "SEK": 10.0, "EUR": 0.9}

# --- BERÄKNA VÄRDE ---
def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map(exchange_rates)
    df["Värde SEK"] = df["Antal"].astype(float) * df["Kurs"].astype(float) * df["Valutakurs"]
    total_value = df["Värde SEK"].sum()
    return df, total_value

# --- UTDATA ---
def render_summary(df, total_value):
    st.metric("📊 Totalt portföljvärde (SEK)", f"{total_value:,.0f} kr")
    grouped = df.groupby("Kategori")["Värde SEK"].sum().reset_index()
    st.bar_chart(grouped.set_index("Kategori"))

# --- REDIGERA INNEHAV ---
def edit_holding(df, worksheet):
    tickers = df["Ticker"].tolist()
    selected = st.selectbox("Välj innehav att redigera", tickers)

    if selected:
        row = df[df["Ticker"] == selected].iloc[0]
        antal = st.number_input("Antal", value=float(row["Antal"]), step=1.0)
        kurs = st.number_input("Kurs", value=float(row["Kurs"]), step=0.1)
        valuta = st.selectbox("Valuta", ["USD", "SEK", "EUR"], index=["USD", "SEK", "EUR"].index(row["Valuta"]))
        kategori = st.selectbox("Kategori", ["Tillväxt", "Utdelning"], index=["Tillväxt", "Utdelning"].index(row["Kategori"]))
        kommentar = st.text_input("Kommentar", value=row["Kommentar"])

        if st.button("Spara ändringar"):
            df.loc[df["Ticker"] == selected, ["Antal", "Kurs", "Valuta", "Kategori", "Kommentar"]] = [antal, kurs, valuta, kategori, kommentar]
            idx = df[df["Ticker"] == selected].index[0] + 2  # +2 för header i Google Sheets
            worksheet.update(f"B{idx}:F{idx}", [[antal, kurs, valuta, kategori, kommentar]])
            st.success("Ändringar sparade.")

# --- LÄGG TILL NYTT INNEHAV ---
def add_new_holding(df, worksheet):
    st.subheader("Lägg till nytt innehav")
    ticker = st.text_input("Ticker")
    namn = st.text_input("Namn")
    antal = st.number_input("Antal", min_value=0.0, step=1.0)
    kurs = st.number_input("Kurs", min_value=0.0, step=0.1)
    valuta = st.selectbox("Valuta", ["USD", "SEK", "EUR"])
    kategori = st.selectbox("Kategori", ["Tillväxt", "Utdelning"])
    kommentar = st.text_input("Kommentar")

    if st.button("Lägg till"):
        if ticker and namn:
            ny_rad = {
                "Ticker": ticker,
                "Namn": namn,
                "Antal": antal,
                "Kurs": kurs,
                "Valuta": valuta,
                "Kategori": kategori,
                "Kommentar": kommentar
            }
            worksheet.append_row(list(ny_rad.values()))
            st.success(f"{ticker} tillagt!")
        else:
            st.error("Ticker och Namn krävs.")

# --- RADERA INNEHAV ---
def delete_holding(df, worksheet):
    st.subheader("Radera innehav")
    tickers = df["Ticker"].tolist()
    selected = st.selectbox("Välj innehav att radera", tickers)

    if st.button("Radera rad"):
        idx = df[df["Ticker"] == selected].index[0] + 2  # +2 för header
        worksheet.delete_rows(idx)
        st.success(f"{selected} raderat.")

# --- VISA HISTORIK ---
def show_dividend_forecast(df):
    st.subheader("Utdelningsprognos framåt")
    prognos = df[df["Kategori"] == "Utdelning"].copy()
    prognos["Förväntad utdelning (SEK)"] = (
        prognos["Antal"] * prognos["Utdelning"] * prognos["Valutakurs"]
    )
    prognos = prognos[["Ticker", "Namn", "Antal", "Utdelning", "Valutakurs", "Förväntad utdelning (SEK)", "Kommentar"]]
    prognos = prognos[prognos["Förväntad utdelning (SEK)"] > 0]

    if not prognos.empty:
        st.dataframe(prognos, use_container_width=True)
        total = prognos["Förväntad utdelning (SEK)"].sum()
        st.metric("Total prognos", f"{total:,.0f} kr")
    else:
        st.info("Inga utdelningar registrerade ännu.")

# --- HISTORISKT UTVECKLING (PLATSHÅLLARE) ---
def show_historical_view():
    st.subheader("Utvecklingshistorik (under uppbyggnad)")
    st.info("Denna funktion kommer visa portföljutveckling dagligen, veckovis, månad etc. – funktionalitet är planerad.")

# --- HUVUDFUNKTION ---
def main():
    st.set_page_config(page_title="Portföljöversikt", layout="wide")
    st.title("📈 Investeringsportfölj")

    exchange_rates = get_exchange_rates()
    df, worksheet = load_data()

    df = df.fillna({"Antal": 0, "Kurs": 0, "Valuta": "USD", "Kategori": "", "Utdelning": 0, "Kommentar": ""})
    df["Antal"] = pd.to_numeric(df["Antal"], errors="coerce").fillna(0)
    df["Kurs"] = pd.to_numeric(df["Kurs"], errors="coerce").fillna(0)
    df["Utdelning"] = pd.to_numeric(df["Utdelning"], errors="coerce").fillna(0)

    df["Valutakurs"] = df["Valuta"].map(exchange_rates).fillna(1)
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]

    total_value = df["Värde SEK"].sum()
    st.metric("Totalt värde", f"{total_value:,.0f} kr")

    tab1, tab2, tab3, tab4 = st.tabs(["📊 Översikt", "➕ Lägg till / ändra", "🗑️ Radera", "💸 Utdelningar"])

    with tab1:
        st.dataframe(df[["Ticker", "Namn", "Antal", "Kurs", "Valuta", "Valutakurs", "Värde SEK", "Kategori", "Kommentar"]], use_container_width=True)

    with tab2:
        add_or_update_holding(df, worksheet, exchange_rates)

    with tab3:
        delete_holding(df, worksheet)

    with tab4:
        show_dividend_forecast(df)
        show_historical_view()

if __name__ == "__main__":
    main()
