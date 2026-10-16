import pandas as pd
import plotly.express as px
import streamlit as st

# 1. Certifique-se de que a coluna Ano seja Texto (string)
df['Ano'] = df['Ano'].astype(str)

# --- GRÁFICOS AMBIENTAIS ---
col_c, col_d = st.columns(2)

with col_c:
  fig_lst = px.line(
      df,
      x='Ano',
      y='LST_Temp_C',
      markers=True,
      title='Temperatura de Superfície - LST (°C)',
      color_discrete_sequence=['#e74c3c'],
  )
  # Força o eixo X a exibir apenas as categorias (sem vírgulas ou decimais)
  fig_lst.update_xaxes(type='category')
  fig_lst.update_layout(
      plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
  )
  st.plotly_chart(fig_lst, use_container_width=True)

with col_d:
  fig_precip = px.bar(
      df,
      x='Ano',
      y='Precipitacao_mm',
      text='Precipitacao_mm',
      title='Precipitação Acumulada (mm - CHIRPS)',
      color='Precipitacao_mm',
      color_continuous_scale='Blues',
  )
  # Força o eixo X a exibir apenas as categorias
  fig_precip.update_xaxes(type='category')
  fig_precip.update_layout(
      plot_bgcolor='rgba(0,0,0,0)',
      paper_bgcolor='rgba(0,0,0,0)',
      showlegend=False,
  )
  st.plotly_chart(fig_precip, use_container_width=True)
