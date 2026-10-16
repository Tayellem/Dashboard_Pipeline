import pandas as pd
import plotly.express as px
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Dashboard TCC - Monitoramento Urbano", page_icon="🌳", layout="wide"
)

st.title("🌳 Monitoramento Ambiental e Biométrico de Árvores Urbanas")
st.markdown(
    "**Trabalho de Conclusão de Curso (TCC)** — Análise temporal (2024–2026) do"
    " canteiro central e entorno em Manaus-AM."
)
st.divider()


# Carregando seus arquivos CSV
# Substitua 'seu_arquivo_colab.csv' e 'seu_arquivo_gee.csv' pelos nomes exatos dos seus arquivos
@st.cache_data
def carregar_dados():
  # Exemplo de leitura dos seus CSVs:
  # df_colab = pd.read_csv('dados_colab.csv')
  # df_gee = pd.read_csv('Indicadores_Ambientais_TCC.csv')

  # Por enquanto, mantendo a estrutura pronta com seus dados unificados:
  df = pd.DataFrame({
      "Ano": ["2024", "2025", "2026 (Parcial)"],
      "Biomassa_kg": [1250.5, 1280.0, 1310.2],
      "Diametro_Copa_m": [4.2, 4.4, 4.6],
      "NDVI": [0.174, 0.178, 0.168],
      "Precipitacao_mm": [1707.38, 2421.52, 1602.57],
      "LST_Temp_C": [35.97, 32.96, 30.79],
  })
  return df


df = carregar_dados()

# Indicadores (KPIs)
st.subheader("📊 Indicadores de Destaque (2024 vs 2026)")
col1, col2, col3, col4 = st.columns(4)

with col1:
  st.metric(
      label="Biomassa Atual",
      value=f"{df['Biomassa_kg'].iloc[-1]} kg",
      delta=f"+{round(df['Biomassa_kg'].iloc[-1] - df['Biomassa_kg'].iloc[0], 1)} kg",
  )
with col2:
  st.metric(
      label="Diâmetro Médio de Copa",
      value=f"{df['Diametro_Copa_m'].iloc[-1]} m",
      delta=f"+{round(df['Diametro_Copa_m'].iloc[-1] - df['Diametro_Copa_m'].iloc[0], 1)} m",
  )
with col3:
  st.metric(
      label="Temp. de Superfície (LST)",
      value=f"{df['LST_Temp_C'].iloc[-1]} °C",
      delta=f"{round(df['LST_Temp_C'].iloc[-1] - df['LST_Temp_C'].iloc[0], 1)} °C",
      delta_color="inverse",
  )
with col4:
  st.metric(
      label="Precipitação Acumulada",
      value=f"{df['Precipitacao_mm'].iloc[-1]} mm",
      delta="Acumulado Período",
  )

st.divider()

# Gráficos da Biometria (Colab)
st.subheader("🔬 Evolução Biométrica das Árvores (Colab)")
col_a, col_b = st.columns(2)

with col_a:
  fig_bio = px.bar(
      df,
      x="Ano",
      y="Biomassa_kg",
      text="Biomassa_kg",
      title="Evolução da Biomassa Estimada (kg)",
      color="Biomassa_kg",
      color_continuous_scale="Greens",
  )
  st.plotly_chart(fig_bio, use_container_width=True)

with col_b:
  fig_copa = px.line(
      df,
      x="Ano",
      y="Diametro_Copa_m",
      markers=True,
      title="Evolução do Diâmetro de Copa (m)",
      color_discrete_sequence=["#27ae60"],
  )
  st.plotly_chart(fig_copa, use_container_width=True)

# Gráficos Ambientais (GEE)
st.subheader("🌍 Condições Ambientais do Entorno (Google Earth Engine)")
col_c, col_d = st.columns(2)

with col_c:
  fig_lst = px.line(
      df,
      x="Ano",
      y="LST_Temp_C",
      markers=True,
      title="Temperatura de Superfície - LST (°C)",
      color_discrete_sequence=["#e74c3c"],
  )
  st.plotly_chart(fig_lst, use_container_width=True)

with col_d:
  fig_precip = px.bar(
      df,
      x="Ano",
      y="Precipitacao_mm",
      text="Precipitacao_mm",
      title="Precipitação Acumulada (mm - CHIRPS)",
      color="Precipitacao_mm",
      color_continuous_scale="Blues",
  )
  st.plotly_chart(fig_precip, use_container_width=True)

st.divider()

# Tabela Consolidada
st.subheader("📋 Tabela Consolidada")
st.dataframe(df, use_container_width=True)