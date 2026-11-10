import streamlit as st
from database import conectar_db

def render_login():
    # Estilo visual moderno para el login
    st.markdown("""
        <style>
            .login-card {
                background-color: #f8f9fa;
                padding: 30px;
                border-radius: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center; color: #0288d1;'>💧 Hidromaps</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #555;'><b>Reto 1:</b> Guardianes de las Cuencas Hidrográficas</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.subheader("🔐 Iniciar Sesión")
            usuario_input = st.text_input("Usuario")
            password_input = st.text_input("Contraseña", type="password")
            submit_login = st.form_submit_button("Ingresar al Sistema", use_container_width=True)
            
            if submit_login:
                conn = conectar_db()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (usuario_input, password_input))
                    user_data = cursor.fetchone()
                    cursor.close()
                    conn.close()
                    
                    if user_data:
                        st.session_state.user_logged = user_data
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos.")
        
        with st.expander("ℹ️ Ver credenciales de prueba"):
            st.markdown("""
            * **Admin:** `admin_cuenca` / `admin123`
            * **Usuario Común:** `guardian_juan` / `12345`
            """)
