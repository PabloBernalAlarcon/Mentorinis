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
if "Comentarios" not in logs_df.columns:
    logs_df["Comentarios"] = ""
st.title("Registro de Reuniones para Mentores")

# --- 2. Smart Login System ---
if "role" not in st.session_state:
    st.session_state.role = None
    st.session_state.current_user = None

if st.session_state.role is None:
    st.info("Por favor, inicie sesión para continuar.")
    
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
    st.header(f"¿Qué desea hacer hoy, {current_mentor}?")
    
    tab1, tab2, tab3 = st.tabs(["Registrar Reunión", "Ver Registro de Reuniones", "Editar Reuniones"])
    
    with tab1:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                dept_list = directory_df[directory_df["Mentor"] == current_mentor]["Curso"].unique()
                selected_dept = st.selectbox("1. Curso", dept_list)
                
            with col2:
                meeting_type = st.selectbox("2. Tipo de Reunión", ["Estudiante", "Familia", "Titular"])
                
            with col3:
                if meeting_type == "Titular":
                    selected_client = st.selectbox("3. Estudiante", ["N/A (Aplica a todo el curso)"], disabled=True)
                else:
                    client_list = directory_df[
                        (directory_df["Mentor"] == current_mentor) & 
                        (directory_df["Curso"] == selected_dept)
                    ]["Estudiante"].unique()
                    selected_client = st.selectbox("3. Estudiante", client_list)
                    
            with col4:
                meeting_date = st.date_input("4. Fecha", value=date.today())

            # --- NEW: Comments Section ---
            meeting_comments = st.text_area("5. Comentarios (Opcional)", placeholder="Escribe aquí los acuerdos principales, observaciones o notas de la reunión...")

            if st.button("Guardar Reunión", type="primary"):
                new_entry = pd.DataFrame([{
                    "Fecha": meeting_date.strftime("%Y-%m-%d"),
                    "Mentor": current_mentor,
                    "Curso": selected_dept,
                    "Estudiante": selected_client,
                    "Tipo": meeting_type,
                    "Comentarios": meeting_comments # Saving the new comments
                }])
                
                logs_df = pd.concat([logs_df, new_entry], ignore_index=True)
                conn.update(worksheet="Sheet2", data=logs_df)
                st.cache_data.clear()
                
                st.success(f"¡Reunión de {meeting_type} registrada exitosamente!")
                st.balloons()
                
        # --- NEW: "Recent Logs" Display ---
        st.divider()
        st.markdown("##### 🕒 Tus últimos 5 registros")
        
        # Grab the mentor's logs, take only the last 5 added, and reverse the order so the newest is at the very top
        mentor_recent_logs = logs_df[logs_df["Mentor"] == current_mentor].tail(5).copy()
        
        if mentor_recent_logs.empty:
            st.info("Aún no has registrado reuniones.")
        else:
            mentor_recent_logs = mentor_recent_logs.iloc[::-1] 
            display_recent = mentor_recent_logs[["Fecha", "Curso", "Tipo", "Estudiante", "Comentarios"]]
            st.dataframe(display_recent, use_container_width=True, hide_index=True)
                
    with tab2:
        st.subheader("Mi Resumen de Actividad")
        
        # --- 1. The Course Filter ---
        mentor_cursos = directory_df[directory_df["Mentor"] == current_mentor]["Curso"].unique()
        selected_filter = st.selectbox("Filtrar por Curso", ["Todos"] + list(mentor_cursos))
        
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
        st.markdown("##### Progreso con Director de Grupo (Por Curso)")
        display_cursos = view_dir["Curso"].unique()
        titular_cols = st.columns(len(display_cursos) if len(display_cursos) > 0 else 1)
        
        for idx, curso in enumerate(display_cursos):
            with titular_cols[idx]:
                hr_logs = view_logs[(view_logs["Curso"] == curso) & (view_logs["Tipo"] == "Director de Grupo")]
                hr_count = len(hr_logs)
                
                with st.container(border=True):
                    st.markdown(f"**Curso: {curso}**")
                    st.metric(label="Reuniones Registradas", value=f"{hr_count} / {GOAL_TITULAR}")
                    st.progress(min(hr_count / GOAL_TITULAR, 1.0))

        st.divider()

        # --- 4. Micro View: Student & Family Meetings ---
        st.markdown("##### Progreso por Estudiante")
        
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

    with tab3:
        st.subheader("Editar un Registro Existente")

        mentor_own_logs = logs_df[logs_df["Mentor"] == current_mentor].sort_values(by="Fecha", ascending=False)

        if mentor_own_logs.empty:
            st.info("Aún no has registrado reuniones para editar.")
        else:
            def format_log_option(idx):
                row = logs_df.loc[idx]
                comentario = str(row["Comentarios"]) if pd.notna(row["Comentarios"]) else ""
                preview = f" — {comentario[:40]}{'...' if len(comentario) > 40 else ''}" if comentario else ""
                return f"{row['Fecha']} | {row['Curso']} | {row['Tipo']} | {row['Estudiante']}{preview}"

            selected_idx = st.selectbox(
                "Selecciona el registro a editar",
                options=mentor_own_logs.index.tolist(),
                format_func=format_log_option,
                key="edit_record_selector"
            )

            current_row = logs_df.loc[selected_idx]

            with st.container(border=True):
                ecol1, ecol2, ecol3, ecol4 = st.columns(4)

                with ecol1:
                    edit_dept_list = directory_df[directory_df["Mentor"] == current_mentor]["Curso"].unique()
                    dept_index = list(edit_dept_list).index(current_row["Curso"]) if current_row["Curso"] in edit_dept_list else 0
                    edit_dept = st.selectbox("1. Curso", edit_dept_list, index=dept_index, key=f"edit_dept_{selected_idx}")

                with ecol2:
                    tipo_options = ["Estudiante", "Familia", "Titular"]
                    tipo_index = tipo_options.index(current_row["Tipo"]) if current_row["Tipo"] in tipo_options else 0
                    edit_tipo = st.selectbox("2. Tipo de Reunión", tipo_options, index=tipo_index, key=f"edit_tipo_{selected_idx}")

                with ecol3:
                    if edit_tipo == "Titular":
                        edit_client = st.selectbox("3. Estudiante", ["N/A (Aplica a todo el curso)"], disabled=True, key=f"edit_client_na_{selected_idx}")
                    else:
                        edit_client_list = directory_df[
                            (directory_df["Mentor"] == current_mentor) &
                            (directory_df["Curso"] == edit_dept)
                        ]["Estudiante"].unique()
                        client_index = list(edit_client_list).index(current_row["Estudiante"]) if current_row["Estudiante"] in edit_client_list else 0
                        edit_client = st.selectbox("3. Estudiante", edit_client_list, index=client_index, key=f"edit_client_{selected_idx}")

                with ecol4:
                    edit_date = st.date_input("4. Fecha", value=pd.to_datetime(current_row["Fecha"]).date(), key=f"edit_date_{selected_idx}")

                edit_comments = st.text_area(
                    "5. Comentarios (Opcional)",
                    value=current_row["Comentarios"] if pd.notna(current_row["Comentarios"]) else "",
                    key=f"edit_comments_{selected_idx}"
                )

                if st.button("Guardar Cambios", type="primary", key=f"save_edit_{selected_idx}"):
                    logs_df.loc[selected_idx, "Fecha"] = edit_date.strftime("%Y-%m-%d")
                    logs_df.loc[selected_idx, "Curso"] = edit_dept
                    logs_df.loc[selected_idx, "Tipo"] = edit_tipo
                    logs_df.loc[selected_idx, "Estudiante"] = edit_client
                    logs_df.loc[selected_idx, "Comentarios"] = edit_comments

                    conn.update(worksheet="Sheet2", data=logs_df)
                    st.cache_data.clear()

                    st.success("¡Registro actualizado exitosamente!")
                    st.rerun()

# ==========================================
# --- 4. ADMIN WORKSPACE (Jaimelandia) ---
# ==========================================
elif st.session_state.role == "Admin":
    st.header("Jaimelandia")

    if st.button("🔄 Sincronizar con Google Sheets"):
        st.cache_data.clear()
        st.rerun()
    
    # Split the admin view into Visuals and Raw Data
    tab_progreso, tab_datos = st.tabs(["Progreso por Curso", "Auditoría de Datos"])
    
    with tab_progreso:
        mentor_list = directory_df["Mentor"].dropna().unique()
        view_employee = st.selectbox("Filtro Principal: Mentor", ["Todos"] + list(mentor_list))

        if view_employee == "Todos":
            view_dir = directory_df
            view_logs = logs_df
        else:
            view_dir = directory_df[directory_df["Mentor"] == view_employee]
            view_logs = logs_df[logs_df["Mentor"] == view_employee]

        # Get unique courses based on the filter
        display_cursos = view_dir["Curso"].unique()
        
        if len(display_cursos) == 0:
            st.info("No hay estudiantes asignados para mostrar.")
            
        # Group everything inside a neat collapsible "folder" per Curso
        for curso in display_cursos:
            with st.expander(f"📁 Curso: {curso}", expanded=False):
                
                # --- 1. Titular Progress (Top of the course folder) ---
                hr_logs = view_logs[(view_logs["Curso"] == curso) & (view_logs["Tipo"] == "Director de Grupo")]
                hr_count = len(hr_logs)
                
                st.markdown("##### 🏫 Progreso con Titular")
                st.progress(min(hr_count / GOAL_TITULAR, 1.0))
                st.caption(f"Reuniones registradas: {hr_count} / {GOAL_TITULAR}")
                
                st.divider()
                
                # --- 2. Students Progress (Grid inside the course folder) ---
                st.markdown("##### 👥 Progreso de Estudiantes y Familias")
                
                # Filter students just for this specific course
                students_in_course = view_dir[view_dir["Curso"] == curso].to_dict('records')
                st_cols = st.columns(3)
                
                for idx, row in enumerate(students_in_course):
                    s_name = row["Estudiante"]
                    s_mentor = row["Mentor"]
                    
                    # Filter logs for this specific student
                    s_logs = view_logs[view_logs["Estudiante"] == s_name]
                    c_est = len(s_logs[s_logs["Tipo"] == "Estudiante"])
                    c_fam = len(s_logs[s_logs["Tipo"] == "Familia"])
                    
                    with st_cols[idx % 3]:
                        with st.container(border=True):
                            st.markdown(f"**{s_name}**")
                            # If viewing 'Todos', remind the Admin who mentors this student
                            if view_employee == "Todos":
                                st.caption(f"Mentor: {s_mentor}")
                            
                            st.write(f"Estudiante: {c_est} / {GOAL_ESTUDIANTE}")
                            st.progress(min(c_est / GOAL_ESTUDIANTE, 1.0))
                            
                            st.write(f"Familia: {c_fam} / {GOAL_FAMILIA}")
                            st.progress(min(c_fam / GOAL_FAMILIA, 1.0))
                            
    with tab_datos:
        st.subheader("Buscador de Registros")
        st.markdown("Aquí puedes buscar, ordenar y exportar un archivo CSV con todas las reuniones registradas históricamente.")
        
        if logs_df.empty:
            st.info("Aún no hay reuniones registradas en la base de datos.")
        else:
            # Show the cleanest version of the raw logs, newest first
            display_all_logs = logs_df.sort_values(by="Fecha", ascending=False)[["Fecha", "Mentor", "Curso", "Tipo", "Estudiante"]]
            
            st.dataframe(
                display_all_logs,
                use_container_width=True,
                hide_index=True
            )
