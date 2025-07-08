import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

# Konfiguration
scope = ["https://www.googleapis.com/auth/spreadsheets"]
credentials = Credentials.from_service_account_info(
    st.secrets["GOOGLE_CREDENTIALS"], scopes=scope
)
client = gspread.authorize(credentials)
SHEET_URL = st.secrets["SHEET_URL"]

def get_exchange_rates():
    try:
        response = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=SEK,EUR")
        data = response.json()
        return {
            "USD": data["rates"]["SEK"],
            "EUR": data["rates"]["SEK"] / data["rates"]["EUR"],
            "SEK": 1.0
        }
    except:
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {"USD": 10.0, "EUR": 11.0, "SEK": 1.0}

def load_data():
    sheet = client.open_by_url(SHEET_URL)
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    return pd.DataFrame(data), worksheet

def save_to_sheet(df, worksheet):
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map(exchange_rates)
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
    total_value = df["Värde SEK"].sum()
    return df, total_value

def main():
    st.title("📈 Aktieportfölj")
    exchange_rates = get_exchange_rates()
    df, worksheet = load_data()
    df, total_value = calculate_portfolio_value(df, exchange_rates)

    st.metric("Totalt portföljvärde (SEK)", f"{total_value:,.0f} kr")
    st.dataframe(df)

    with st.expander("Lägg till nytt innehav"):
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input("Ticker")
            antal = st.number_input("Antal", min_value=0.0, step=1.0)
            kurs = st.number_input("Kurs", min_value=0.0)
        with col2:
            valuta = st.selectbox("Valuta", ["SEK", "USD", "EUR"])
            datum = st.date_input("Datum", value=datetime.today())
        if st.button("Spara innehav"):
            new_row = {
                "Ticker": ticker,
                "Antal": antal,
                "Kurs": kurs,
                "Valuta": valuta,
                "Datum": datum.strftime("%Y-%m-%d")
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            save_to_sheet(df, worksheet)
            st.success("Innehavet har sparats.")

if __name__ == "__main__":
    main()
