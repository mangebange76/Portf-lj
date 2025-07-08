import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests
import json

# Konfiguration
st.set_page_config(page_title="Portföljanalys", layout="wide")

# Autentisering
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = Credentials.from_service_account_info(st.secrets["GOOGLE_CREDENTIALS"], scopes=scope)
client = gspread.authorize(credentials)

# Ladda kalkylblad
SHEET_URL = st.secrets["SHEET_URL"]

def load_data():
    spreadsheet = client.open_by_url(SHEET_URL)
    worksheet = spreadsheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df, worksheet

# Hämta valutakurser
def get_exchange_rates():
    try:
        res = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=SEK,CAD,NOK")
        rates = res.json()["rates"]
        return {
            "USD": 1,
            "SEK": rates.get("SEK", 10.5),
            "NOK": rates.get("NOK", 1.0),
            "CAD": rates.get("CAD", 1.0),
        }
    except Exception:
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")
        return {"USD": 1, "SEK": 10.5, "NOK": 1, "CAD": 1}

# Beräkna portföljvärde
def calculate_portfolio_value(df, exchange_rates):
    df["Valutakurs"] = df["Valuta"].map(exchange_rates).fillna(1)
    df["Värde SEK"] = df["Antal"] * df["Kurs"] * df["Valutakurs"]
    total_value = df["Värde SEK"].sum()
    return df, total_value

# Utdelningsprognos (månatlig summering)
def calculate_dividend_projection(df):
    today = datetime.today()
    df["Kommande utdelning"] = pd.to_datetime(df["Utdelningsdatum"], errors='coerce')
    df["Utdelning väntad"] = df.apply(
        lambda row: row["Antal"] * row["Utdelning per aktie"] if row["Kommande utdelning"] and row["Kommande utdelning"] >= today else 0,
        axis=1,
    )
    df["Månad"] = df["Kommande utdelning"].dt.strftime("%Y-%m")
    månadsvis = df.groupby("Månad")["Utdelning väntad"].sum().reset_index()
    månadsvis = månadsvis[månadsvis["Utdelning väntad"] > 0]
    total_kommande = df["Utdelning väntad"].sum()
    return månadsvis, total_kommande

def visa_portfolio(df, total_value, månadsvis, total_kommande):
    st.header("📊 Portföljöversikt")
    st.metric("Totalt portföljvärde (SEK)", f"{total_value:,.0f} kr")

    st.dataframe(df[["Bolag", "Ticker", "Antal", "Kurs", "Valuta", "Värde SEK"]].sort_values(by="Värde SEK", ascending=False), use_container_width=True)

    st.markdown("---")
    st.subheader("📆 Prognos: Kommande utdelningar")

    if månadsvis.empty:
        st.info("Inga bekräftade framtida utdelningar just nu.")
    else:
        st.dataframe(månadsvis.rename(columns={
            "Månad": "Utdelningsmånad",
            "Utdelning väntad": "Förväntad utdelning (SEK)"
        }), use_container_width=True)

        st.metric("Totalt väntad utdelning", f"{total_kommande:,.0f} kr")

            idx = df[df["Ticker"] == ticker].index[0] + 2  # +2 för att hoppa header och 0-index
            for i, key in enumerate(["Bolag", "Ticker", "Valuta", "Antal", "Kurs", "Utdelning", "Månad"]):
                worksheet.update_cell(idx, i + 1, ny_rad[key])
            st.success("Innehavet uppdaterat!")
        else:
            st.error("Ticker kunde inte matchas med någon befintlig rad.")
    else:
        st.warning("Fyll i alla fält korrekt för att uppdatera ett innehav.")

def visa_utdelningsprognos(df):
    st.subheader("📅 Kommande utdelningar")

    df["Månad"] = df["Månad"].astype(str).str.strip()
    aktuell_månad = str(datetime.now().month)
    kommande = df[df["Månad"] == aktuell_månad]

    if not kommande.empty:
        kommande["Utdelning totalt"] = kommande["Utdelning"] * kommande["Antal"] * kommande["Valutakurs"]
        total = kommande["Utdelning totalt"].sum()
        st.dataframe(kommande[["Bolag", "Ticker", "Utdelning totalt"]])
        st.markdown(f"**Totalt förväntad utdelning denna månad:** `{total:.2f} SEK`")
    else:
        st.info("Inga utdelningar planerade för denna månad.")

def spara_utdelningshistorik(df, worksheet):
    månad = datetime.now().month
    år = datetime.now().year
    total = (df[df["Månad"] == månad]["Utdelning"] * df["Antal"] * df["Valutakurs"]).sum()
    
    # Kolumn Z och rad efter år - 2024 + 2 (förskjutet från rad 2)
    rad = år - 2024 + 2
    worksheet.update_acell(f'Z{rad}', total)

def visa_utdelningshistorik(worksheet):
    st.subheader("📈 Utdelningshistorik")

    data = worksheet.get_all_values()
    header = data[0]
    rows = data[1:]
    år_col = [row[0] for row in rows]
    utdelning_col = [row[25] if len(row) > 25 else "" for row in rows]  # Kolumn Z = index 25

    historik = pd.DataFrame({
        "År": år_col,
        "Total utdelning (SEK)": utdelning_col
    })

    historik = historik[historik["År"].str.isnumeric()]
    historik["År"] = historik["År"].astype(int)
    historik["Total utdelning (SEK)"] = pd.to_numeric(historik["Total utdelning (SEK)"], errors="coerce")
    historik = historik.dropna()

    if not historik.empty:
        st.bar_chart(historik.set_index("År"))
    else:
        st.info("Ingen utdelningshistorik sparad än.")

# HUVUDFUNKTION
def main():
    st.title("📊 Aktieportfölj och Utdelningsspårning")
    
    try:
        exchange_rates = get_exchange_rates()
    except:
        exchange_rates = {"USD": 10.0, "EUR": 11.0}
        st.warning("Kunde inte hämta aktuella valutakurser. Visar förinställda värden.")

    df, worksheet = load_data()
    df = uppdatera_valutakurs(df, exchange_rates)
    df, total_value = calculate_portfolio_value(df, exchange_rates)

    with st.expander("📌 Nuvarande innehav"):
        visa_tabell(df, total_value)

    st.markdown("---")
    st.header("➕ Lägg till nytt innehav")
    lägg_till_innehav(df, worksheet)

    st.markdown("---")
    st.header("✏️ Redigera innehav")
    redigera_innehav(df, worksheet)

    st.markdown("---")
    visa_utdelningsprognos(df)
    spara_utdelningshistorik(df, worksheet)

    st.markdown("---")
    visa_utdelningshistorik(worksheet)

if __name__ == "__main__":
    main()
