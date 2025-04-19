# -*- coding: utf-8 -*-
"""
Created on Sat Apr 19 00:49:37 2025

@author: usuario
"""

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import io

# --------------------------------------
# SCRAPER Y TRANSFORMADOR DE DATOS
# --------------------------------------

@st.cache_data
def obtener_datos_tesoro(periodos):
    all_data = []
    for year in periodos:
        url = f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value={year}'
        response = requests.get(url)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'class': 'usa-table views-table views-view-table cols-26'})
            if table:
                headers = [header.text.strip() for header in table.find_all('th')]
                for row in table.find_all('tr')[1:]:
                    cells = [year] + [cell.text.strip() for cell in row.find_all('td')]
                    all_data.append(cells)

    if all_data:
        headers = ['Year'] + headers
        df = pd.DataFrame(all_data, columns=headers)
        df = df.drop(columns=['1.5 Mo'], errors='ignore')
        df = df.apply(lambda x: x.replace('N/A', pd.NA) if x.dtype == "object" else x)
        df = df.dropna(axis=1, how='all')
        df = df.fillna(0)
        for col in df.columns[2:]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")
        return df
    else:
        return pd.DataFrame()

# --------------------------------------
# STREAMLIT UI
# --------------------------------------

st.set_page_config(layout="wide")
st.title("Daily Treasury Par Yield Curve Dashboard")
años = st.multiselect("Selecciona año(s):", list(range(2020, 2026)), default=[2024])
df = obtener_datos_tesoro(años)

if not df.empty:
    st.success(f"{df.shape[0]} registros obtenidos.")

    # Selector de fechas para visualización múltiple
    fechas = sorted(df["Date"].unique())
    fechas_seleccionadas = st.multiselect("Selecciona una o más fechas para comparar curvas:", fechas[-10:], default=fechas[-3:])

    # Spread 10Y - 2Y
    if "10 Yr" in df.columns and "2 Yr" in df.columns:
        df["Spread 10Y - 2Y"] = df["10 Yr"] - df["2 Yr"]
        st.metric("📉 Spread 10Y - 2Y actual", f"{df['Spread 10Y - 2Y'].iloc[-1]:.2f} %")

        fig_spread = px.line(df, x="Date", y="Spread 10Y - 2Y", title="Evolución del Spread 10Y - 2Y")
        st.plotly_chart(fig_spread, use_container_width=True)

    # -------------------
    # OVERLAY DE CURVAS
    # -------------------
    st.subheader("Comparación de curvas por fecha")
    fig_comparacion = px.line()

    for fecha in fechas_seleccionadas:
        datos_fecha = df[df["Date"] == fecha].iloc[0]
        maturities = df.columns[2:-2]  # evitar Year, Date, Spread
        tasas = datos_fecha[maturities].values.astype(float)

        fig_comparacion.add_scatter(x=maturities, y=tasas, mode="lines+markers", name=str(fecha.date()))

    fig_comparacion.update_layout(title="Curvas de rendimiento comparadas", xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
    st.plotly_chart(fig_comparacion, use_container_width=True)

    # -------------------
    # ANIMACIÓN
    # -------------------
    st.subheader("Rendimiento de los bonos del Tesoro a la par")
    df_anim = df.copy()
    df_anim = df_anim.melt(id_vars=["Date"], value_vars=maturities, var_name="Maturity", value_name="Yield")

    fig_anim = px.line(df_anim, x="Maturity", y="Yield", animation_frame=df_anim["Date"].dt.strftime("%Y-%m-%d"),
                       title="Evolución diaria de la curva de rendimiento")
    fig_anim.update_layout(xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
    st.plotly_chart(fig_anim, use_container_width=True)

    # -------------------
    # DESCARGA DE DATOS
    # -------------------
    st.subheader("📥 Exportar datos")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Yield Curve')
        if "Spread 10Y - 2Y" in df.columns:
            df[['Date', 'Spread 10Y - 2Y']].to_excel(writer, index=False, sheet_name='Spread')

    st.download_button(label="Descargar Excel", data=output.getvalue(), file_name="treasury_par_yield_curve.xlsx")

else:
    st.warning("No se encontraron datos para los años seleccionados.")
