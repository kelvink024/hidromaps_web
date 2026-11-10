import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import Draw, LocateControl
from streamlit_folium import st_folium
import pandas as pd
import json
import os
from database import conectar_db

def render_user_view(user, archivos_shp, sig_dir):
    st.markdown(f"<h2>🌿 Panel del Guardián Comunitario</h2>", unsafe_allow_html=True)
    st.markdown(f"Bienvenido, <b>{user['nombre_completo']}</b>. Modo ultrarrápido activo.", unsafe_allow_html=True)
    
    tab_mapa, tab_nuevo_reporte = st.tabs(["🗺️ Mapa Multicapa en Vivo", "📝 Registrar Reporte y Severidad"])
    
    # Filtrar estrictamente solo shapefiles y gpkg válidos, ignorando cualquier ráster colgado
    capas_seleccionadas = [c for c in st.session_state.get('capas_activas', []) if c.endswith(('.shp', '.gpkg'))]

    @st.cache_data
    def cargar_multiples_capas(lista_capas):
        capas_cargadas = {}
        for nombre in lista_capas:
            ruta = f"{sig_dir}/{nombre}"
            try:
                gdf = gpd.read_file(ruta)
                if gdf.crs and gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs(epsg=4326)
                
                if 'geometry' in gdf.columns:
                    gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.005, preserve_topology=True)
                
                if len(gdf) > 400:
                    gdf = gdf.head(400)
                    
                capas_cargadas[nombre] = gdf
            except Exception as e:
                pass
        return capas_cargadas

    gdfs_activos = cargar_multiples_capas(capas_seleccionadas)

    lat_centro, lon_centro = 12.6849, -85.9599
    zoom_inicial = 10
    for gdf in gdfs_activos.values():
        if gdf is not None and not gdf.empty:
            bounds = gdf.total_bounds
            lon_centro = (bounds[0] + bounds[2]) / 2
            lat_centro = (bounds[1] + bounds[3]) / 2
            zoom_inicial = 11
            break

    with tab_mapa:
        st.markdown("### Mapa de Alertas Hídricas y Microcuenca")
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=zoom_inicial, tiles="OpenStreetMap")
        LocateControl(auto_start=True, flyTo=True).add_to(m)

        colores_capas = ['#3182bd', '#31a354', '#756bb1', '#de2d26', '#3690c0']
        for idx, (nombre_capa, gdf) in enumerate(gdfs_activos.items()):
            if gdf is not None and not gdf.empty:
                color_actual = colores_capas[idx % len(colores_capas)]
                folium.GeoJson(
                    gdf,
                    name=nombre_capa, 
                    style_function=lambda x, col=color_actual: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.3}
                ).add_to(m)

        conn = conectar_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM reportes_campo")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            for rep in rows:
                sev = rep.get('severidad', 'Moderada')
                color_sev = 'green' if sev == 'Leve' else ('orange' if sev == 'Moderada' else 'red')
                
                try:
                    ref_raw = rep['referencia_espacial']
                    geom_data = json.loads(ref_raw) if isinstance(ref_raw, str) else ref_raw
                    if isinstance(geom_data, list):
                        coords = [[c[1], c[0]] for c in geom_data]
                        folium.Polygon(locations=coords, color=color_sev, fill=True, fill_color=color_sev, fill_opacity=0.5, popup=f"<b>{rep['titulo']}</b><br>Severidad: <b>{sev}</b>").add_to(m)
                    elif isinstance(geom_data, dict) and geom_data.get('type') == 'Polygon':
                        coords = [[c[1], c[0]] for c in geom_data['coordinates'][0]]
                        folium.Polygon(locations=coords, color=color_sev, fill=True, fill_color=color_sev, fill_opacity=0.5, popup=f"<b>{rep['titulo']}</b><br>Severidad: <b>{sev}</b>").add_to(m)
                    else:
                        folium.Marker(location=[rep['lat'], rep['lon']], popup=f"<b>{rep['titulo']}</b><br>Severidad: <b>{sev}</b>", icon=folium.Icon(color=color_sev, icon='warning-sign')).add_to(m)
                except:
                    pass

        st_folium(m, width=1250, height=500, returned_objects=[])

    with tab_nuevo_reporte:
        st.markdown("### 📍 Delimitar Zona Afectada y Nivel de Urgencia")
        m_draw = folium.Map(location=[lat_centro, lon_centro], zoom_start=11, tiles="OpenStreetMap")
        LocateControl(auto_start=True, flyTo=True).add_to(m_draw)

        if capas_seleccionadas:
            for c_sel in capas_seleccionadas:
                if c_sel in gdfs_activos and gdfs_activos[c_sel] is not None:
                    prime_gdf = gdfs_activos[c_sel]
                    if not prime_gdf.empty:
                        folium.GeoJson(prime_gdf.head(150), style_function=lambda x: {'fillColor': '#9ecae1', 'color': '#3182bd', 'weight': 1, 'fillOpacity': 0.2}).add_to(m_draw)
                        break

        draw = Draw(export=False, position='topleft', draw_options={'polyline': False, 'polygon': True, 'rectangle': True, 'circle': False, 'marker': True, 'circlemarker': False}, edit_options={'edit': True})
        draw.add_to(m_draw)

        output_map = st_folium(m_draw, width=1250, height=450, returned_objects=["last_active_drawing"])

        geom_capturada = None
        lat_cap, lon_cap = lat_centro, lon_centro

        if output_map and output_map.get("last_active_drawing"):
            geom_capturada = output_map["last_active_drawing"]["geometry"]
            if geom_capturada["type"] == "Point":
                lon_cap, lat_cap = geom_capturada["coordinates"]
            elif geom_capturada.get("type") == "Polygon":
                first_coord = geom_capturada["coordinates"][0][0]
                lon_cap, lat_cap = first_coord[0], first_coord[1]

        with st.form("form_reporte"):
            titulo_rep = st.text_input("Título de la Incidencia")
            col1, col2 = st.columns(2)
            with col1:
                capa_asociada = st.selectbox("Capa asociada:", [c for c in archivos_shp if c.endswith(('.shp', '.gpkg'))])
            with col2:
                severidad_rep = st.selectbox("Nivel de Severidad / Urgencia:", ["Leve", "Moderada", "Crítica"])
            
            descripcion_rep = st.text_area("Descripción detallada del problema ambiental")
            foto_evidencia = st.file_uploader("Evidencia Fotográfica", type=["png", "jpg", "jpeg"])

            submitted = st.form_submit_button("🚀 Enviar Reporte de Campo", use_container_width=True)
            if submitted:
                if titulo_rep and descripcion_rep:
                    nombre_foto = "Sin foto"
                    if foto_evidencia is not None:
                        os.makedirs("uploads", exist_ok=True)
                        ruta_foto = os.path.join("uploads", foto_evidencia.name)
                        with open(ruta_foto, "wb") as f:
                            f.write(foto_evidencia.getbuffer())
                        nombre_foto = foto_evidencia.name

                    ref_espacial = json.dumps(geom_capturada) if geom_capturada else json.dumps({"type": "Point", "coordinates": [lon_cap, lat_cap]})
                    
                    conn = conectar_db()
                    if conn:
                        cursor = conn.cursor()
                        query = "INSERT INTO reportes_campo (usuario_id, titulo, lat, lon, capa_afectada, descripcion, evidencia, estado, severidad, referencia_espacial) VALUES (%s, %s, %s, %s, %s, %s, %s, 'Pendiente', %s, %s)"
                        cursor.execute(query, (user['id'], titulo_rep, lat_cap, lon_cap, capa_asociada, descripcion_rep, nombre_foto, severidad_rep, ref_espacial))
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success("¡Reporte enviado con éxito!")
                else:
                    st.warning("Completa los campos obligatorios.")
