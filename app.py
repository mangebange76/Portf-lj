import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

# Autentisering
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)
SHEET_URL = st.secrets["SHEET_URL"]
spreadsheet = client.open_by_url(SHEET_URL)
worksheet = spreadsheet.sheet1

# Hämta data från Google Sheets
def load_data():
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

# Hämta valutakurser från ECB
def get_exchange_rates():
    try:
        response = requests.get("https://api.exchangerate.host/latest?base=USD")
        rates = response.json().get("rates", {})
        return {
            "USD": 1,
            "SEK": rates.get("SEK", 11.0),
            "EUR": rates.get("EUR", 0.91),
            "NOK": rates.get("NOK", 10.5),
            "DKK": rates.get("DKK", 6.8)
        }
    except:
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {
            "USD": 1,
            "SEK": 11.0,
            "EUR": 0.91,
            "NOK": 10.5,
            "DKK": 6.8
        }

# Räkna ut värden i SEK
def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map(exchange_rates)
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
    total_value = df["Värde SEK"].sum()
    return df, total_value

# Spara ändringar tillbaka till Google Sheets
def save_to_gsheet(df):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

# Huvudfunktion
def main():
    st.title("📈 Aktieportfölj")

    exchange_rates = get_exchange_rates()
    df = load_data()

    st.subheader("Innehav")
    edited_df = st.data_editor(df, num_rows="dynamic")

    if st.button("💾 Spara ändringar"):
        save_to_gsheet(edited_df)
        st.success("Ändringar sparade!")

    df, total_value = calculate_portfolio_value(edited_df, exchange_rates)

    st.metric("📊 Totalt portföljvärde (SEK)", f"{total_value:,.0f} kr")

    st.subheader("Valutakurser")
    st.json(exchange_rates)

if __name__ == "__main__":
    main()
