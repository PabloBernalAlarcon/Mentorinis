import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- 1. Configuration & Setup ---
st.set_page_config(page_title="Mentorinis", layout="wide")
TARGET_MEETINGS = 9

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the data from the two tabs
# Replace YOUR_URL with your actual Google Sheets link
directory_df = conn.read(worksheet="Sheet1", ttl="10m")
logs_df = conn.read(worksheet="Sheet2", ttl="10m")
# Clean up empty rows
directory_df = directory_df.dropna(how="all")
logs_df = logs_df.dropna(how="all")

st.title("🤝 Mentorosos")

# --- 2. Data Entry Section ---
st.header("Registrar reunión")

with st.container(border=True):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        emp_list = directory_df["Mentor"].dropna().unique()
        selected_employee = st.selectbox("1. Mentor", emp_list)
    
    with col2:
        dept_list = directory_df[directory_df["Mentor"] == selected_employee]["Curso"].unique()
        selected_dept = st.selectbox("2. Curso", dept_list)
        
    with col3:
        # FIXED: Now looks for "Estudiante" instead of "Client Name"
        client_list = directory_df[
            (directory_df["Mentor"] == selected_employee) & 
            (directory_df["Curso"] == selected_dept)
        ]["Estudiante"].unique()
        selected_client = st.selectbox("3. Estudiante", client_list)
        
    with col4:
        meeting_date = st.date_input("4. Fecha", value=date.today())

    # Save the log back to Google Sheets
    if st.button("Log Meeting", type="primary"):
        new_entry = pd.DataFrame([{
            "Fecha": meeting_date.strftime("%Y-%m-%d"),
            "Mentor": selected_employee,
            "Curso": selected_dept,
            "Estudiante": selected_client
        }])
        
        updated_logs = pd.concat([logs_df, new_entry], ignore_index=True)
        # FIXED: Now writes to "Sheet2" instead of "Logs"
        conn.update(worksheet="Sheet2", data=updated_logs)

        st.cache_data.clear()
        
        st.success(f"¡Reunión registrada para {selected_client}!")
        st.rerun()

st.divider()

# --- 3. Supervisor Dashboard Section ---
st.header("Jaimelandia")

# 1. Check if the user is already authenticated in this session
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# 2. The Password Gate
if not st.session_state.authenticated:
    st.info("🔒 Esta sección está protegida.")
    pwd = st.text_input("Contraseña de acceso:", type="password")
    
    if st.button("Entrar"):
        if pwd == st.secrets["admin_password"]:
            st.session_state.authenticated = True
            st.rerun() # Refresh the page to show the dashboard
        else:
            st.error("Contraseña incorrecta.")

# 3. The Actual Dashboard (Only shows if authenticated == True)
else:
    if st.button("Cerrar sesión"):
        st.session_state.authenticated = False
        st.rerun()
        
    view_employee = st.selectbox("Filtrar por mentor", ["All"] + list(emp_list))

    if view_employee == "All":
        view_df = directory_df
    else:
        view_df = directory_df[directory_df["Mentor"] == view_employee]

    # --- MACRO VIEW: Department Health ---
    st.subheader("🏢 Resumen por Curso")
    departments = view_df["Curso"].unique()
    dept_cols = st.columns(len(departments) if len(departments) > 0 else 1)

    for idx, dept in enumerate(departments):
        with dept_cols[idx]:
            dept_clients_count = len(view_df[view_df["Curso"] == dept])
            total_target_meetings = dept_clients_count * TARGET_MEETINGS
            
            if view_employee == "All":
                dept_logs = logs_df[logs_df["Curso"] == dept]
            else:
                dept_logs = logs_df[(logs_df["Curso"] == dept) & (logs_df["Mentor"] == view_employee)]
                
            current_meetings = len(dept_logs)
            progress = min(current_meetings / total_target_meetings, 1.0) if total_target_meetings > 0 else 0
            
            with st.container(border=True):
                st.markdown(f"**{dept} Curso**")
                st.metric(label="Total de reuniones", value=f"{current_meetings} / {total_target_meetings}")
                st.progress(progress)

    st.divider()

    # --- MICRO VIEW: Individual Clients ---
    st.subheader("👤 Progreso por Estudiante")

    clients_to_display = view_df.to_dict('records')
    client_cols = st.columns(4)

    for idx, row in enumerate(clients_to_display):
        client_name = row["Estudiante"]
        emp_name = row["Mentor"]
        dept_name = row["Curso"]
        
        count = len(logs_df[
            (logs_df["Mentor"] == emp_name) & 
            (logs_df["Estudiante"] == client_name)
        ])
        
        with client_cols[idx % 4]:
            with st.container(border=True):
                st.markdown(f"**{client_name}**")
                st.caption(f"{dept_name} | Mentor: {emp_name}")
                st.metric(label="Reuniones", value=f"{count} / {TARGET_MEETINGS}")
                st.progress(min(count / TARGET_MEETINGS, 1.0))