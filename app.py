import base64
import io
import json

import numpy as np
import rasterio
from PIL import Image
from matplotlib import colors as mpl_colors
from rasterio.enums import Resampling
from rasterio.warp import calculate_default_transform, reproject
from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.colormap import LinearColormap
from folium.plugins import Fullscreen, MiniMap
from streamlit_folium import st_folium

st.set_page_config(page_title="Árvores urbanas | TCC", page_icon="🌳", layout="wide")
BASE = Path(__file__).parent

# ============================================================
# TEXTOS EXPLICATIVOS (edite aqui: um bloco por aba)
# ============================================================
LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor "
    "incididunt ut labore et dolore magna aliqua.\n\n"
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip "
    "ex ea commodo consequat.\n\n"
    "- Duis aute irure dolor in reprehenderit in voluptate velit.\n"
    "- Excepteur sint occaecat cupidatat non proident.\n"
    "- Sunt in culpa qui officia deserunt mollit anim id est laborum."
)
TEXTOS = {k: LOREM for k in ["geral", "mapa", "arvores", "ambiente", "associacao", "ar", "sobre"]}

# Imagens do Earth Engine (salve os prints em imagens/ no repositório)
IMAGENS = [
    ("imagens/gee_area_estudo.png", "Área de estudo (≈1,1 km) no Earth Engine"),
    ("imagens/gee_indices.png", "NDVI / EVI no entorno"),
]

COR_T = {"aumento": "#2E9E5B", "estável": "#8A8F98", "redução": "#F28C28", "indeterminada": "#B8BCC4"}
PALETA = ["#2E9E5B", "#2F80ED", "#F28C28", "#9B51E0", "#E63946", "#00A8A8"]

POLUENTES = {
    "MP2,5": ("pm25_ug_m3", "µg/m³"),
    "MP10": ("pm10_ug_m3", "µg/m³"),
    "CO": ("co_ug_m3", "µg/m³"),
    "NO₂": ("no2_ug_m3", "µg/m³"),
}
MESES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai",
         6: "Jun", 7: "Jul", 8: "Ago", 9: "Set"}

# Nomes das abas (usados no seletor e nos blocos "if aba == ...")
ABA_GERAL = "🏠 Visão geral"
ABA_MAPA = "🗺️ Mapa"
ABA_ARVORES = "🌿 Árvores"
ABA_AMBIENTE = "🌍 Ambiente"
ABA_AR = "🌫️ Qualidade do ar"
ABA_ASSOC = "🔗 Associação"
ABA_SOBRE = "📖 Sobre"
ABAS = [ABA_GERAL, ABA_MAPA, ABA_ARVORES, ABA_AMBIENTE, ABA_AR, ABA_ASSOC, ABA_SOBRE]


# Escalas e paletas iguais às utilizadas no Google Earth Engine.
INDICADORES = {
    "NDVI": {"arquivo": "NDVI", "min": 0, "max": 0.8,
             "cores": ["#d73027", "#fee08b", "#1a9850"], "unidade": "NDVI"},
    "EVI": {"arquivo": "EVI", "min": 0, "max": 0.6,
            "cores": ["#d73027", "#fee08b", "#1a9850"], "unidade": "EVI"},
    "Precipitação": {"arquivo": "Precipitacao", "min": 1000, "max": 3000,
                     "cores": ["#f7fbff", "#6baed6", "#08306b"], "unidade": "mm (jan–set)"},
    "Temperatura": {"arquivo": "Temperatura", "min": 25, "max": 40,
                    "cores": ["#313695", "#74add1", "#fee090", "#f46d43", "#a50026"],
                    "unidade": "°C (superfície)"},
}


@st.cache_data(show_spinner=False)
def preparar_raster(caminho, minimo, maximo, cores):
    """Lê GeoTIFF, reprojeta para WGS84 e produz PNG RGBA georreferenciado."""
    with rasterio.open(caminho) as src:
        if src.crs is None:
            raise ValueError("GeoTIFF sem SRC: verifique a exportação do GEE.")
        if src.crs.to_epsg() == 4326:
            dados = src.read(1, masked=True).astype("float32")
            transform = src.transform
            valido = ~np.ma.getmaskarray(dados)
            valores = np.asarray(dados.filled(np.nan))
        else:
            transform, largura, altura = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds
            )
            valores = np.full((altura, largura), np.nan, dtype="float32")
            reproject(
                source=rasterio.band(src, 1), destination=valores,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=transform, dst_crs="EPSG:4326",
                src_nodata=src.nodata, dst_nodata=np.nan,
                resampling=Resampling.nearest,
            )
            valido = np.isfinite(valores)
        valido &= np.isfinite(valores)
        # Sem reamostragem visual: preserva a resolução nativa do sensor.
        normalizado = np.clip((valores - minimo) / (maximo - minimo), 0, 1)
        mapa_cores = mpl_colors.LinearSegmentedColormap.from_list("gee", list(cores))
        rgba = (mapa_cores(np.nan_to_num(normalizado)) * 255).astype("uint8")
        rgba[..., 3] = np.where(valido, 255, 0).astype("uint8")
        oeste = transform.c
        norte = transform.f
        leste = oeste + transform.a * valores.shape[1]
        sul = norte + transform.e * valores.shape[0]
        if not (sul < norte and oeste < leste):
            raise ValueError("Limites geográficos inválidos no GeoTIFF.")
        buffer = io.BytesIO()
        Image.fromarray(rgba, "RGBA").save(buffer, format="PNG")
        url = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
        return url, [[sul, oeste], [norte, leste]]


def adicionar_legenda_ambiental(mapa, indicador, configuracao):
    # A escala é fixa entre os anos para que a comparação seja consistente.
    legenda = LinearColormap(
        colors=configuracao["cores"], vmin=configuracao["min"],
        vmax=configuracao["max"],
        caption=f"{indicador} — {configuracao['unidade']} (jan–set)"
    )
    legenda.add_to(mapa)


st.markdown(
    """<style>
.banner{background:linear-gradient(120deg,#2E9E5B,#2F80ED);color:#fff;padding:22px 26px;border-radius:16px;margin-bottom:14px}
.banner h1{margin:0;font-size:1.7rem}.banner p{margin:4px 0 0;opacity:.92}
[data-testid="stMetric"]{background:#fff;border:1px solid #DDE8E0;border-radius:14px;padding:12px 14px;box-shadow:0 2px 8px rgba(0,0,0,.05)}
.stTabs [data-baseweb="tab"]{font-weight:600}
div[role="radiogroup"]{gap:6px;flex-wrap:wrap}
div[role="radiogroup"] label{background:#fff;border:1px solid #DDE8E0;border-radius:10px;padding:6px 14px;font-weight:600}
</style>""",
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="banner"><h1>🌳 Árvores urbanas: copa, biomassa e ambiente</h1>'
    "<p>Canteiro central de duas avenidas em Manaus-AM · imagens de 2024, 2025 e 2026 · "
    "os resultados descrevem associações, não causas</p></div>",
    unsafe_allow_html=True,
)


# ============================================================
# DADOS
# ============================================================
def achar(nome):
    for pasta in (BASE, BASE / "data"):
        if (pasta / nome).exists():
            return pasta / nome
    return None


@st.cache_data
def carregar():
    gj_p, amb_p = achar("arvores_3anos.geojson"), achar("Indicadores_Ambientais_TCC.csv")
    faltam = [n for n, p in (("arvores_3anos.geojson", gj_p), ("Indicadores_Ambientais_TCC.csv", amb_p)) if p is None]
    if faltam:
        return None, None, None, faltam
    gj = json.loads(gj_p.read_text(encoding="utf-8"))
    arv = pd.DataFrame([f["properties"] for f in gj["features"]])
    arv["tendencia"] = arv["tendencia"].fillna("indeterminada")
    arv["observacao"] = arv["observacao"].fillna("")
    amb = pd.read_csv(amb_p).drop(columns=[".geo", "system:index"], errors="ignore")
    amb["Ano"] = amb["Ano"].astype(str).str.extract(r"(\d{4})")[0].astype(int)
    return gj, arv, amb.sort_values("Ano"), []


@st.cache_data(show_spinner=False)
def carregar_ar():
    caminho = achar("qualidade_ar_mensal_comparavel_2024_2026.csv")
    if caminho is None:
        return None, "Arquivo de médias mensais da qualidade do ar não encontrado em data/ ou na raiz."
    try:
        df = pd.read_csv(caminho, encoding="utf-8-sig")
        requeridas = {"ano", "mes", "n_horas", *[x[0] for x in POLUENTES.values()]}
        ausentes = sorted(requeridas - set(df.columns))
        if ausentes:
            return None, "Colunas ausentes no CSV de ar: " + ", ".join(ausentes)
        for campo in requeridas:
            df[campo] = pd.to_numeric(df[campo], errors="coerce")
        df = df.dropna(subset=["ano", "mes", "n_horas"]).copy()
        df["ano"] = df["ano"].astype(int)
        df["mes"] = df["mes"].astype(int)
        df = df[df["ano"].isin([2024, 2025, 2026]) & df["mes"].between(1, 9)]
        df["mes_nome"] = df["mes"].map(MESES)
        df = df.sort_values(["ano", "mes"])
        return df, None
    except Exception as exc:
        return None, f"Erro ao ler o arquivo de qualidade do ar: {exc}"


def resumo_ar(mensal):
    """Média ponderada pelas horas disponíveis, não média simples de médias mensais."""
    linhas = []
    for ano_ref, grupo in mensal.groupby("ano"):
        linha = {"ano": int(ano_ref)}
        for coluna, _ in POLUENTES.values():
            validos = grupo.dropna(subset=[coluna, "n_horas"])
            pesos = validos["n_horas"].clip(lower=0)
            linha[coluna] = float(np.average(validos[coluna], weights=pesos)) if len(validos) and pesos.sum() > 0 else np.nan
        linhas.append(linha)
    return pd.DataFrame(linhas).sort_values("ano")


gj, arv, amb, faltam = carregar()
if faltam:
    st.error(f"Arquivos não encontrados no repositório: {', '.join(faltam)}")
    st.stop()

ar_mensal, erro_ar = carregar_ar()
ar_resumo = resumo_ar(ar_mensal) if ar_mensal is not None and not ar_mensal.empty else None

tot = arv.groupby("ano").agg(area=("area_copa_m2", "sum"), bio=("biomassa_kg", "sum")).reset_index()
res = tot.merge(amb, left_on="ano", right_on="Ano")
ids = sorted(arv["det_id"].unique())
a26 = arv[arv["ano"] == 2026].sort_values("det_id")


def kpi(col):
    v0, v1 = res.loc[res.ano == 2024, col].iloc[0], res.loc[res.ano == 2026, col].iloc[0]
    return v1, (v1 - v0) / v0 * 100


def estilizar(fig):
    fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=50, b=10), legend_title_text="")
    fig.update_xaxes(type="category")
    return fig


def explicacao(chave):
    with st.expander("ℹ️ Como ler esta seção", expanded=True):
        st.markdown(TEXTOS[chave])


# ============================================================
# NAVEGAÇÃO (substitui st.tabs) E BARRA LATERAL
# ============================================================
aba = st.radio("Seção", ABAS, horizontal=True, label_visibility="collapsed", key="aba_ativa")

# Valores padrão (usados apenas se a aba Mapa não estiver ativa).
ano = 2026
modo = "tendência"
sobrepor = True
destaque = None
indicador_ambiental = "Nenhum"
ano_ambiental = 2026
opacidade_ambiental = 0.70

# A barra lateral só é criada na aba do mapa; nas outras ela não aparece.
if aba == ABA_MAPA:
    st.sidebar.header("Filtros do mapa")
    ano = st.sidebar.select_slider("Ano", [2024, 2025, 2026], value=2026)
    modo = st.sidebar.radio("Colorir por", ["tendência", "biomassa"])
    sobrepor = st.sidebar.checkbox("Sobrepor contorno de 2024", value=True)
    destaque = st.sidebar.selectbox("Destacar árvore", ["—"] + [int(i) for i in ids])
    destaque = None if destaque == "—" else destaque

    st.sidebar.divider()
    st.sidebar.header("Camada ambiental")
    indicador_ambiental = st.sidebar.selectbox(
        "Indicador", ["Nenhum", *INDICADORES.keys()], index=1
    )
    ano_ambiental = st.sidebar.selectbox("Ano do indicador", [2024, 2025, 2026], index=2)
    opacidade_ambiental = st.sidebar.slider("Opacidade", 0.0, 1.0, 0.70, 0.05)


# ============================================================
# MAPA
# ============================================================
def construir_mapa():
    sel = {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"]["ano"] == ano]}
    cmap = LinearColormap(["#E8F5E9", "#43A047", "#1B5E20"], vmin=float(arv.biomassa_kg.min()),
                          vmax=float(arv.biomassa_kg.max()), caption="Biomassa (kg)")

    def estilo(f):
        p = f["properties"]
        cor = COR_T.get(p["tendencia"], "#999") if modo == "tendência" else cmap(p["biomassa_kg"])
        s = p["det_id"] == destaque
        return {"fillColor": cor, "color": "#FFFFFF" if s else "#1B2A22",
                "weight": 4 if s else 1.2, "fillOpacity": 0.82}

    m = folium.Map(location=[-3.1, -60.0], zoom_start=18, tiles=None, max_zoom=21)
    folium.TileLayer(tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                     attr="Esri World Imagery", name="Satélite", max_native_zoom=19, max_zoom=21).add_to(m)
    folium.TileLayer("CartoDB positron", name="Mapa claro", show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Ruas", show=False).add_to(m)

    # Sobreposição raster primeiro; copas e contorno são desenhados acima.
    if indicador_ambiental != "Nenhum":
        conf = INDICADORES[indicador_ambiental]
        raster = BASE / "rasters" / f"{conf['arquivo']}_{ano_ambiental}.tif"
        if raster.exists():
            try:
                png, limites = preparar_raster(
                    str(raster), conf["min"], conf["max"], tuple(conf["cores"])
                )
                folium.raster_layers.ImageOverlay(
                    image=png, bounds=limites, opacity=opacidade_ambiental,
                    name=f"{indicador_ambiental} {ano_ambiental}",
                    overlay=True, control=True, show=True,
                ).add_to(m)
                adicionar_legenda_ambiental(m, indicador_ambiental, conf)
            except Exception as erro:
                st.warning(f"Não foi possível carregar {raster.name}: {erro}")
        else:
            st.warning(f"Raster não encontrado: rasters/{raster.name}")

    if sobrepor and ano != 2024:
        ref = {"type": "FeatureCollection", "features": [f for f in gj["features"] if f["properties"]["ano"] == 2024]}
        folium.GeoJson(ref, name="Contorno 2024",
                       style_function=lambda f: {"fill": False, "color": "#FFFFFF", "weight": 1.5, "dashArray": "4"}).add_to(m)

    campos = ["det_id", "ano", "altura_m", "area_copa_m2", "biomassa_kg", "dCA_2024_2026_m2",
              "V_2024_2026_pct", "tendencia", "observacao"]
    nomes = ["Árvore", "Ano", "Altura (m)", "Copa (m²)", "Biomassa (kg)", "ΔCA 2024→2026 (m²)",
             "V% 2024→2026", "Tendência", "Observação"]
    camada = folium.GeoJson(sel, name=f"Copas {ano}", style_function=estilo,
                            tooltip=folium.GeoJsonTooltip(fields=["det_id", "area_copa_m2", "biomassa_kg"],
                                                          aliases=["Árvore", "Copa (m²)", "Biomassa (kg)"], localize=True),
                            popup=folium.GeoJsonPopup(fields=campos, aliases=nomes, localize=True, max_width=280))
    camada.add_to(m)
    m.fit_bounds(camada.get_bounds())

    area = achar("area_estudo.geojson")
    if area:
        folium.GeoJson(json.loads(area.read_text(encoding="utf-8")), name="Área de estudo (≈1,1 km)",
                       style_function=lambda f: {"fill": False, "color": "#E63946", "weight": 3, "dashArray": "8"}).add_to(m)

    if modo == "biomassa":
        cmap.add_to(m)
    else:
        itens = "".join(f'<div><span style="background:{c};display:inline-block;width:12px;height:12px;margin-right:6px"></span>{n}</div>'
                        for n, c in COR_T.items())
        m.get_root().html.add_child(folium.Element(
            f'<div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:#fff;padding:8px 12px;'
            f'border-radius:8px;font:12px sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.3)">'
            f'<b>Tendência (2024→2026)</b>{itens}</div>'))
    Fullscreen().add_to(m)
    MiniMap(toggle_display=True).add_to(m)
    folium.LayerControl().add_to(m)
    return m


def mostrar_imagens():
    cols = st.columns(len(IMAGENS))
    for c, (caminho, legenda) in zip(cols, IMAGENS):
        with c:
            if (BASE / caminho).exists():
                st.image(str(BASE / caminho), caption=legenda, use_container_width=True)
            else:
                st.info(f"Adicione a imagem **{caminho}** ao repositório.\n\n{legenda}")


# ============================================================
# CONTEÚDO DAS ABAS (somente a aba selecionada é executada)
# ============================================================
if aba == ABA_GERAL:
    explicacao("geral")
    c = st.columns(5)
    area_v, area_d = kpi("area")
    bio_v, bio_d = kpi("bio")
    lst_v, lst_d = kpi("Temperatura_C")
    pre_v, pre_d = kpi("Precipitacao_mm")
    c[0].metric("Árvores monitoradas", len(ids))
    c[1].metric("Área de copa 2026", f"{area_v:,.1f} m²", f"{area_d:+.1f}% vs 2024")
    c[2].metric("Biomassa 2026", f"{bio_v:,.0f} kg", f"{bio_d:+.1f}% vs 2024")
    c[3].metric("Temp. superfície 2026", f"{lst_v:.1f} °C", f"{lst_d:+.1f}% vs 2024", delta_color="inverse")
    c[4].metric("Precipitação jan–set 2026", f"{pre_v:,.0f} mm", f"{pre_d:+.1f}% vs 2024")
    g1, g2 = st.columns(2)
    g1.plotly_chart(estilizar(px.bar(tot, x="ano", y="area", text_auto=".1f", title="Área total de copa (m²)",
                                     color_discrete_sequence=[PALETA[0]])), use_container_width=True)
    g2.plotly_chart(estilizar(px.bar(tot, x="ano", y="bio", text_auto=".0f", title="Biomassa total (kg)",
                                     color_discrete_sequence=[PALETA[1]])), use_container_width=True)
    st.caption("Biomassa: Jucker et al. (2017), Eq. 7, com a altura de campo igual nos três anos.")

if aba == ABA_MAPA:
    explicacao("mapa")
    st.caption(
        f"Copas: {ano} · Camada ambiental: "
        + (f"{indicador_ambiental} {ano_ambiental}" if indicador_ambiental != "Nenhum" else "desativada")
        + " · Período ambiental: janeiro a setembro"
    )
    st_folium(construir_mapa(), height=580, use_container_width=True, returned_objects=[])
    st.caption(
        "NDVI/EVI: Sentinel-2; precipitação: CHIRPS; temperatura de superfície: MODIS. "
        "As resoluções espaciais dos sensores são diferentes; pixels maiores não representam detalhes de árvores individuais."
    )
    if destaque is not None:
        r = arv[arv.det_id == destaque].sort_values("ano")
        d = r.iloc[-1]
        k = st.columns(4)
        k[0].metric(f"Árvore {destaque}", d["tendencia"])
        k[1].metric("Altura", f"{d['altura_m']:.1f} m")
        k[2].metric("ΔCA 2024→2026", f"{d['dCA_2024_2026_m2']:+.1f} m²", f"{d['V_2024_2026_pct']:+.1f}%")
        k[3].metric("Biomassa 2026", f"{d['biomassa_kg']:.1f} kg")
        st.plotly_chart(estilizar(px.line(r, x="ano", y="area_copa_m2", markers=True, title=f"Copa da árvore {destaque} (m²)",
                                          color_discrete_sequence=[PALETA[0]])), use_container_width=True)
        if d["observacao"]:
            st.warning(d["observacao"])
    # O mapa interativo acima já mostra os GeoTIFFs reais; prints são opcionais.


if aba == ABA_ARVORES:
    explicacao("arvores")
    a, b = st.columns([3, 2])
    fig = px.bar(a26.assign(arvore=a26.det_id.astype(str)), x="arvore", y="dCA_2024_2026_m2", color="tendencia",
                 color_discrete_map=COR_T, title="Variação da copa por árvore, 2024→2026 (m²)",
                 labels={"arvore": "Árvore", "dCA_2024_2026_m2": "ΔCA (m²)"})
    a.plotly_chart(estilizar(fig), use_container_width=True)
    cont = a26.tendencia.value_counts().reset_index()
    b.plotly_chart(px.pie(cont, names="tendencia", values="count", hole=0.55, color="tendencia",
                          color_discrete_map=COR_T, title="Tendências"), use_container_width=True)
    esc = st.multiselect("Árvores na linha do tempo", [int(i) for i in ids], default=[int(i) for i in ids[:6]])
    lin = arv[arv.det_id.isin(esc)].assign(arvore=lambda d: d.det_id.astype(str))
    st.plotly_chart(estilizar(px.line(lin, x="ano", y="area_copa_m2", color="arvore", markers=True,
                                      title="Área de copa por ano (m²)", color_discrete_sequence=PALETA)),
                    use_container_width=True)
    tab = a26[["det_id", "altura_m", "ca_2024", "ca_2025", "ca_2026", "dCA_2024_2026_m2",
               "V_2024_2026_pct", "tendencia", "biomassa_kg", "observacao"]].rename(columns={
        "det_id": "Árvore", "altura_m": "Altura (m)", "ca_2024": "Copa 2024", "ca_2025": "Copa 2025",
        "ca_2026": "Copa 2026", "dCA_2024_2026_m2": "ΔCA (m²)", "V_2024_2026_pct": "V%",
        "tendencia": "Tendência", "biomassa_kg": "Biomassa 2026 (kg)", "observacao": "Observação"})
    st.dataframe(tab.round(1), use_container_width=True, hide_index=True)
    st.download_button("Baixar tabela (CSV)", tab.to_csv(index=False).encode("utf-8"), "arvores.csv", "text/csv")

if aba == ABA_AMBIENTE:
    explicacao("ambiente")
    ind = amb.melt(id_vars="Ano", value_vars=["EVI_Medio", "NDVI_Medio"], var_name="Índice", value_name="valor")
    e1, e2 = st.columns(2)
    e1.plotly_chart(estilizar(px.bar(ind, x="Ano", y="valor", color="Índice", barmode="group", text_auto=".3f",
                                     title="EVI e NDVI médios (jan–set)", color_discrete_sequence=PALETA)), use_container_width=True)
    e2.plotly_chart(estilizar(px.bar(amb, x="Ano", y="Precipitacao_mm", text_auto=".0f", title="Precipitação acumulada (mm)",
                                     color_discrete_sequence=[PALETA[1]])), use_container_width=True)
    e3, e4 = st.columns(2)
    e3.plotly_chart(estilizar(px.line(amb, x="Ano", y="Temperatura_C", markers=True,
                                      title="Temperatura de superfície diurna, LST (°C)",
                                      color_discrete_sequence=[PALETA[4]])), use_container_width=True)
    if "N_cenas_S2" in amb.columns:
        e4.plotly_chart(estilizar(px.bar(amb, x="Ano", y="N_cenas_S2", text_auto=True, title="Cenas Sentinel-2 usadas",
                                         color_discrete_sequence=[PALETA[5]])), use_container_width=True)
    st.caption("Médias do entorno de ≈1,1 km (não das árvores). A temperatura é de superfície (MODIS), não do ar.")
    # Os gráficos usam o CSV consolidado, não os rasters.

if aba == ABA_AR:
    explicacao("ar")
    st.subheader("Qualidade do ar em Manaus | CAMS Global")
    st.caption("Estimativas modeladas do Open-Meteo/CAMS Global (grade de aproximadamente 45 km). "
               "Não são medições de sensores locais nem médias de todas as estações de Manaus.")
    if ar_mensal is None or ar_mensal.empty:
        st.warning(erro_ar or "Não há registros de qualidade do ar para exibir.")
        st.code("data/qualidade_ar_mensal_comparavel_2024_2026.csv")
    else:
        filtro1, filtro2 = st.columns([2, 3])
        with filtro1:
            poluente = st.selectbox("Poluente", list(POLUENTES), key="pol_ar")
        with filtro2:
            anos_ar = st.multiselect("Anos", [2024, 2025, 2026], default=[2024, 2025, 2026], key="anos_ar")
        campo, unidade = POLUENTES[poluente]
        selecionado = ar_mensal[ar_mensal["ano"].isin(anos_ar)].copy()
        resumo_filtrado = ar_resumo[ar_resumo["ano"].isin(anos_ar)].copy()
        if selecionado.empty:
            st.info("Selecione pelo menos um ano.")
        else:
            metricas = st.columns(len(resumo_filtrado))
            for caixa, (_, item) in zip(metricas, resumo_filtrado.iterrows()):
                caixa.metric(f"Média {int(item['ano'])} · {poluente}", f"{item[campo]:.2f} {unidade}")
            selecionado["ano_txt"] = selecionado["ano"].astype(str)
            mensal_fig = px.line(selecionado, x="mes", y=campo, color="ano_txt", markers=True,
                category_orders={"ano_txt": ["2024", "2025", "2026"]},
                labels={"mes": "Mês", campo: f"Concentração ({unidade})", "ano_txt": "Ano"},
                title=f"Variação mensal de {poluente} (mesmos dias nos três anos)")
            mensal_fig.update_xaxes(tickmode="array", tickvals=list(MESES), ticktext=list(MESES.values()))
            st.plotly_chart(estilizar(mensal_fig), use_container_width=True)
            bar = px.bar(resumo_filtrado.assign(ano_txt=resumo_filtrado["ano"].astype(str)),
                x="ano_txt", y=campo, text_auto=".2f",
                labels={"ano_txt": "Ano", campo: f"Concentração ({unidade})"},
                title=f"Média no período comparável — {poluente}")
            st.plotly_chart(estilizar(bar), use_container_width=True)
            st.subheader("Tabela mensal")
            dados_tabela = selecionado[["ano", "mes_nome", "n_horas", campo]].rename(columns={
                "ano": "Ano", "mes_nome": "Mês", "n_horas": "Horas válidas",
                campo: f"{poluente} ({unidade})"})
            st.dataframe(dados_tabela, use_container_width=True, hide_index=True)
            st.download_button("Baixar dados filtrados (CSV)",
                selecionado.to_csv(index=False).encode("utf-8-sig"),
                file_name="qualidade_ar_filtrada.csv", mime="text/csv")
        st.info("Período harmonizado: 10 de janeiro a 22 de setembro de cada ano, excluindo "
                "29 de fevereiro de 2024. Janeiro e setembro são meses parciais. "
                "As médias por ano são ponderadas pelas horas válidas de cada mês. "
                "Os indicadores do Earth Engine foram originalmente calculados para janeiro a setembro, "
                "portanto as janelas temporais não coincidem integralmente.")


if aba == ABA_ASSOC:
    explicacao("associacao")
    cols = {"area": "Área de copa", "bio": "Biomassa", "EVI_Medio": "EVI", "NDVI_Medio": "NDVI",
            "Precipitacao_mm": "Precipitação", "Temperatura_C": "Temp. superfície"}
    idx = res[["ano", *cols]].copy()
    for k in cols:
        idx[k] = idx[k] / idx.loc[idx.ano == 2024, k].iloc[0] * 100
    long = idx.melt(id_vars="ano", var_name="variavel", value_name="índice").replace({"variavel": cols})
    st.plotly_chart(estilizar(px.line(long, x="ano", y="índice", color="variavel", markers=True,
                                      title="Todas as variáveis na mesma escala (2024 = 100)",
                                      color_discrete_sequence=PALETA)), use_container_width=True)
    sentido = pd.DataFrame({
        "Variável": list(cols.values()),
        "2024→2025": [f"{'▲' if res[k].iloc[1] > res[k].iloc[0] else '▼'} {(res[k].iloc[1]/res[k].iloc[0]-1)*100:+.1f}%" for k in cols],
        "2025→2026": [f"{'▲' if res[k].iloc[2] > res[k].iloc[1] else '▼'} {(res[k].iloc[2]/res[k].iloc[1]-1)*100:+.1f}%" for k in cols],
        "2024→2026": [f"{'▲' if res[k].iloc[2] > res[k].iloc[0] else '▼'} {(res[k].iloc[2]/res[k].iloc[0]-1)*100:+.1f}%" for k in cols]})
    st.dataframe(sentido, use_container_width=True, hide_index=True)
    st.warning("Há apenas três pontos no tempo e um único valor ambiental para todas as árvores: o painel mostra se as "
               "variáveis se movem juntas, sem teste estatístico e sem relação de causa.")
    st.subheader("Qualidade do ar e variação das árvores")
    if ar_resumo is None:
        st.info(erro_ar or "Sem registros válidos de qualidade do ar.")
    else:
        pol_ass = st.selectbox("Poluente para comparação descritiva", list(POLUENTES), key="pol_ass")
        col_ass, unidade_ass = POLUENTES[pol_ass]
        combinado = tot.merge(ar_resumo[["ano", col_ass]], on="ano", how="inner")
        if len(combinado) == 3:
            # Índices normalizados para ilustrar trajetórias, sem inferência causal.
            comparacao = combinado[["ano", "area", "bio", col_ass]].copy()
            for var in ["area", "bio", col_ass]:
                base_2024 = comparacao.loc[comparacao["ano"] == 2024, var].iloc[0]
                comparacao[var] = comparacao[var] / base_2024 * 100 if pd.notna(base_2024) and base_2024 != 0 else np.nan
            longo = comparacao.melt(id_vars="ano", var_name="variavel", value_name="indice")
            longo["variavel"] = longo["variavel"].replace({"area": "Área total de copa", "bio": "Biomassa estimada", col_ass: pol_ass})
            st.plotly_chart(estilizar(px.line(longo, x="ano", y="indice", color="variavel", markers=True,
                        title="Trajetórias relativas (2024 = 100)", labels={"indice": "Índice relativo", "ano": "Ano"})),
                        use_container_width=True)
            st.caption(f"{pol_ass} em {unidade_ass}: médias modeladas do CAMS Global, de 10/jan a 22/set "
                       "(excluído 29/fev); dados do GEE: jan–set. Períodos não são idênticos. "
                       "Três observações anuais não permitem inferência causal ou regressão robusta.")
        else:
            st.warning("É necessário ter dados dos três anos para a comparação.")

if aba == ABA_SOBRE:
    explicacao("sobre")
    st.markdown("**Fontes:** imagens de satélite segmentadas por IA no QGIS · Sentinel-2 SR (NDVI/EVI) · "
                "CHIRPS (precipitação) · MODIS MOD11A1 (temperatura de superfície) · "
                 "Open-Meteo/CAMS Global (qualidade do ar, modelagem atmosférica) · Jucker et al. (2017).")
