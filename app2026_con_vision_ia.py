import sqlite3
import datetime
import io
import random
import os
import json

import pandas as pd
import streamlit as st
from PIL import Image

# ============================================================
# GEMINI - SDK ACTUAL
# ============================================================
# Instalar con:
# pip install -U google-genai
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# ============================================================
# REPORTLAB
# ============================================================
from reportlab.lib.pagesizes import letter
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


# ============================================================
# 1. CONFIGURACIÓN
# ============================================================
st.set_page_config(
    page_title="Gestión de Inventario Hogar",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_FILE = "inventario_hogar.db"

UNIDADES_VALIDAS = [
    "Unidades",
    "Kg",
    "Gramos",
    "Litros",
    "Packs",
    "Cajas",
]

# Modelo multimodal actual de Gemini.
# Se puede cambiar desde Streamlit Secrets con GEMINI_MODEL.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "").strip()


# ============================================================
# 2. ESTILOS
# ============================================================
FRUITS = [
    "🍎", "🍌", "🍊", "🍐", "🍓",
    "🍏", "🍉", "🍇", "🍋", "🍒",
    "🍑", "🍍", "🥑", "🫐", "🥝",
]

random.seed(42)
fruits_html_list = []

for _ in range(28):
    fruit = random.choice(FRUITS)
    top = random.randint(2, 92)
    left = random.randint(2, 92)
    size = round(random.uniform(2.5, 6.5), 1)
    rotate = random.randint(-35, 35)

    fruits_html_list.append(
        f'<div style="position:absolute;top:{top}vh;left:{left}vw;'
        f'font-size:{size}rem;transform:rotate({rotate}deg);">{fruit}</div>'
    )

bg_fruits_html = "".join(fruits_html_list)

CUSTOM_CSS = f"""
<style>
    .stApp {{
        background-color: #f4f8f5;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont,
                     'Segoe UI', Roboto, sans-serif;
        color: #2b3a30;
    }}

    .bg-fruits-overlay {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 0;
        opacity: 0.10;
        overflow: hidden;
    }}

    [data-testid="stAppViewContainer"] > .main {{
        position: relative;
        z-index: 1;
    }}

    .metric-card {{
        background: #ffffff;
        border: 1px solid #d8e6dc;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
        border-left: 4px solid #52796f;
        margin-bottom: 10px;
    }}

    .metric-card-title {{
        color: #6b8a7a;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    .metric-card-value {{
        color: #1b4332;
        font-size: 1.8rem;
        font-weight: 800;
        margin-top: 4px;
    }}

    .badge-disponible {{
        background-color: #e8f5e9;
        color: #2e7d32;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
        border: 1px solid #c8e6c9;
    }}

    .badge-poco-stock {{
        background-color: #fff8e1;
        color: #f57f17;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
        border: 1px solid #ffe082;
    }}

    .badge-agotado {{
        background-color: #ffebee;
        color: #c62828;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.8rem;
        border: 1px solid #ffcdd2;
    }}

    [data-testid="stSidebar"] {{
        background-color: #e8f5e9 !important;
        border-right: 2px solid #a5d6a7;
        padding: 20px 10px;
    }}

    div[role="radiogroup"] > label {{
        background-color: #ffffff;
        border: 1px solid #a5d6a7;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
        border-radius: 10px !important;
        font-weight: 600;
        color: #1b4332;
    }}

    div[role="radiogroup"] > label:hover {{
        border-color: #2e7d32;
        background-color: #c8e6c9;
    }}

    .stButton > button {{
        border-radius: 8px;
        border: 1px solid #a3c9ad;
        background-color: #ffffff;
        color: #2e7d32;
        font-weight: 600;
        padding: 6px 14px;
    }}

    .stButton > button:hover {{
        background-color: #52796f;
        color: #ffffff;
        border-color: #52796f;
    }}

    #MainMenu {{
        visibility: hidden;
    }}

    footer {{
        visibility: hidden;
    }}

    .fruits-falling-container {{
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        pointer-events: none;
        z-index: 9999;
        overflow: hidden;
        animation: fadeOut 0.5s ease 4.8s forwards;
    }}

    .fruit-item {{
        position: absolute;
        top: -80px;
        font-size: 2.2rem;
        animation: fall 4.5s linear 1 forwards;
    }}

    @keyframes fall {{
        0% {{
            transform: translateY(0) rotate(0deg);
            opacity: 1;
        }}
        90% {{
            opacity: 1;
        }}
        100% {{
            transform: translateY(105vh) rotate(360deg);
            opacity: 0;
        }}
    }}

    @keyframes fadeOut {{
        to {{
            opacity: 0;
            visibility: hidden;
        }}
    }}
</style>

<div class="bg-fruits-overlay">
    {bg_fruits_html}
</div>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ============================================================
# 3. BASE DE DATOS SQLITE
# ============================================================
def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS productos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                cantidad REAL NOT NULL DEFAULT 0,
                unidad TEXT NOT NULL,
                minimo REAL NOT NULL DEFAULT 1,
                ultima_modificacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                descripcion TEXT NOT NULL
            )
            """
        )

        conn.commit()


def registrar_log(descripcion):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO historial (descripcion) VALUES (?)",
            (descripcion,),
        )
        conn.commit()


def obtener_productos():
    query = """
        SELECT
            id,
            nombre,
            cantidad,
            unidad,
            minimo,
            ultima_modificacion,
            CASE
                WHEN cantidad <= 0 THEN 'Agotado'
                WHEN cantidad <= minimo THEN 'Poco Stock'
                ELSE 'Disponible'
            END AS estado
        FROM productos
        ORDER BY nombre COLLATE NOCASE ASC
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


def agregar_producto(nombre, cantidad, unidad, minimo):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO productos
                (nombre, cantidad, unidad, minimo)
            VALUES (?, ?, ?, ?)
            """,
            (nombre, cantidad, unidad, minimo),
        )
        conn.commit()

    registrar_log(
        f"Se creó el producto '{nombre}' con {cantidad} {unidad}."
    )


def editar_producto_db(prod_id, nombre, cantidad, unidad, minimo):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE productos
            SET
                nombre = ?,
                cantidad = ?,
                unidad = ?,
                minimo = ?,
                ultima_modificacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (nombre, cantidad, unidad, minimo, prod_id),
        )
        conn.commit()

    registrar_log(f"Producto actualizado: '{nombre}'.")


def actualizar_stock(prod_id, nuevo_stock, nombre_producto):
    nuevo_stock = max(0.0, float(nuevo_stock))

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE productos
            SET cantidad = ?, ultima_modificacion = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (nuevo_stock, prod_id),
        )
        conn.commit()

    registrar_log(
        f"Stock actualizado de '{nombre_producto}' a {nuevo_stock}."
    )


def eliminar_producto(prod_id, nombre_producto):
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM productos WHERE id = ?",
            (prod_id,),
        )
        conn.commit()

    registrar_log(f"Producto eliminado: '{nombre_producto}'.")


# ============================================================
# 4. GEMINI - ANÁLISIS DE IMÁGENES
# ============================================================
def obtener_api_key_gemini():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if api_key:
        return api_key

    try:
        api_key = str(st.secrets["GEMINI_API_KEY"]).strip()
    except Exception:
        api_key = ""

    return api_key


def extraer_json_de_respuesta(texto):
    """
    Gemini puede devolver JSON puro o JSON dentro de un bloque Markdown.
    Esta función limpia ambos casos.
    """
    texto = (texto or "").strip()

    if not texto:
        raise ValueError("La respuesta de Gemini llegó vacía.")

    # Caso normal: JSON puro.
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    # Quitar ```json ... ```
    if "```" in texto:
        partes = texto.split("```")

        for parte in partes:
            parte = parte.strip()

            if parte.lower().startswith("json"):
                parte = parte[4:].strip()

            try:
                return json.loads(parte)
            except json.JSONDecodeError:
                continue

    # Intentar localizar el primer objeto JSON.
    inicio = texto.find("{")
    fin = texto.rfind("}")

    if inicio != -1 and fin != -1 and fin > inicio:
        candidato = texto[inicio : fin + 1]

        try:
            return json.loads(candidato)
        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Gemini no devolvió un JSON válido. "
        "Respuesta recibida: " + texto[:500]
    )


def obtener_modelo_vision(client):
    """
    Busca un modelo que REALMENTE esté disponible para la API key usada
    por esta aplicación y que anuncie soporte para generateContent.

    Esto evita depender de que un nombre de modelo esté disponible en
    una cuenta/proyecto/API concreto.
    """
    disponibles = []

    try:
        for modelo in client.models.list():
            nombre = str(getattr(modelo, "name", "")).strip()
            acciones = getattr(modelo, "supported_actions", None) or []

            if nombre and "generateContent" in acciones:
                nombre_limpio = nombre.replace("models/", "", 1)
                disponibles.append(nombre_limpio)
    except Exception as exc:
        raise RuntimeError(
            "La API key fue recibida, pero no se pudo consultar la lista "
            f"de modelos disponibles. Detalle: {exc}"
        ) from exc

    if not disponibles:
        raise RuntimeError(
            "La API key no tiene ningún modelo disponible que soporte "
            "generateContent."
        )

    # Si el usuario configuró GEMINI_MODEL, se intenta primero.
    if GEMINI_MODEL:
        for modelo in disponibles:
            if modelo == GEMINI_MODEL or modelo.endswith(GEMINI_MODEL):
                return modelo

    # Preferencias actuales. Si uno no está habilitado, se pasa al siguiente.
    preferencias = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]

    for preferido in preferencias:
        for modelo in disponibles:
            if modelo == preferido:
                return modelo

    # Último recurso: elegir un modelo generateContent disponible.
    return disponibles[0]


def obtener_resultado_vision(image_bytes):
    if genai is None or types is None:
        raise RuntimeError(
            "Falta la librería google-genai. "
            "Agrega 'google-genai' a requirements.txt."
        )

    api_key = obtener_api_key_gemini()

    if not api_key:
        raise RuntimeError(
            "No se encontró GEMINI_API_KEY. "
            "Configúrala como secreto de Streamlit."
        )

    client = genai.Client(api_key=api_key)

    # IMPORTANTE:
    # Ya no suponemos que el problema sea "gemini-2.5-flash".
    # Consultamos primero qué modelos acepta realmente esta API key.
    modelo = obtener_modelo_vision(client)

    imagen = Image.open(io.BytesIO(image_bytes))

    if imagen.mode not in ("RGB", "L"):
        imagen = imagen.convert("RGB")

    prompt = """
Analiza cuidadosamente la imagen y detecta los alimentos visibles.

Devuelve ÚNICAMENTE un objeto JSON válido, sin Markdown y sin explicaciones.

Formato obligatorio:
{
  "alimentos": [
    {
      "nombre": "nombre del alimento",
      "cantidad": 1,
      "unidad": "Unidades",
      "confianza": 90,
      "observacion": "descripción breve"
    }
  ]
}

Reglas:
- "cantidad" debe ser un número.
- "confianza" debe ser un entero de 0 a 100.
- "unidad" debe ser exactamente una de:
  "Unidades", "Kg", "Gramos", "Litros", "Packs", "Cajas".
- Si es una fruta u objeto individual visible, usa "Unidades".
- Si la cantidad exacta no puede determinarse, realiza una estimación razonable.
- No inventes alimentos que no sean visibles.
- Si no hay alimentos identificables, devuelve:
  {"alimentos": []}
"""

    try:
        response = client.models.generate_content(
            model=modelo,
            contents=[prompt, imagen],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1000,
                response_mime_type="application/json",
            ),
        )
    except Exception as exc:
        mensaje = str(exc)

        # NO ocultamos el error real detrás de "el modelo no está disponible".
        # Así, si vuelve a fallar, Streamlit mostrará el motivo exacto.
        if "429" in mensaje:
            raise RuntimeError(
                "Gemini rechazó la solicitud por límite de uso o cuota. "
                f"Modelo seleccionado: {modelo}. Detalle: {mensaje}"
            ) from exc

        if "401" in mensaje or "403" in mensaje:
            raise RuntimeError(
                "La API Key de Gemini no es válida, está restringida "
                "incorrectamente o no tiene permisos. "
                f"Modelo seleccionado: {modelo}. Detalle: {mensaje}"
            ) from exc

        raise RuntimeError(
            f"Falló la llamada de visión de Gemini usando "
            f"'{modelo}'. Error real de la API: {mensaje}"
        ) from exc

    contenido = getattr(response, "text", "")

    resultado = extraer_json_de_respuesta(contenido)
    alimentos = resultado.get("alimentos", [])

    if not isinstance(alimentos, list):
        raise ValueError(
            "El JSON recibido no contiene una lista 'alimentos'."
        )

    alimentos_limpios = []

    for item in alimentos:
        if not isinstance(item, dict):
            continue

        nombre = str(item.get("nombre", "")).strip()

        if not nombre:
            continue

        try:
            cantidad = max(
                0.0,
                float(item.get("cantidad", 1)),
            )
        except (TypeError, ValueError):
            cantidad = 1.0

        unidad = str(
            item.get("unidad", "Unidades")
        ).strip()

        if unidad not in UNIDADES_VALIDAS:
            unidad = "Unidades"

        try:
            confianza = max(
                0,
                min(100, int(float(item.get("confianza", 90)))),
            )
        except (TypeError, ValueError):
            confianza = 90

        observacion = str(
            item.get("observacion", "")
        ).strip()

        alimentos_limpios.append(
            {
                "nombre": nombre,
                "cantidad": cantidad,
                "unidad": unidad,
                "confianza": confianza,
                "observacion": observacion,
            }
        )

    return alimentos_limpios


def guardar_alimentos_detectados(df_resultados):
    guardados = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for _, row in df_resultados.iterrows():
            nombre = str(row.get("nombre", "")).strip()
            unidad = str(row.get("unidad", "Unidades")).strip()

            if not nombre or unidad not in UNIDADES_VALIDAS:
                continue

            try:
                cantidad = max(
                    0.0,
                    float(row.get("cantidad", 0)),
                )
            except (TypeError, ValueError):
                continue

            if cantidad <= 0:
                continue

            minimo = 1.0

            cursor.execute(
                """
                SELECT id, cantidad
                FROM productos
                WHERE LOWER(nombre) = LOWER(?)
                  AND unidad = ?
                LIMIT 1
                """,
                (nombre, unidad),
            )

            existente = cursor.fetchone()

            if existente:
                nueva_cantidad = (
                    float(existente["cantidad"]) + cantidad
                )

                cursor.execute(
                    """
                    UPDATE productos
                    SET
                        cantidad = ?,
                        ultima_modificacion = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (nueva_cantidad, existente["id"]),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO productos
                        (nombre, cantidad, unidad, minimo)
                    VALUES (?, ?, ?, ?)
                    """,
                    (nombre, cantidad, unidad, minimo),
                )

            guardados += 1

        conn.commit()

    if guardados:
        registrar_log(
            f"Se guardaron {guardados} alimento(s) "
            "detectado(s) mediante IA."
        )

    return guardados


# ============================================================
# 5. PDF
# ============================================================
def generar_pdf_lista_compras(df_faltantes):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    story = []

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.HexColor("#2e7d32"),
        spaceAfter=10,
    )

    story.append(
        Paragraph("Lista de Compras del Hogar", title_style)
    )

    fecha_str = datetime.datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )

    story.append(
        Paragraph(
            f"<b>Fecha de emisión:</b> {fecha_str}",
            styles["Normal"],
        )
    )

    story.append(Spacer(1, 15))

    data = [
        ["[  ]", "Producto", "Stock Actual", "Notas"]
    ]

    for _, row in df_faltantes.iterrows():
        stock_text = f"{row['cantidad']} {row['unidad']}"

        data.append(
            [
                "[  ]",
                str(row["nombre"]),
                stock_text,
                "",
            ]
        )

    table = Table(
        data,
        colWidths=[40, 220, 120, 170],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#e8f5e9"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#1b4332"),
                ),
                (
                    "ALIGN",
                    (0, 0),
                    (-1, -1),
                    "LEFT",
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, 0),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, 0),
                    10,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, 0),
                    8,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#c8e6c9"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    story.append(table)
    doc.build(story)

    buffer.seek(0)
    return buffer


# ============================================================
# 6. ANIMACIÓN
# ============================================================
def animacion_frutas_5s():
    html_code = """
    <div class="fruits-falling-container">
        <div class="fruit-item" style="left:8%;">🍎</div>
        <div class="fruit-item"
             style="left:24%;animation-delay:0.3s;">🍌</div>
        <div class="fruit-item"
             style="left:40%;animation-delay:0.1s;">🍊</div>
        <div class="fruit-item"
             style="left:58%;animation-delay:0.4s;">🍐</div>
        <div class="fruit-item"
             style="left:74%;animation-delay:0.2s;">🍓</div>
        <div class="fruit-item"
             style="left:88%;animation-delay:0.5s;">🍏</div>
    </div>
    """

    st.markdown(html_code, unsafe_allow_html=True)


# ============================================================
# 7. INICIALIZACIÓN
# ============================================================
init_db()

if "resultado_vision_alimentos" not in st.session_state:
    st.session_state["resultado_vision_alimentos"] = []


# ============================================================
# 8. NAVEGACIÓN
# ============================================================
st.sidebar.markdown("### Inventario Hogar")

opcion_menu = st.sidebar.radio(
    "Navegación",
    [
        "Panel Central",
        "Inventario Principal",
        "Añadir Alimento",
        "Analizar Alimentos con IA",
        "Editar Alimento",
        "Lista de Compras & PDF",
    ],
    label_visibility="collapsed",
)


# ============================================================
# 9. PANEL CENTRAL
# ============================================================
if opcion_menu == "Panel Central":
    animacion_frutas_5s()

    st.header("Panel Central")

    df = obtener_productos()

    total = len(df)
    disponibles = len(
        df[df["estado"] == "Disponible"]
    )
    poco_stock = len(
        df[df["estado"] == "Poco Stock"]
    )
    agotados = len(
        df[df["estado"] == "Agotado"]
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">Total Alimentos</div>
            <div class="metric-card-value">{total}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col2.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">Disponibles</div>
            <div class="metric-card-value">{disponibles}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col3.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">Poco Stock</div>
            <div class="metric-card-value">{poco_stock}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col4.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-card-title">Agotados</div>
            <div class="metric-card-value">{agotados}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    if not df.empty:
        import plotly.express as px

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            with st.container(border=True):
                st.markdown("**Estado del Inventario**")

                estado_counts = (
                    df["estado"]
                    .value_counts()
                    .reset_index()
                )

                estado_counts.columns = [
                    "Estado",
                    "Cantidad",
                ]

                color_map = {
                    "Disponible": "#2e7d32",
                    "Poco Stock": "#f57f17",
                    "Agotado": "#c62828",
                }

                fig1 = px.pie(
                    estado_counts,
                    values="Cantidad",
                    names="Estado",
                    hole=0.5,
                    color="Estado",
                    color_discrete_map=color_map,
                )

                fig1.update_traces(
                    textposition="inside",
                    textinfo="percent+label",
                )

                fig1.update_layout(
                    margin=dict(
                        t=10,
                        b=10,
                        l=10,
                        r=10,
                    ),
                    height=220,
                    showlegend=False,
                )

                st.plotly_chart(
                    fig1,
                    use_container_width=True,
                )

        with col_chart2:
            with st.container(border=True):
                st.markdown("**Productos Agotados**")

                df_agotados = df[
                    df["estado"] == "Agotado"
                ]

                if not df_agotados.empty:
                    st.error(
                        f"Hay {len(df_agotados)} alimento(s) "
                        "sin stock:"
                    )

                    st.dataframe(
                        df_agotados[
                            ["nombre", "unidad"]
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info(
                        "No hay alimentos agotados actualmente."
                    )
    else:
        st.info(
            "La base de datos está vacía. "
            "Añade productos desde el menú lateral."
        )


# ============================================================
# 10. INVENTARIO PRINCIPAL
# ============================================================
elif opcion_menu == "Inventario Principal":
    st.header("Gestión de Inventario")

    df = obtener_productos()

    with st.container(border=True):
        col_search, col_est = st.columns([3, 1])

        with col_search:
            busqueda = st.text_input(
                "Buscar alimento por nombre:",
                "",
            )

        with col_est:
            est_filtro = st.selectbox(
                "Estado:",
                [
                    "Todos",
                    "Disponible",
                    "Poco Stock",
                    "Agotado",
                ],
            )

    if busqueda:
        df = df[
            df["nombre"].str.contains(
                busqueda,
                case=False,
                na=False,
            )
        ]

    if est_filtro != "Todos":
        df = df[
            df["estado"] == est_filtro
        ]

    st.divider()

    if df.empty:
        st.warning(
            "No se encontraron productos en la base de datos."
        )
    else:
        for _, row in df.iterrows():
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns(
                    [4, 2, 2, 2, 2]
                )

                c1.markdown(
                    f"**{row['nombre']}**"
                )

                clase_badge = (
                    row["estado"]
                    .lower()
                    .replace(" ", "-")
                )

                badge = (
                    f"<span class='badge-{clase_badge}'>"
                    f"{row['estado']}"
                    "</span>"
                )

                c2.markdown(
                    badge,
                    unsafe_allow_html=True,
                )

                c3.write(
                    f"Stock: **{row['cantidad']}** "
                    f"{row['unidad']}"
                )

                if c4.button(
                    "+ 1",
                    key=f"add_{row['id']}",
                ):
                    actualizar_stock(
                        row["id"],
                        row["cantidad"] + 1,
                        row["nombre"],
                    )
                    st.rerun()

                if c5.button(
                    "- 1",
                    key=f"sub_{row['id']}",
                ):
                    nueva_cant = max(
                        0.0,
                        row["cantidad"] - 1,
                    )

                    actualizar_stock(
                        row["id"],
                        nueva_cant,
                        row["nombre"],
                    )
                    st.rerun()


# ============================================================
# 11. AÑADIR ALIMENTO
# ============================================================
elif opcion_menu == "Añadir Alimento":
    st.header("Añadir Nuevo Alimento")

    with st.container(border=True):
        with st.form(
            "form_anadir_producto",
            clear_on_submit=True,
        ):
            nombre = st.text_input(
                "Nombre del alimento:"
            ).strip()

            col_qty, col_unit, col_min = st.columns(3)

            with col_qty:
                cantidad = st.number_input(
                    "Cantidad inicial:",
                    min_value=0.0,
                    step=1.0,
                    value=1.0,
                )

            with col_unit:
                unidad = st.selectbox(
                    "Unidad:",
                    UNIDADES_VALIDAS,
                )

            with col_min:
                minimo = st.number_input(
                    "Stock mínimo (alerta):",
                    min_value=0.0,
                    step=1.0,
                    value=1.0,
                )

            submitted = st.form_submit_button(
                "Guardar Alimento"
            )

            if submitted:
                if not nombre:
                    st.error(
                        "El nombre del alimento es obligatorio."
                    )
                else:
                    agregar_producto(
                        nombre,
                        cantidad,
                        unidad,
                        minimo,
                    )

                    st.success(
                        f"Producto '{nombre}' "
                        "guardado exitosamente."
                    )


# ============================================================
# 12. ANALIZAR ALIMENTOS CON IA
# ============================================================
elif opcion_menu == "Analizar Alimentos con IA":
    st.header("Analizar Alimentos con IA")

    st.markdown(
        "Toma una foto o sube una imagen de tus alimentos. "
        "Gemini intentará identificar cada alimento, "
        "estimar su cantidad y mostrar una confianza "
        "antes de guardarlo."
    )

    with st.container(border=True):
        fuente_imagen = st.radio(
            "Origen de la imagen:",
            ["Tomar una foto", "Subir una imagen"],
            horizontal=True,
        )

        imagen_bytes = None

        if fuente_imagen == "Tomar una foto":
            foto = st.camera_input(
                "Tomar foto de los alimentos"
            )

            if foto is not None:
                imagen_bytes = foto.getvalue()

        else:
            archivo = st.file_uploader(
                "Seleccionar imagen",
                type=[
                    "jpg",
                    "jpeg",
                    "png",
                    "webp",
                ],
                accept_multiple_files=False,
            )

            if archivo is not None:
                imagen_bytes = archivo.getvalue()

        if imagen_bytes:
            st.image(
                imagen_bytes,
                caption="Imagen seleccionada",
                use_container_width=True,
            )

            if st.button(
                "Analizar alimentos",
                type="primary",
                key="analizar_alimentos_ia",
            ):
                with st.spinner(
                    f"Consultando Gemini y buscando automáticamente un modelo "
                    f"compatible con tu API..."
                ):
                    try:
                        resultados = obtener_resultado_vision(
                            imagen_bytes
                        )

                        if not resultados:
                            st.warning(
                                "No se pudieron identificar "
                                "alimentos."
                            )

                            st.session_state[
                                "resultado_vision_alimentos"
                            ] = []
                        else:
                            st.session_state[
                                "resultado_vision_alimentos"
                            ] = resultados

                            st.success(
                                f"Se identificaron "
                                f"{len(resultados)} tipo(s) "
                                "de alimento."
                            )

                    except Exception as exc:
                        st.error(
                            "No se pudo analizar la imagen: "
                            f"{exc}"
                        )

    resultados_guardados = st.session_state.get(
        "resultado_vision_alimentos",
        [],
    )

    if resultados_guardados:
        st.divider()
        st.subheader("Resultados detectados")

        st.caption(
            "Puedes modificar el nombre, cantidad, unidad, "
            "confianza u observación antes de guardar."
        )

        df_ia = pd.DataFrame(
            resultados_guardados
        )

        columnas_editor = [
            "nombre",
            "cantidad",
            "unidad",
            "confianza",
            "observacion",
        ]

        df_editado = st.data_editor(
            df_ia[columnas_editor],
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "nombre": st.column_config.TextColumn(
                    "Alimento",
                    required=True,
                ),
                "cantidad": st.column_config.NumberColumn(
                    "Cantidad",
                    min_value=0.0,
                    step=0.1,
                    format="%.2f",
                ),
                "unidad": st.column_config.SelectboxColumn(
                    "Unidad",
                    options=UNIDADES_VALIDAS,
                    required=True,
                ),
                "confianza": st.column_config.NumberColumn(
                    "Confianza (%)",
                    min_value=0,
                    max_value=100,
                    step=1,
                    format="%d%%",
                ),
                "observacion": st.column_config.TextColumn(
                    "Observación",
                ),
            },
            key="editor_resultados_vision",
        )

        col_guardar, col_limpiar = st.columns(2)

        with col_guardar:
            if st.button(
                "Guardar resultados en inventario",
                type="primary",
                use_container_width=True,
                key="guardar_resultados_vision",
            ):
                try:
                    cantidad_guardada = (
                        guardar_alimentos_detectados(
                            df_editado
                        )
                    )

                    if cantidad_guardada > 0:
                        st.success(
                            f"Se guardaron "
                            f"{cantidad_guardada} alimento(s) "
                            "en el inventario."
                        )

                        st.session_state[
                            "resultado_vision_alimentos"
                        ] = []

                        st.rerun()
                    else:
                        st.warning(
                            "No hay resultados válidos "
                            "con una cantidad mayor que cero "
                            "para guardar."
                        )

                except Exception as exc:
                    st.error(
                        "No se pudieron guardar los "
                        f"resultados: {exc}"
                    )

        with col_limpiar:
            if st.button(
                "Descartar resultados",
                use_container_width=True,
                key="descartar_resultados_vision",
            ):
                st.session_state[
                    "resultado_vision_alimentos"
                ] = []

                st.rerun()


# ============================================================
# 13. EDITAR ALIMENTO
# ============================================================
elif opcion_menu == "Editar Alimento":
    st.header("Editar Alimento Existente")

    df_prod = obtener_productos()

    if df_prod.empty:
        st.info(
            "No hay productos registrados para editar."
        )
    else:
        with st.container(border=True):
            opciones_productos = df_prod[
                ["id", "nombre"]
            ].drop_duplicates()

            producto_sel_nombre = st.selectbox(
                "Seleccione el producto a editar:",
                opciones_productos["nombre"].tolist(),
            )

            prod_data = df_prod[
                df_prod["nombre"] == producto_sel_nombre
            ].iloc[0]

            with st.form("form_editar_producto"):
                nuevo_nombre = st.text_input(
                    "Nombre del alimento:",
                    value=str(prod_data["nombre"]),
                ).strip()

                col_qty, col_unit, col_min = st.columns(3)

                with col_qty:
                    cantidad = st.number_input(
                        "Cantidad:",
                        min_value=0.0,
                        step=1.0,
                        value=float(
                            prod_data["cantidad"]
                        ),
                    )

                with col_unit:
                    idx_u = (
                        UNIDADES_VALIDAS.index(
                            prod_data["unidad"]
                        )
                        if prod_data["unidad"]
                        in UNIDADES_VALIDAS
                        else 0
                    )

                    unidad = st.selectbox(
                        "Unidad:",
                        UNIDADES_VALIDAS,
                        index=idx_u,
                    )

                with col_min:
                    minimo = st.number_input(
                        "Stock mínimo:",
                        min_value=0.0,
                        step=1.0,
                        value=float(
                            prod_data["minimo"]
                        ),
                    )

                btn_guardar = st.form_submit_button(
                    "Actualizar Alimento"
                )

                if btn_guardar:
                    if not nuevo_nombre:
                        st.error(
                            "El nombre no puede estar vacío."
                        )
                    else:
                        editar_producto_db(
                            prod_data["id"],
                            nuevo_nombre,
                            cantidad,
                            unidad,
                            minimo,
                        )

                        st.success(
                            "Producto actualizado correctamente."
                        )

                        st.rerun()

            st.divider()

            if st.button(
                "Eliminar Producto",
                key="eliminar_producto",
            ):
                eliminar_producto(
                    prod_data["id"],
                    prod_data["nombre"],
                )

                st.success(
                    f"Producto '{prod_data['nombre']}' eliminado."
                )

                st.rerun()


# ============================================================
# 14. LISTA DE COMPRAS Y PDF
# ============================================================
elif opcion_menu == "Lista de Compras & PDF":
    st.header("Lista de Compras Automática")

    df = obtener_productos()

    df_faltantes = df[
        df["estado"].isin(
            ["Agotado", "Poco Stock"]
        )
    ].copy()

    with st.container(border=True):
        if df_faltantes.empty:
            st.success(
                "No tienes productos faltantes "
                "ni con poco stock."
            )
        else:
            st.warning(
                f"Se encontraron {len(df_faltantes)} "
                "productos que requieren reposición."
            )

            st.dataframe(
                df_faltantes[
                    [
                        "nombre",
                        "cantidad",
                        "unidad",
                        "estado",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )

            pdf_buffer = generar_pdf_lista_compras(
                df_faltantes
            )

            st.download_button(
                label="Descargar Lista de Compras en PDF",
                data=pdf_buffer,
                file_name=(
                    f"lista_compras_"
                    f"{datetime.date.today()}.pdf"
                ),
                mime="application/pdf",
            )
