import sys
import traceback

import pandas as pd
import pulp
import streamlit as st

st.set_page_config(page_title="Media Optimizer Pro", page_icon="🎯", layout="wide")
st.title("🎯 Media Plan Optimizer")
st.caption("Encuentra la distribución presupuestaria óptima para maximizar el retorno de impacto de tus campañas utilizando programación lineal (PuLP).")

# ---------------- Parámetros editables ----------------
datos_iniciales = pd.DataFrame(
    {
        "Medio": ["TV", "Radio", "Redes Sociales", "Prensa"],
        "Costo": [8.0, 3.0, 4.0, 2.0],
        "Impacto": [14.0, 5.0, 7.0, 3.0],
    }
)

with st.sidebar:
    st.header("🎛️ Panel de Control")
    presupuesto = st.number_input("Presupuesto de Campaña", min_value=0.0, value=9.0, step=1.0)
    tipo = st.radio(
        "Estrategia de Asignación",
        ["Binaria (usar o no el medio)", "Entera (nº de unidades)", "Continua"],
        index=0,
    )
    max_unidades = None
    if tipo.startswith("Entera"):
        max_unidades = st.number_input("Límite de unidades por canal (0 = sin límite)", min_value=0, value=0, step=1)

st.subheader("📊 Configuración de Costos y Retornos de Impacto")
st.write("Modifica, añade o elimina canales de difusión directamente en el editor interactivo de abajo:")
df = st.data_editor(datos_iniciales, num_rows="dynamic", use_container_width=True, key="editor")

# ---------------- Resolución ----------------
def crear_var(prob, nombre, low, up, cat):
    # Compatible con versiones antiguas y nuevas de PuLP
    if hasattr(prob, "add_variable"):
        return prob.add_variable(nombre, lowBound=low, upBound=up, cat=cat)
    return pulp.LpVariable(nombre, lowBound=low, upBound=up, cat=cat)


def resolver(df, presupuesto, tipo, max_unidades):
    df = df.dropna().reset_index(drop=True)
    df = df[df["Medio"].astype(str).str.strip() != ""].reset_index(drop=True)
    if df.empty:
        return None, None, None

    prob = pulp.LpProblem("Maximizar_Impacto", pulp.LpMaximize)

    nombres = [f"x_{i}" for i in range(len(df))]
    
    if tipo.startswith("Binaria"):
        x = [crear_var(prob, n, 0, 1, pulp.LpBinary) for n in nombres]
    elif tipo.startswith("Entera"):
        limite = None if max_unidades == 0 else max_unidades
        x = [crear_var(prob, n, 0, limite, pulp.LpInteger) for n in nombres]
    else:
        x = [crear_var(prob, n, 0, None, pulp.LpContinuous) for n in nombres]

    prob += pulp.lpSum(df.loc[i, "Impacto"] * x[i] for i in range(len(df))), "Impacto_total"
    prob += pulp.lpSum(df.loc[i, "Costo"] * x[i] for i in range(len(df))) <= presupuesto, "Presupuesto"

    if hasattr(pulp, "PULP_CBC_CMD"):
        solver = pulp.PULP_CBC_CMD(msg=False)
    else:  # PuLP 4.x
        solver = pulp.COIN_CMD(msg=False)
    prob.solve(solver)

    res = df.copy()
    res["Cantidad"] = [v.value() if v.value() is not None else 0 for v in x]
    res["Costo total"] = res["Cantidad"] * res["Costo"]
    res["Impacto total"] = res["Cantidad"] * res["Impacto"]
    return prob, res, pulp.LpStatus[prob.status]


if st.button("⚡ Calcular Plan Óptimo", type="primary"):
    try:
        prob, res, estado = resolver(df, presupuesto, tipo, max_unidades)
    except Exception:
        st.error("Error al resolver. Detalle completo (cópialo y compártelo):")
        st.code(
            f"PuLP: {getattr(pulp, '__version__', 'desconocida')}
"
            f"Python: {sys.version}
"
            f"Archivo de pulp: {getattr(pulp, '__file__', 'desconocido')}

"
            + traceback.format_exc()
        )
        st.stop()

    if prob is None:
        st.error("Por favor introduce al menos un canal con valores correctos.")
    else:
        st.subheader("📈 Métricas de Rendimiento Calculadas")
        if estado != "Optimal":
            st.error(f"No se encontró solución óptima. Estado del solver: {estado}")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Impacto de Campaña", f"{pulp.value(prob.objective):,.2f}")
            c2.metric("Presupuesto Invertido", f"{res['Costo total'].sum():,.2f}")
            c3.metric("Remanente del Presupuesto", f"{presupuesto - res['Costo total'].sum():,.2f}")

            st.dataframe(res.round(4), use_container_width=True)
            st.bar_chart(res.set_index("Medio")["Impacto total"])

            with st.expander("🔍 Inspección del Modelo Matemático"):
                st.code(str(prob), language="text")
else:
    st.info("Configura los parámetros en el menú izquierdo y pulsa **Calcular Plan Óptimo**.")
