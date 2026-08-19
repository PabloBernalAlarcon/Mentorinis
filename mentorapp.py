import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- 1. Configuration & Setup ---
st.set_page_config(page_title="Mentorosos", layout="wide")

# The Goals
GOAL_ESTUDIANTE = 9
GOAL_FAMILIA = 3
GOAL_TITULAR = 15

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)
directory_df = conn.read(worksheet="Sheet1", ttl="10m").dropna(how="all")
logs_df = conn.read(worksheet="Sheet2", ttl="10m").dropna(how="all")

# Ensure all expected columns exist in logs to prevent errors
if "Tipo" not in logs_df.columns:
    logs_df["Tipo"] = ""

st.title("Mentoríaslandia 2.0")

# --- 2. Smart Login System ---
if "role" not in st.session_state:
    st.session_state.role = None
    st.session_state.current_user = None

if st.session_state.role is None:
    st.info("Por favor, inicia sesión para continuar.")
    
    # Get list of mentors + Admin
    mentor_list = directory_df["Mentor"].dropna().unique().tolist()
    user_options = ["Admin"] + mentor_list
    
    with st.form("login_form"):
        selected_user = st.selectbox("Usuario", user_options)
        pwd = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
        
        if submitted:
            # Check the password against the secrets.toml file
            try:
                correct_pwd = st.secrets["passwords"][selected_user]
                if pwd == correct_pwd:
                    st.session_state.current_user = selected_user
                    st.session_state.role = "Admin" if selected_user == "Admin" else "Mentor"
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
            except KeyError:
                st.error(f"No se encontró contraseña para {selected_user} en secrets.toml")
    st.stop() # Stops the rest of the app from loading until logged in

# Logout Button for anyone logged in
with st.sidebar:
    st.write(f"Conectado como: **{st.session_state.current_user}**")
    if st.button("Cerrar sesión"):
        st.session_state.role = None
        st.session_state.current_user = None
        st.rerun()


# ==========================================
# --- 3. MENTOR WORKSPACE ---
# ==========================================
if st.session_state.role == "Mentor":
    current_mentor = st.session_state.current_user
    st.header(f"Buenas las tenga, {current_mentor}")
    
    tab1, tab2 = st.tabs(["📝 Registrar Reunión", "📊 Mis Reuniones"])
    
    with tab1:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # Filter to only show this mentor's courses
                dept_list = directory_df[directory_df["Mentor"] == current_mentor]["Curso"].unique()
                selected_dept = st.selectbox("1. Curso", dept_list)
                
            with col2:
                # Select the type of meeting
                meeting_type = st.selectbox("2. Tipo de Reunión", ["Estudiante", "Familia", "Director de Grupo"])
                
            with col3:
                # If meeting is HR/Titular, Estudiante is N/A because it's for the whole class
                if meeting_type == "Director de Grupo":
                    selected_client = st.selectbox("3. Estudiante", ["N/A (Aplica a todo el curso)"], disabled=True)
                else:
                    client_list = directory_df[
                        (directory_df["Mentor"] == current_mentor) & 
                        (directory_df["Curso"] == selected_dept)
                    ]["Estudiante"].unique()
                    selected_client = st.selectbox("3. Estudiante", client_list)
                    
            with col4:
                meeting_date = st.date_input("4. Fecha", value=date.today())

            if st.button("Guardar Reunión", type="primary"):
                new_entry = pd.DataFrame([{
                    "Fecha": meeting_date.strftime("%Y-%m-%d"),
                    "Mentor": current_mentor,
                    "Curso": selected_dept,
                    "Estudiante": selected_client,
                    "Tipo": meeting_type
                }])

                logs_df = pd.concat([logs_df,new_entry],ignore_index=True)

                #updated_logs = pd.concat([logs_df, new_entry], ignore_index=True)
                conn.update(worksheet="Sheet2", data=logs_df)
                st.cache_data.clear()
                
                st.success(f"¡Reunión de {meeting_type} registrada exitosamente!")
                st.balloons()
                
    with tab2:
        st.subheader("Mi Resumen de Actividad")
        
        # --- 1. The Course Filter ---
        mentor_cursos = directory_df[directory_df["Mentor"] == current_mentor]["Curso"].unique()
        selected_filter = st.selectbox("📌 Filtrar por Curso", ["Todos"] + list(mentor_cursos))
        
        # --- 2. Filter the Data based on selection ---
        if selected_filter == "Todos":
            view_dir = directory_df[directory_df["Mentor"] == current_mentor]
            view_logs = logs_df[logs_df["Mentor"] == current_mentor].copy()
        else:
            view_dir = directory_df[
                (directory_df["Mentor"] == current_mentor) & 
                (directory_df["Curso"] == selected_filter)
            ]
            view_logs = logs_df[
                (logs_df["Mentor"] == current_mentor) & 
                (logs_df["Curso"] == selected_filter)
            ].copy()

        # --- 3. Macro View: Titular Meetings ---
        st.markdown("##### 🏫 Progreso con Director de Grupo (Por Curso)")
        display_cursos = view_dir["Curso"].unique()
        titular_cols = st.columns(len(display_cursos) if len(display_cursos) > 0 else 1)
        
        for idx, curso in enumerate(display_cursos):
            with titular_cols[idx]:
                hr_logs = view_logs[(view_logs["Curso"] == curso) & (view_logs["Tipo"] == "Titular")]
                hr_count = len(hr_logs)
                
                with st.container(border=True):
                    st.markdown(f"**Curso: {curso}**")
                    st.metric(label="Reuniones Registradas", value=f"{hr_count} / {GOAL_TITULAR}")
                    st.progress(min(hr_count / GOAL_TITULAR, 1.0))

        st.divider()

        # --- 4. Micro View: Student & Family Meetings ---
        st.markdown("##### 👥 Progreso por Estudiante")
        
        if view_dir.empty:
            st.info("No hay estudiantes asignados a esta vista.")
        else:
            students_list = view_dir.to_dict('records')
            st_cols = st.columns(3) # Grid layout
            
            for idx, row in enumerate(students_list):
                s_name = row["Estudiante"]
                s_curso = row["Curso"]
                
                # Count specific meeting types for this student
                s_logs = view_logs[view_logs["Estudiante"] == s_name]
                c_est = len(s_logs[s_logs["Tipo"] == "Estudiante"])
                c_fam = len(s_logs[s_logs["Tipo"] == "Familia"])
                
                with st_cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{s_name}**")
                        # Only show the course tag if they are looking at "Todos"
                        if selected_filter == "Todos":
                            st.caption(f"Curso: {s_curso}")
                        
                        st.write(f"Estudiante: {c_est} / {GOAL_ESTUDIANTE}")
                        st.progress(min(c_est / GOAL_ESTUDIANTE, 1.0))
                        
                        st.write(f"Familia: {c_fam} / {GOAL_FAMILIA}")
                        st.progress(min(c_fam / GOAL_FAMILIA, 1.0))

        st.divider()

        # --- 5. The Raw Data Table (Collapsed to save space) ---
        with st.expander("Ver historial detallado de fechas"):
            if view_logs.empty:
                st.info("Aún no has registrado reuniones para esta selección.")
            else:
                display_table = view_logs.sort_values(by="Fecha", ascending=False)[["Fecha", "Curso", "Tipo", "Estudiante"]]
                st.dataframe(display_table, use_container_width=True, hide_index=True)

# ==========================================
# --- 4. ADMIN WORKSPACE (Jaimelandia) ---
# ==========================================
elif st.session_state.role == "Admin":
    st.header("Jaimelandia (me da guayabo cambiar el título :( )")
    
    mentor_list = directory_df["Mentor"].dropna().unique()
    view_employee = st.selectbox("Filtrar por mentor", ["Todos"] + list(mentor_list))

    if view_employee == "Todos":
        view_df = directory_df
        view_logs = logs_df
    else:
        view_df = directory_df[directory_df["Mentor"] == view_employee]
        view_logs = logs_df[logs_df["Mentor"] == view_employee]

    # --- MACRO VIEW: Titular/HR Meetings (Per Curso) ---
    st.subheader("🏢 Reuniones con Director de Grupo (Meta: 15 por Curso)")
    departments = view_df["Curso"].unique()
    dept_cols = st.columns(len(departments) if len(departments) > 0 else 1)

    for idx, dept in enumerate(departments):
        with dept_cols[idx]:
            # Count ONLY "Titular" meetings for this specific class
            hr_logs = view_logs[(view_logs["Curso"] == dept) & (view_logs["Tipo"] == "Director de Grupo")]
            hr_count = len(hr_logs)
            hr_progress = min(hr_count / GOAL_TITULAR, 1.0)
            
            with st.container(border=True):
                st.markdown(f"**Curso: {dept}**")
                st.metric(label="Reuniones con Director de Grupo", value=f"{hr_count} / {GOAL_TITULAR}")
                st.progress(hr_progress)

    st.divider()

    # --- MICRO VIEW: Estudiante & Familia Meetings ---
    st.subheader("Progreso Individual (Estudiante y Familia)")

    clients_to_display = view_df.to_dict('records')
    client_cols = st.columns(3) # Wider columns to fit both progress bars

    for idx, row in enumerate(clients_to_display):
        client_name = row["Estudiante"]
        emp_name = row["Mentor"]
        dept_name = row["Curso"]
        
        # Filter logs for this specific student
        student_logs = view_logs[view_logs["Estudiante"] == client_name]
        
        # Count types
        count_estudiante = len(student_logs[student_logs["Tipo"] == "Estudiante"])
        count_familia = len(student_logs[student_logs["Tipo"] == "Familia"])
        
        with client_cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"**{client_name}**")
                st.caption(f"{dept_name} | Mentor: {emp_name}")
                
                # Student Progress
                st.write(f"Estudiante: {count_estudiante} / {GOAL_ESTUDIANTE}")
                st.progress(min(count_estudiante / GOAL_ESTUDIANTE, 1.0))
                
                # Family Progress
                st.write(f"Familia: {count_familia} / {GOAL_FAMILIA}")
                st.progress(min(count_familia / GOAL_FAMILIA, 1.0))
