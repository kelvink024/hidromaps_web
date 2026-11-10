import streamlit as st
import geopandas as gpd
import folium
from folium import Element
from streamlit_folium import st_folium
import pandas as pd
import json
import os
import shapely.geometry
import subprocess
from database import conectar_db

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def render_admin_view(archivos_shp, sig_dir):
    st.markdown("<h2>⚙️ Consola de Administración y Comité Técnico</h2>", unsafe_allow_html=True)
    
    tab_mapa, tab_gestion = st.tabs(["🗺️ Mapa Multicapa Gerencial con Leyenda", "🛠️ Auditoría, Ficha PDF y QGIS"])

    capas_seleccionadas = st.session_state.get('capas_activas', [])

    @st.cache_data
    def cargar_multiples_capas(lista_capas):
        capas_cargadas = {}
        for nombre in lista_capas:
            ruta = f"{sig_dir}/{nombre}"
            try:
                gdf = gpd.read_file(ruta)
                if gdf.crs and gdf.crs != "EPSG:4326":
                    gdf = gdf.to_crs(epsg=4326)
                # Simplificación estricta para evitar sobrecarga de memoria
                gdf['geometry'] = gdf['geometry'].simplify(tolerance=0.0001, preserve_topology=True)
                capas_cargadas[nombre] = gdf
            except:
                pass
        return capas_cargadas

    gdfs_activos = cargar_multiples_capas(capas_seleccionadas)

    with tab_mapa:
        st.markdown("### Mapa de Alertas y Semáforo de Riesgo en Cuencas")
        
        col_f1, col_f2 = st.columns([2, 4])
        with col_f1:
            filtro_severidad = st.selectbox("Filtrar Alertas en Mapa:", ["Todas", "Crítica", "Moderada", "Leve"])

        lat_centro, lon_centro = 12.6849, -85.9599
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=8, tiles="OpenStreetMap")
        
        legend_html = '''
             <div style="
                 position: fixed; 
                 bottom: 50px; right: 50px; width: 210px; height: 140px; 
                 background-color: white; z-index:9999; font-size:13px;
                 border:2px solid #333; border-radius: 5px; padding: 10px;
                 box-shadow: 0 4px 8px rgba(0,0,0,0.2);">
             <b>🗺️ LEYENDA CARTOGRÁFICA</b><br>
             <hr style="margin:5px 0;">
             <i style="background:red;width:12px;height:12px;float:left;margin-right:8px;border-radius:50%;"></i> Alerta Crítica<br>
             <i style="background:orange;width:12px;height:12px;float:left;margin-right:8px;border-radius:50%;"></i> Alerta Moderada<br>
             <i style="background:green;width:12px;height:12px;float:left;margin-right:8px;border-radius:50%;"></i> Alerta Leve / Preventiva
             </div>
             '''
        m.get_root().html.add_child(Element(legend_html))

        colores_capas = ['#2b8cbe', '#31a354', '#756bb1', '#de2d26', '#3690c0']
        for idx, (nombre_capa, gdf) in enumerate(gdfs_activos.items()):
            if gdf is not None and not gdf.empty:
                color_actual = colores_capas[idx % len(colores_capas)]
                folium.GeoJson(gdf.head(1000), name=nombre_capa, style_function=lambda x, col=color_actual: {'fillColor': col, 'color': col, 'weight': 1, 'fillOpacity': 0.3}).add_to(m)

        conn = conectar_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT r.*, u.nombre_completo FROM reportes_campo r JOIN usuarios u ON r.usuario_id = u.id")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            for rep in rows:
                sev = rep.get('severidad', 'Moderada')
                if filtro_severidad != "Todas" and sev != filtro_severidad:
                    continue

                color_sev = 'green' if sev == 'Leve' else ('orange' if sev == 'Moderada' else 'red')
                
                try:
                    ref_raw = rep['referencia_espacial']
                    geom_data = None
                    if isinstance(ref_raw, str):
                        try:
                            geom_data = json.loads(ref_raw)
                        except:
                            geom_data = None
                    else:
                        geom_data = ref_raw

                    if isinstance(geom_data, list):
                        coords = [[c[1], c[0]] for c in geom_data]
                        folium.Polygon(locations=coords, color=color_sev, fill=True, fill_color=color_sev, fill_opacity=0.5, popup=f"<b>[ADMIN] {rep['titulo']}</b><br>Urgencia: <b>{sev}</b>").add_to(m)
                    elif isinstance(geom_data, dict) and geom_data.get('type') == 'Polygon':
                        coords = [[c[1], c[0]] for c in geom_data['coordinates'][0]]
                        folium.Polygon(locations=coords, color=color_sev, fill=True, fill_color=color_sev, fill_opacity=0.5, popup=f"<b>[ADMIN] {rep['titulo']}</b><br>Urgencia: <b>{sev}</b>").add_to(m)
                    else:
                        folium.Marker(location=[rep['lat'], rep['lon']], popup=f"<b>[ADMIN] {rep['titulo']}</b><br>Urgencia: <b>{sev}</b>", icon=folium.Icon(color=color_sev, icon='flag')).add_to(m)
                except:
                    pass

        st_folium(m, width=1250, height=500, returned_objects=[])

    with tab_gestion:
        st.markdown("### 🖼️ Auditoría, Ficha Ejecutiva y QGIS")
        conn = conectar_db()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT r.id, u.nombre_completo AS guardian, r.titulo, r.lat, r.lon, r.capa_afectada, r.severidad, r.evidencia, r.estado, r.descripcion, r.notas_admin, r.referencia_espacial, r.fecha FROM reportes_campo r JOIN usuarios u ON r.usuario_id = u.id")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            df_admin = pd.DataFrame(rows) if rows else pd.DataFrame()
            if not df_admin.empty:
                st.dataframe(df_admin[['id', 'guardian', 'titulo', 'severidad', 'estado', 'capa_afectada', 'fecha']], use_container_width=True)

                reporte_ids = df_admin['id'].tolist()
                rep_id_sel = st.selectbox("Seleccionar ID de reporte a auditar:", reporte_ids)
                rep_actual = df_admin[df_admin['id'] == rep_id_sel].iloc[0]

                col_info1, col_info2 = st.columns([1.5, 1])
                with col_info1:
                    st.markdown(f"**Título:** {rep_actual['titulo']}")
                    st.markdown(f"**Guardián:** {rep_actual['guardian']}")
                    st.markdown(f"**Nivel de Severidad:** `{rep_actual['severidad']}`")
                    st.markdown(f"**Estado Actual:** `{rep_actual['estado']}`")
                    st.markdown(f"**Descripción:** {rep_actual['descripcion']}")
                    
                    with st.form("form_admin_gestion"):
                        nuevo_estado = st.selectbox("Actualizar Estado:", ["Pendiente", "En Mitigación", "Resuelto"], index=["Pendiente", "En Mitigación", "Resuelto"].index(rep_actual['estado']))
                        nuevas_notas = st.text_area("Notas Técnicas / Acciones de Mitigación:", value=str(rep_actual['notas_admin']) if pd.notna(rep_actual['notas_admin']) else "")
                        
                        btn_act = st.form_submit_button("💾 Guardar Cambios")
                        if btn_act:
                            conn = conectar_db()
                            if conn:
                                cursor = conn.cursor()
                                cursor.execute("UPDATE reportes_campo SET estado = %s, notas_admin = %s WHERE id = %s", (nuevo_estado, nuevas_notas, rep_id_sel))
                                conn.commit()
                                cursor.close()
                                conn.close()
                                st.success("¡Actualizado con éxito!")
                                st.rerun()

                with col_info2:
                    st.markdown("<b>📸 Evidencia Fotográfica de Campo:</b>", unsafe_allow_html=True)
                    nombre_archivo_foto = rep_actual['evidencia']
                    if nombre_archivo_foto and nombre_archivo_foto != "Sin foto":
                        ruta_imagen = os.path.join("uploads", nombre_archivo_foto)
                        if os.path.exists(ruta_imagen):
                            st.image(ruta_imagen, caption=f"Evidencia #{rep_actual['id']}", use_container_width=True)
                        else:
                            st.info(f"Archivo no encontrado ({nombre_archivo_foto}).")
                    else:
                        st.info("Este reporte no tiene foto.")

                st.markdown("---")
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("📄 Generar y Descargar Ficha Ejecutiva Estilo Plano (PDF)", use_container_width=True):
                        pdf_filename = f"/tmp/Ficha_Cartografica_Reporte_{rep_actual['id']}.pdf"
                        doc = SimpleDocTemplate(pdf_filename, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
                        elements = []
                        styles = getSampleStyleSheet()
                        
                        header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#0d47a1'), spaceAfter=2, alignment=1)
                        subheader_style = ParagraphStyle('SubHeader', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#555555'), spaceAfter=10, alignment=1)
                        section_style = ParagraphStyle('SectionStyle', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#0d47a1'), spaceBefore=8, spaceAfter=4)
                        
                        elements.append(Paragraph("HIDROMAPS — SISTEMA DE GESTIÓN DE CUENCAS", header_style))
                        elements.append(Paragraph("<b>RETO 1: GUARDIANES DE LAS CUENCAS HIDROGRÁFICAS</b> | REPORTE TÉCNICO DE CAMPO", subheader_style))
                        elements.append(Spacer(1, 5))

                        data_table = [
                            [Paragraph("<b>ID de Incidencia:</b>", styles['Normal']), Paragraph(str(rep_actual['id']), styles['Normal'])],
                            [Paragraph("<b>Título del Reporte:</b>", styles['Normal']), Paragraph(str(rep_actual['titulo']), styles['Normal'])],
                            [Paragraph("<b>Guardián Responsable:</b>", styles['Normal']), Paragraph(str(rep_actual['guardian']), styles['Normal'])],
                            [Paragraph("<b>Nivel de Urgencia (Severidad):</b>", styles['Normal']), Paragraph(str(rep_actual['severidad']), styles['Normal'])],
                            [Paragraph("<b>Estado de Atención:</b>", styles['Normal']), Paragraph(str(rep_actual['estado']), styles['Normal'])],
                            [Paragraph("<b>Capa de Referencia SIG:</b>", styles['Normal']), Paragraph(str(rep_actual['capa_afectada']), styles['Normal'])],
                            [Paragraph("<b>Coordenadas Geográficas:</b>", styles['Normal']), Paragraph(f"Lat: {rep_actual['lat']:.4f}, Lon: {rep_actual['lon']:.4f}", styles['Normal'])],
                            [Paragraph("<b>Fecha y Hora:</b>", styles['Normal']), Paragraph(str(rep_actual['fecha']), styles['Normal'])],
                            [Paragraph("<b>Descripción del Daño:</b>", styles['Normal']), Paragraph(str(rep_actual['descripcion']), styles['Normal'])],
                            [Paragraph("<b>Acciones del Comité Técnico:</b>", styles['Normal']), Paragraph(str(rep_actual['notas_admin']) if pd.notna(rep_actual['notas_admin']) else "Pendiente de revisión técnica", styles['Normal'])],
                        ]
                        
                        t = Table(data_table, colWidths=[170, 360])
                        t.setStyle(TableStyle([
                            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f1f8e9')),
                            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#c8e6c9')),
                            ('VALIGN', (0,0), (-1,-1), 'TOP'),
                            ('PADDING', (0,0), (-1,-1), 5),
                        ]))
                        elements.append(t)
                        elements.append(Spacer(1, 8))

                        elements.append(Paragraph("📋 LEYENDA Y ESPECIFICACIONES CARTOGRÁFICAS", section_style))
                        leyenda_pdf_text = """
                        <b>• Sistema de Referencia:</b> Coordenadas Geográficas WGS 84 / Proyección Local.<br/>
                        <b>• Criterio de Severidad:</b> 
                        <font color="red">■</font> <b>Crítica</b> (Afectación severa a fuentes hídricas), 
                        <font color="orange">■</font> <b>Moderada</b> (Daño ambiental con riesgo de expansión), 
                        <font color="green">■</font> <b>Leve</b> (Monitoreo preventivo).<br/>
                        <i>Nota oficial generada automáticamente para trámites ante comités de cuenca y municipalidades.</i>
                        """
                        elements.append(Paragraph(leyenda_pdf_text, ParagraphStyle('LegendPdf', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#444444'))))
                        elements.append(Spacer(1, 8))

                        if nombre_archivo_foto and nombre_archivo_foto != "Sin foto":
                            ruta_img = os.path.join("uploads", nombre_archivo_foto)
                            if os.path.exists(ruta_img):
                                elements.append(Paragraph("📸 <b>EVIDENCIA FOTOGRÁFICA DE CAMPO:</b>", section_style))
                                elements.append(Spacer(1, 3))
                                elements.append(RLImage(ruta_img, width=200, height=140))

                        doc.build(elements)

                        with open(pdf_filename, "rb") as pdf_file:
                            st.download_button(
                                label="📥 Descargar Ficha Estilo Plano (PDF)",
                                data=pdf_file,
                                file_name=f"Ficha_Cartografica_Hidromaps_{rep_actual['id']}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                        st.success("¡Ficha ejecutiva generada con éxito con cuadro de metadatos y leyenda cartográfica!")

                with col_btn2:
                    if st.button("🚀 Lanzar QGIS con la Capa y la Geometría Exacta", use_container_width=True):
                        ruta_shp = f"{sig_dir}/{rep_actual['capa_afectada']}"
                        if not os.path.exists(ruta_shp):
                            archivos_disponibles = [f for f in os.listdir(sig_dir) if f.endswith('.shp')]
                            if archivos_disponibles:
                                ruta_shp = f"{sig_dir}/{archivos_disponibles[0]}"

                        temp_geojson = f"/tmp/reporte_qgis_{rep_actual['id']}.geojson"
                        try:
                            ref_raw = rep_actual['referencia_espacial']
                            geom_data = None
                            if isinstance(ref_raw, str):
                                try:
                                    geom_data = json.loads(ref_raw)
                                except:
                                    geom_data = None

                            if isinstance(geom_data, list):
                                shapely_geom = shapely.geometry.Polygon(geom_data)
                            elif isinstance(geom_data, dict) and geom_data.get('type') == 'Polygon':
                                shapely_geom = shapely.geometry.Polygon(geom_data['coordinates'][0])
                            else:
                                shapely_geom = shapely.geometry.Point(rep_actual['lon'], rep_actual['lat'])

                            reporte_gdf = GeoDataFrame(  # Nota corregida internamente
                                pd.DataFrame([{'id': rep_actual['id'], 'titulo': rep_actual['titulo'], 'severidad': rep_actual['severidad']}]),
                                geometry=[shapely_geom], crs="EPSG:4326"
                            )
                            reporte_gdf.to_file(temp_geojson, driver="GeoJSON")
                            subprocess.Popen(["qgis", ruta_shp, temp_geojson])
                            st.success("¡QGIS abierto con la capa y polígono exacto!")
                        except Exception as e:
                            st.error(f"Error al preparar geometría para QGIS: {e}")
            else:
                st.info("No hay registros en la base de datos.")
