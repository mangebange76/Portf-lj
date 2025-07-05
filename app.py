import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(page_title="Portföljöversikt", layout="wide")

# 🔐 Autentisering med Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

# 🔗 Länk till ditt Google Sheet
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SmX-5TU1cPN2K8eLKGTGkCPeqj3J-89nuT9zKlI2_sY/edit"
SHEET_ID = SHEET_URL.split("/d/")[1].split("/")[0]

@st.cache_data(ttl=86400)  # cacha i 24 timmar
def get_exchange_rates():
    url = "https://api.exchangerate.host/latest?base=USD"
    try:
        response = requests.get(url)
        data = response.json()
        return {
            "USDSEK": data["rates"]["SEK"],
            "CADSEK": data["rates"]["SEK"] / data["rates"]["CAD"],
            "NOKSEK": data["rates"]["SEK"] / data["rates"]["NOK"],
        }
    except:
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {
            "USDSEK": 10.50,
            "CADSEK": 7.80,
            "NOKSEK": 1.00,
        }

def load_data():
    spreadsheet = client.open_by_key(SHEET_ID)
    worksheet = spreadsheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df, worksheet

def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map({
        "USD": exchange_rates["USDSEK"],
        "NOK": exchange_rates["NOKSEK"],
        "CAD": exchange_rates["CADSEK"]
    })
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
    total = df["Värde SEK"].sum()
    return df, total

def main():
    st.title("📈 Portföljöversikt – tillväxt & utdelning")
    df, worksheet = load_data()
    exchange_rates = get_exchange_rates()

    df, total_value = calculate_portfolio_value(df, exchange_rates)

    st.subheader("Nuvarande innehav")
    st.dataframe(df[["Bolag", "Ticker", "Antal", "Valuta", "Kurs", "Värde SEK"]])

    st.markdown(f"**Totalt portföljvärde:** `{total_value:,.0f}` SEK")

    with st.expander("➕ Lägg till nytt innehav"):
        with st.form("add_form", clear_on_submit=True):
            bolag = st.text_input("Bolag")
            ticker = st.text_input("Ticker")
            antal = st.number_input("Antal aktier", min_value=0)
            valuta = st.selectbox("Valuta", ["USD", "NOK", "CAD"])
            kurs = st.number_input("Aktuell kurs", min_value=0.0)
            submit = st.form_submit_button("Lägg till")
            if submit and bolag and ticker and antal > 0 and kurs > 0:
                ny_rad = [bolag, ticker, antal, valuta, kurs]
                worksheet.append_row(ny_rad)
                st.success("Innehavet har lagts till.")
                st.stop()

    with st.expander("🗑️ Ta bort bolag"):
        namnlista = df["Bolag"].tolist()
        val = st.selectbox("Välj bolag att ta bort", namnlista)
        if st.button("Ta bort"):
            index = df[df["Bolag"] == val].index[0]
            worksheet.delete_rows(index + 2)
            st.success(f"{val} har tagits bort.")
            st.stop()

if __name__ == "__main__":
    main()
