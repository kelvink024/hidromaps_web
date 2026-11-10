import streamlit as st
import os
from views.login import render_login
from views.user_view import render_user_view
from views.admin_view import render_admin_view

st.set_page_config(page_title="Hidromaps - Gestor de Cuencas", layout="wide")

SIG_DIR = os.path.expanduser("~/Documentos/CAPAS-SGG/Datos SIG")

def obtener_shapefiles():
    if not os.path.exists(SIG_DIR):
        return []
    # ESTRICTO: Solo archivos vectoriales ligeros (.shp y .gpkg). Se excluyen los .tif de 52MB para evitar bloqueos web.
    return [f for f in os.listdir(SIG_DIR) if f.endswith(('.shp', '.gpkg'))]

archivos_shp = obtener_shapefiles()

if 'user_logged' not in st.session_state:
    st.session_state.user_logged = None

if st.session_state.user_logged is None:
    render_login()
else:
    user = st.session_state.user_logged
    
    st.sidebar.title(f"👤 {user['nombre_completo']}")
    st.sidebar.markdown(f"**Rol:** `{user['rol'].upper()}`")
    
    if archivos_shp:
        st.sidebar.markdown("---")
        st.sidebar.header("🗂️ Capas SIG Vectoriales")
        st.sidebar.markdown("Selecciona las capas a visualizar:")
        st.session_state['capas_activas'] = st.sidebar.multiselect(
            "Capas disponibles:", 
            archivos_shp, 
            default=[archivos_shp[0]] if archivos_shp else []
        )
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.user_logged = None
        st.rerun()

    if user['rol'] == 'usuario':
        render_user_view(user, archivos_shp, SIG_DIR)
    elif user['rol'] == 'admin':
        render_admin_view(archivos_shp, SIG_DIR)
