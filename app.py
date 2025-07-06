import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import requests
from datetime import datetime
from forex_python.converter import CurrencyRates

# Anslut till Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file"]
credentials = Credentials.from_service_account_info(
    json.loads(st.secrets["GOOGLE_CREDENTIALS"]), scopes=scope)
client = gspread.authorize(credentials)

SHEET_URL = "https://docs.google.com/spreadsheets/d/1SmX-5TU1cPN2K8eLKGTGkCPeqj3J-89nuT9zKlI2_sY/edit?usp=drivesdk"

def load_data():
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df, worksheet

def fetch_exchange_rates():
    try:
        c = CurrencyRates()
        return {
            "USD": c.get_rate("USD", "SEK"),
            "NOK": c.get_rate("NOK", "SEK"),
            "CAD": c.get_rate("CAD", "SEK")
        }
    except:
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {"USD": 10.0, "NOK": 1.0, "CAD": 7.5}

def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map(exchange_rates)
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
    total_value = df["Värde SEK"].sum()
    return df, total_value

def show_summary(df, total_value):
    st.header("📊 Sammanfattning")
    st.metric("Totalt portföljvärde (SEK)", f"{total_value:,.0f} kr")
    grouped = df.groupby("Kategori")["Värde SEK"].sum()
    for kategori, värde in grouped.items():
        procent = värde / total_value * 100
        st.write(f"- **{kategori}**: {värde:,.0f} kr ({procent:.1f}%)")

def edit_holdings(df, worksheet):
    st.header("✏️ Redigera innehav")
    index = st.selectbox("Välj rad att redigera", df.index)
    row = df.loc[index]
    with st.form(key="edit_form"):
        antal = st.number_input("Antal", value=row["Antal"])
        kurs = st.number_input("Senaste kurs", value=row["Kurs"])
        submitted = st.form_submit_button("Spara ändringar")
        if submitted:
            worksheet.update_cell(index + 2, df.columns.get_loc("Antal") + 1, antal)
            worksheet.update_cell(index + 2, df.columns.get_loc("Kurs") + 1, kurs)
            st.success("Uppdaterat! Ladda om sidan för att se ändringarna.")

def add_transaction(worksheet, df):
    st.header("➕ Lägg till nytt innehav")
    with st.form(key="add_form"):
        namn = st.text_input("Bolagsnamn")
        ticker = st.text_input("Ticker")
        antal = st.number_input("Antal", min_value=0)
        valuta = st.selectbox("Valuta", ["USD", "NOK", "CAD"])
        kurs = st.number_input("Senaste kurs")
        kategori = st.selectbox("Kategori", ["Tillväxt", "Utdelning", "Övrigt"])
        submitted = st.form_submit_button("Lägg till")
        if submitted and namn:
            ny_rad = [namn, ticker, antal, valuta, kurs, kategori]
            worksheet.append_row(ny_rad)
            st.success("Innehavet har lagts till!")

def main():
    st.title("📈 Min Aktieportfölj")
    exchange_rates = fetch_exchange_rates()
    df, worksheet = load_data()
    df, total_value = calculate_portfolio_value(df, exchange_rates)

    st.sidebar.header("Navigering")
    sida = st.sidebar.radio("Gå till", ["Översikt", "Redigera innehav", "Lägg till innehav"])

    if sida == "Översikt":
        show_summary(df, total_value)
        st.dataframe(df)
    elif sida == "Redigera innehav":
        edit_holdings(df, worksheet)
    elif sida == "Lägg till innehav":
        add_transaction(worksheet, df)

if __name__ == "__main__":
    main()
