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


# --- CARREGAMENTO DOS DADOS REAIS DO GITHUB ---
@st.cache_data
def carregar_dados():
  # Aqui você pode ler o seu arquivo CSV principal que está no repositório.
  # Substitua 'Indicadores_Ambientais_TCC.csv' pelo nome exato do arquivo que você quer usar principal,
  # ou ajuste para unificar com o seu outro CSV se preferir.
  try:
    df = pd.read_csv("Indicadores_Ambientais_TCC.csv")
  except:
    # Fallback caso queira garantir que abra mesmo se o nome diferir
    df = pd.read_csv("biomassa_3anos.csv")

  # Garante que a coluna Ano seja string/texto para evitar decimais no eixo X
  if "Ano" in df.columns:
    df["Ano"] = df["Ano"].astype(str)

  return df


df = carregar_dados()

# Tratamento preventivo de colunas caso precise garantir nomes padronizados
# (Certifique-se de que seus CSVs possuem colunas correspondentes ou ajuste aqui)
if "Biomassa_kg" not in df.columns and "Biomassa" in df.columns:
  df.rename(columns={"Biomassa": "Biomassa_kg"}, inplace=True)
if "Diametro_Copa_m" not in df.columns and "Copa" in df.columns:
  df.rename(columns={"Copa": "Diametro_Copa_m"}, inplace=True)
if "LST_Temp_C" not in df.columns and "Temperatura_C" in df.columns:
  df.rename(columns={"Temperatura_C": "LST_Temp_C"}, inplace=True)

# --- INDICADORES DE DESTAQUE (KPIs) ---
st.subheader("📊 Indicadores de Destaque")
col1, col2, col3, col4 = st.columns(4)

# Exibe os KPIs com segurança baseados na última linha disponível
with col1:
  val_bio = (
      f"{df['Biomassa_kg'].iloc[-1]} kg"
      if "Biomassa_kg" in df.columns
      else "N/A"
  )
  st.metric(label="Biomassa Atual", value=val_bio)

with col2:
  val_copa = (
      f"{df['Diametro_Copa_m'].iloc[-1]} m"
      if "Diametro_Copa_m" in df.columns
      else "N/A"
  )
  st.metric(label="Diâmetro Médio de Copa", value=val_copa)

with col3:
  val_lst = (
      f"{df['LST_Temp_C'].iloc[-1]} °C"
      if "LST_Temp_C" in df.columns
      else "N/A"
  )
  st.metric(
      label="Temp. de Superfície (LST)",
      value=val_lst,
      delta_color="inverse",
  )

with col4:
  val_prec = (
      f"{df['Precipitacao_mm'].iloc[-1]} mm"
      if "Precipitacao_mm" in df.columns
      else "N/A"
  )
  st.metric(label="Precipitação Acumulada", value=val_prec)

st.divider()

# --- SEÇÃO 1: GRÁFICOS DA BIOMETRIA ---
st.subheader("🔬 Evolução Biométrica das Árvores")
col_a, col_b = st.columns(2)

with col_a:
  if "Biomassa_kg" in df.columns:
    fig_bio = px.bar(
        df,
        x="Ano",
        y="Biomassa_kg",
        text="Biomassa_kg",
        title="Evolução da Biomassa Estimada (kg)",
        color="Biomassa_kg",
        color_continuous_scale="Greens",
    )
    fig_bio.update_xaxes(type="category")
    fig_bio.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig_bio, use_container_width=True)
  else:
    st.info("Coluna de biomassa não encontrada no CSV.")

with col_b:
  if "Diametro_Copa_m" in df.columns:
    fig_copa = px.line(
        df,
        x="Ano",
        y="Diametro_Copa_m",
        markers=True,
        title="Evolução do Diâmetro de Copa (m)",
        color_discrete_sequence=["#27ae60"],
    )
    fig_copa.update_xaxes(type="category")
    fig_copa.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_copa, use_container_width=True)
  else:
    st.info("Coluna de diâmetro de copa não encontrada no CSV.")

# --- SEÇÃO 2: GRÁFICOS AMBIENTAIS (GEE) ---
st.subheader("🌍 Condições Ambientais do Entorno (Google Earth Engine)")
col_c, col_d = st.columns(2)

with col_c:
  if "LST_Temp_C" in df.columns:
    fig_lst = px.line(
        df,
        x="Ano",
        y="LST_Temp_C",
        markers=True,
        title="Temperatura de Superfície - LST (°C)",
        color_discrete_sequence=["#e74c3c"],
    )
    fig_lst.update_xaxes(type="category")
    fig_lst.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)"
    )
    st.plotly_chart(fig_lst, use_container_width=True)
  else:
    st.info("Coluna de temperatura não encontrada no CSV.")

with col_d:
  if "Precipitacao_mm" in df.columns:
    fig_precip = px.bar(
        df,
        x="Ano",
        y="Precipitacao_mm",
        text="Precipitacao_mm",
        title="Precipitação Acumulada (mm - CHIRPS)",
        color="Precipitacao_mm",
        color_continuous_scale="Blues",
    )
    fig_precip.update_xaxes(type="category")
    fig_precip.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
    )
    st.plotly_chart(fig_precip, use_container_width=True)
  else:
    st.info("Coluna de precipitação não encontrada no CSV.")

st.divider()

# --- TABELA CONSOLIDADA ---
st.subheader("📋 Tabela Consolidada de Dados")
st.dataframe(df, use_container_width=True)
