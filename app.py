import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

# Konfiguration
SHEET_URL = "https://docs.google.com/spreadsheets/d/1SmX-5TU1cPN2K8eLKGTGkCPeqj3J-89nuT9zKlI2_sY/edit#gid=0"
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

# Funktion för valutakurser
def get_exchange_rates():
    try:
        res = requests.get("https://api.exchangerate.host/latest?base=USD")
        data = res.json()
        return {
            "USD": 1,
            "SEK": data["rates"]["SEK"],
            "NOK": data["rates"]["NOK"],
            "CAD": data["rates"]["CAD"]
        }
    except:
        st.warning("⚠️ Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {"USD": 1, "SEK": 10.5, "NOK": 1.0, "CAD": 8.0}

# Ladda portföljdata
def load_data():
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    return df, sheet

# Spara till Google Sheet
def save_data(df, sheet):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

# Beräkna portföljvärde
def calculate_portfolio_value(df, rates):
    missing = []
    try:
        df["Valutakurs"] = df["Valuta"].map(rates)
        df["Kurs"] = pd.to_numeric(df["Kurs"], errors="coerce")
        df["Antal"] = pd.to_numeric(df["Antal"], errors="coerce")
        df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
        df.dropna(subset=["Värde SEK"], inplace=True)
        total = df["Värde SEK"].sum()
        df["Portföljandel %"] = (df["Värde SEK"] / total * 100).round(2)
        return df, total
    except Exception as e:
        st.error(f"Något gick fel vid värdeberäkning: {e}")
        return df, 0

# Huvudfunktion
def main():
    st.title("📊 Min Aktie- & Utdelningsportfölj")

    # Ladda data och växelkurser
    df, sheet = load_data()
    exchange_rates = get_exchange_rates()
    df, total_value = calculate_portfolio_value(df, exchange_rates)

    st.subheader(f"💼 Portföljvärde: {round(total_value):,} SEK")
    st.dataframe(df, use_container_width=True)

    # Lägg till nytt innehav
    st.subheader("➕ Lägg till eller uppdatera innehav")
    with st.form("add_form"):
        ny = {
            "Ticker": st.text_input("Ticker"),
            "Bolagsnamn": st.text_input("Bolagsnamn"),
            "Antal": st.number_input("Antal aktier", min_value=0.0),
            "Kurs": st.number_input("Aktuell kurs", min_value=0.0),
            "Valuta": st.selectbox("Valuta", ["USD", "SEK", "NOK", "CAD"])
        }
        submit = st.form_submit_button("Spara")

        if submit:
            idx = df[df["Ticker"] == ny["Ticker"]].index
            if not idx.empty:
                df.loc[idx[0], ["Bolagsnamn", "Antal", "Kurs", "Valuta"]] = ny["Bolagsnamn"], ny["Antal"], ny["Kurs"], ny["Valuta"]
            else:
                df = pd.concat([df, pd.DataFrame([ny])], ignore_index=True)
            save_data(df, sheet)
            st.success("✅ Innehavet är uppdaterat.")

    # Ta bort innehav
    st.subheader("🗑️ Ta bort innehav")
    selected = st.selectbox("Välj bolag att ta bort", df["Ticker"].unique())
    if st.button("Ta bort"):
        df = df[df["Ticker"] != selected]
        save_data(df, sheet)
        st.success(f"{selected} borttaget!")

    # Köpguide
    st.subheader("💡 Köpguide")
    kapital = st.number_input("Hur mycket vill du investera? (SEK)", min_value=0)
    if kapital > 0:
        df_sorted = df.sort_values(by="Portföljandel %")
        kandidat = df_sorted.iloc[0]
        kurs_sek = kandidat["Kurs"] * exchange_rates.get(candidat["Valuta"], 1)
        omkostnad = kurs_sek
        if kapital >= omkostnad:
            st.success(f"Köp 1 aktie i {kandidat['Bolagsnamn']} ({kandidat['Ticker']}) för ca {round(omkostnad)} kr")
        else:
            st.info(f"💭 Vänta tills du har minst {round(omkostnad)} kr för att köpa 1 aktie i {kandidat['Bolagsnamn']}")

if __name__ == "__main__":
    main()
