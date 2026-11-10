import mysql.connector
import streamlit as st

def conectar_db():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="1234qwer",
            database="hidromaps_db"
        )
        return conn
    except Exception as e:
        st.error(f"Error al conectar con la base de datos MySQL: {e}")
        return None
