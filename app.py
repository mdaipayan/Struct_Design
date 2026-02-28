import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math

# --- PAGE SETUP ---
st.set_page_config(page_title="3D Building Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & Design")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Building Geometry")
st.sidebar.caption("Define the structural grid.")

col1, col2 = st.sidebar.columns(2)
with col1:
    num_stories = st.number_input("Stories", min_value=1, value=3)
    bay_x = st.number_input("Bays in X", min_value=1, value=2)
    bay_y = st.number_input("Bays in Y", min_value=1, value=2)
with col2:
    h_story = st.number_input("Story Ht (m)", value=3.0)
    L_x = st.number_input("X Bay Wdt (m)", value=4.0)
    L_y = st.number_input("Y Bay Wdt (m)", value=5.0)

st.sidebar.header("2. Section & Material Properties")
col_dim = st.sidebar.text_input("Column Size (mm)", "300x450")
beam_dim = st.sidebar.text_input("Beam Size (mm)", "230x400")

col3, col4 = st.sidebar.columns(2)
with col3:
    fck = st.number_input("fck (MPa)", value=25.0, step=5.0, help="Concrete Grade")
with col4:
    fy = st.number_input("fy (MPa)", value=500.0, step=85.0, help="Steel Grade")

st.sidebar.header("3. Geotechnical Properties")
sbc = st.sidebar.number_input("Soil Bearing Capacity (kN/m²)", value=200.0, step=10.0, help="Safe Bearing Capacity for Footing Design")

# --- GEOMETRY GENERATOR ---
nodes = []
elements = []

node_id = 0
for z in range(int(num_stories) + 1):
    for y in range(int(bay_y) + 1):
        for x in range(int(bay_x) + 1):
            nodes.append({'id': node_id, 'x': x * L_x, 'y': y * L_y, 'z': z * h_story})
            node_id += 1

def get_node(x_idx, y_idx, z_idx):
    for n in nodes:
        if n['x'] == x_idx * L_x and n['y'] == y_idx * L_y and n['z'] == z_idx * h_story:
            return n['id']
    return None

element_id = 0
for z in range(int(num_stories) + 1):
    for y in range(int(bay_y) + 1):
        for x in range(int(bay_x) + 1):
            current_node = get_node(x, y, z)
            if z < num_stories:
                top_node = get_node(x, y, z + 1)
                if top_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': top_node, 'type': 'Column'})
                    element_id += 1
            if z > 0 and x < bay_x:
                right_node = get_node(x + 1, y, z)
                if right_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': right_node, 'type': 'Beam'})
                    element_id += 1
            if z > 0 and y < bay_y:
                back_node = get_node(x, y + 1, z)
                if back_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': back_node, 'type': 'Beam'})
                    element_id += 1

# --- 3D VISUALIZATION (PLOTLY) ---
st.subheader("Structural Model Viewport")

fig = go.Figure()

# Plot Elements
for el in elements:
    ni = next(n for n in nodes if n['id'] == el['ni'])
    nj = next(n for n in nodes if n['id'] == el['nj'])
    color = 'blue' if el['type'] == 'Column' else 'red'
    
    fig.add_trace(go.Scatter3d(
        x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']],
        mode='lines', line=dict(color=color, width=4),
        hoverinfo='text', text=f"{el['type']} ID: {el['id']}", showlegend=False
    ))

# Midpoint calculation for visible Element IDs
mid_x = [(next(n for n in nodes if n['id'] == el['ni'])['x'] + next(n for n in nodes if n['id'] == el['nj'])['x'])/2 for el in elements]
mid_y = [(next(n for n in nodes if n['id'] == el['ni'])['y'] + next(n for n in nodes if n['id'] == el['nj'])['y'])/2 for el in elements]
mid_z = [(next(n for n in nodes if n['id'] == el['ni'])['z'] + next(n for n in nodes if n['id'] == el['nj'])['z'])/2 for el in elements]
el_labels = [str(el['id']) for el in elements]

fig.add_trace(go.Scatter3d(
    x=mid_x, y=mid_y, z=mid_z,
    mode='text', text=el_labels,
    textfont=dict(color='darkgreen', size=10), showlegend=False
))

x_coords = [n['x'] for n in nodes]
y_coords = [n['y'] for n in nodes]
z_coords = [n['z'] for n in nodes]

fig.add_trace(go.Scatter3d(
    x=x_coords, y=y_coords, z=z_coords, mode='markers',
    marker=dict(size=3, color='black'), hoverinfo='text',
    text=[f"Node: {n['id']}" for n in nodes], showlegend=False
))

fig.update_layout(
    scene=dict(xaxis_title='X (m)', yaxis_title='Y (m)', zaxis_title='Z (m)', aspectmode='data'),
    margin=dict(l=0, r=0, b=0, t=0), height=500
)
st.plotly_chart(fig, use_container_width=True)

# --- LOAD DEFINITION ---
st.divider()
st.header("4. Load Definition (IS 875 & IS 456)")

colA, colB, colC = st.columns(3)
with colA:
    slab_thickness = st.number_input("Slab Thickness (mm)", value=150)
    dl_area = (slab_thickness / 1000.0) * 25.0 + 1.5 # Self weight + finishes
    st.info(f"**Calculated Dead Load (DL):** {dl_area:.2f} kN/m²")
with colB:
    occupancy = st.selectbox("Occupancy Type (IS 875 Part 2)", ["Residential (2.0 kN/m²)", "Office (3.0 kN/m²)", "Retail (4.0 kN/m²)", "Custom"])
    if occupancy == "Custom":
        ll_area = st.number_input("Custom Live Load (kN/m²)", value=3.0, step=0.5)
    else:
        ll_area = float(occupancy.split('(')[1].split(' ')[0])
with colC:
    q_factored = 1.5 * (dl_area + ll_area)
    st.success(f"**Factored Area Load ($q_u$):** {q_factored:.2f} kN/m²")

# --- MASTER ANALYSIS & DESIGN EXECUTION ---
if st.button("Run Complete 3D Structural Analysis & IS 456 Design", type="primary", use_container_width=True):
    with st.spinner("Executing Stiffness Method & Code Checks..."):
        
        # --- 1. Distribute Loads (Yield Line / Tributary) ---
        Lx, Ly = min(L_x, L_y), max(L_x, L_y)
        aspect_ratio = Ly / Lx
        
        if aspect_ratio > 2.0:
            w_long, w_short = q_factored * (Lx / 2.0), 0.0
        else:
            w_short = (q_factored * Lx) / 3.0
            w_long = (q_factored * Lx / 6.0) * (3.0 - (Lx / Ly)**2)
            
        w_x_beam = w_short if L_x == Lx else w_long
        w_y_beam = w_long if L_x == Lx else w_short
            
        for el in elements:
            el['load_kN_m'] = 0.0
            if el['type'] == 'Beam':
                ni = next(n for n in nodes if n['id'] == el['ni'])
                nj = next(n for n in nodes if n['id'] == el['nj'])
                
                if abs(ni['y'] - nj['y']) < 0.01: 
                    multiplier = 1.0 if ni['y'] == 0 or ni['y'] == bay_y * L_y else 2.0
                    el['load_kN_m'] = w_x_beam * multiplier
                elif abs(ni['x'] - nj['x']) < 0.01:
                    multiplier = 1.0 if ni['x'] == 0 or ni['x'] == bay_x * L_x else 2.0
                    el['load_kN_m'] = w_y_beam * multiplier

        # --- 2. Matrix Helper Functions ---
        def get_transformation_matrix(ni, nj):
            dx, dy, dz = nj['x'] - ni['x'], nj['y'] - ni['y'], nj['z'] - ni['z']
            L = math.sqrt(dx**2 + dy**2 + dz**2)
            cx, cy, cz = dx/L, dy/L, dz/L
            lam = np.zeros((3, 3))
            if abs(cx) < 1e-6 and abs(cy) < 1e-6:
                lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
            else: 
                D = math.sqrt(cx**2 + cy**2)
                lam = np.array([[cx, cy, cz], [-cx*cz/D, -cy*cz/D, D], [-cy/D, cx/D, 0]])
            T = np.zeros((12, 12))
            for i in range(4): T[i*3:(i+1)*3, i*3:(i+1)*3] = lam
            return T

        def get_local_stiffness(E, G, A, Iy, Iz, J, L):
            k = np.zeros((12, 12))
            k[0, 0] = k[6, 6] = E * A / L
            k[0, 6] = k[6, 0] = -E * A / L
            k[3, 3] = k[9, 9] = G * J / L
            k[3, 9] = k[9, 3] = -G * J / L
            k[2, 2] = k[8, 8] = 12 * E * Iy / L**3
            k[2, 8] = k[8, 2] = -12 * E * Iy / L**3
            k[4, 4] = k[10, 10] = 4 * E * Iy / L
            k[4, 10] = k[10, 4] = 2 * E * Iy / L
            k[2, 4] = k[2, 10] = k[4, 2] = k[10, 2] = -6 * E * Iy / L**2
            k[8, 4] = k[8, 10] = k[4, 8] = k[10, 8] = 6 * E * Iy / L**2
            k[1, 1] = k[7, 7] = 12 * E * Iz / L**3
            k[1, 7] = k[7, 1] = -12 * E * Iz / L**3
            k[5, 5] = k[11, 11] = 4 * E * Iz / L
            k[5, 11] = k[11, 5] = 2 * E * Iz / L
            k[1, 5] = k[1, 11] = k[5, 1] = k[11, 1] = 6 * E * Iz / L**2
            k[7, 5] = k[7, 11] = k[5, 7] = k[11, 7] = -6 * E * Iz / L**2
            return k

        # --- 3. Assemble Forces & Stiffness ---
        num_nodes = len(nodes)
        F_global = np.zeros(num_nodes * 6)
        E_conc = 5000 * math.sqrt(fck) * 1e3 # Correct IS 456 Elastic Modulus in kPa
        G_conc = E_conc / (2 * (1 + 0.2)) 
        
        b_beam, h_beam = map(lambda x: float(x)/1000, beam_dim.split('x'))
        b_col, h_col = map(lambda x: float(x)/1000, col_dim.split('x'))

        for el in elements:
            ni_data = next(n for n in nodes if n['id'] == el['ni'])
            nj_data = next(n for n in nodes if n['id'] == el['nj'])
            L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
            
            b, h = (b_col, h_col) if el['type'] == 'Column' else (b_beam, h_beam)
            A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
            J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))

            T_matrix = get_transformation_matrix(ni_data, nj_data)
            k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
            el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

            w = el.get('load_kN_m', 0.0)
            if el['type'] == 'Beam' and w > 0:
                V, M = (w * L) / 2.0, (w * L**2) / 12.0
                F_local_ENL = np.zeros(12)
                F_local_ENL[2], F_local_ENL[4] = -V, -M
                F_local_ENL[8], F_local_ENL[10] = -V, M
                P_global = np.dot(T_matrix.T, F_local_ENL)
                dof_i, dof_j = el['ni'] * 6, el['nj'] * 6
                F_global[dof_i : dof_i + 6] += P_global[0:6]
                F_global[dof_j : dof_j + 6] += P_global[6:12]

        K_global = np.zeros((num_nodes * 6, num_nodes * 6))
        for el in elements:
            i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
            k_g = el['k_global']
            K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_g[0:6, 0:6]
            K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_g[0:6, 6:12]
            K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_g[6:12, 0:6]
            K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_g[6:12, 6:12]

        fixed_dofs = [dof for n in nodes if n['z'] == 0 for dof in range(n['id'] * 6, n['id'] * 6 + 6)]
        free_dofs = sorted(list(set(range(num_nodes * 6)) - set(fixed_dofs)))
        K_free = K_global[np.ix_(free_dofs, free_dofs)]
        F_free = F_global[free_dofs]

        # --- 4. Solver ---
        try:
            U_free = np.linalg.solve(K_free, F_free)
            U_global = np.zeros(num_nodes * 6)
            U_global[free_dofs] = U_free
            
            for el in elements:
                ni_data = next(n for n in nodes if n['id'] == el['ni'])
                nj_data = next(n for n in nodes if n['id'] == el['nj'])
                L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
                T_matrix = get_transformation_matrix(ni_data, nj_data)
                
                b, h = (b_col, h_col) if el['type'] == 'Column' else (b_beam, h_beam)
                A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
                J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))
                k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
                
                i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
                u_global = np.concatenate((U_global[i_dof:i_dof+6], U_global[j_dof:j_dof+6]))
                u_local = np.dot(T_matrix, u_global)
                
                F_local_ENL = np.zeros(12)
                w = el.get('load_kN_m', 0.0)
                if el['type'] == 'Beam' and w > 0:
                    V, M = (w * L) / 2.0, (w * L**2) / 12.0
                    F_local_ENL[2], F_local_ENL[4] = -V, -M
                    F_local_ENL[8], F_local_ENL[10] = -V, M
                    
                el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL

            st.success("🎉 Analysis Successful! Max Deflection: {:.2f} mm".format(np.max(np.abs(U_global)) * 1000))
        except np.linalg.LinAlgError:
            st.error("Solver Failed: Global Stiffness Matrix is singular.")
            st.stop()

        # --- 5. IS 456 DESIGN MODULE ---
        st.divider()
        st.header("5. Output & Design Summaries (IS 456:2000)")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Slab Design", "Beam Design", "Column Design", "Footing Design"])
        
        # --- TAB 1: SLABS ---
        with tab1:
            st.subheader("Floor Slab Parameters")
            slab_type = "One-Way Slab" if aspect_ratio > 2.0 else "Two-Way Slab"
            eff_depth_req = Lx * 1000 / (26 if slab_type == "Two-Way Slab" else 20) # Deflection control approximation
            
            st.write(f"**Classification:** {slab_type} ($L_y/L_x = {aspect_ratio:.2f}$)")
            st.write(f"**Required Effective Depth (Deflection):** {eff_depth_req:.1f} mm")
            
            if slab_thickness - 25 < eff_depth_req:
                st.warning(f"Slab depth {slab_thickness}mm might fail deflection criteria. Recommended overall depth: {eff_depth_req + 25} mm.")
            else:
                st.success(f"Provided Depth ({slab_thickness}mm) is safe for deflection.")

            # Simplified Grashoff's for moments
            w_u = q_factored
            if slab_type == "Two-Way Slab":
                r = aspect_ratio
                alpha_x = (r**4) / (1 + r**4) / 8 # Adjusted approximation for simple supports
                alpha_y = (r**2) / (1 + r**4) / 8
                Mx_u = alpha_x * w_u * (Lx**2)
                My_u = alpha_y * w_u * (Lx**2)
                st.write(f"**Factored Moments:** $M_x = {Mx_u:.2f}$ kN-m, $M_y = {My_u:.2f}$ kN-m")
            else:
                M_u = (w_u * Lx**2) / 8
                st.write(f"**Factored Bending Moment:** $M_u = {M_u:.2f}$ kN-m")

        # --- TAB 2: BEAMS ---
        with tab2:
            beam_results = []
            clear_cover = 0.030 
            d_beam = h_beam - clear_cover
            Mu_lim_kNm = 0.133 * fck * b_beam * (d_beam**2) * 1000 
            
            tau_c_assumed = 0.40
            tau_c_max = 0.62 * math.sqrt(fck)
            A_sv = 2 * (math.pi/4) * (8**2) 
            
            for el in elements:
                if el['type'] == 'Beam':
                    Mu_max = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
                    Ast_min = (0.85 * b_beam * d_beam * 1e6) / fy
                    status, Ast_req = "", 0.0
                    
                    if Mu_max <= Mu_lim_kNm:
                        status = "Singly Reinforced"
                        a = (0.87 * fy * fy) / (b_beam * d_beam * fck)
                        b_coef = 0.87 * fy * d_beam
                        c = -Mu_max / 1000.0
                        discriminant = b_coef**2 - 4*a*c
                        if discriminant >= 0:
                            Ast_m2 = (b_coef - math.sqrt(discriminant)) / (2*a)
                            Ast_req = max(Ast_m2 * 1e6, Ast_min)
                    else:
                        status = "Doubly Reinforced"
                        Ast_req = None

                    Vu_max = max(abs(el['F_internal'][2]), abs(el['F_internal'][8]))
                    tau_v = (Vu_max * 1000) / (b_beam * d_beam * 1e6)
                    
                    if tau_v > tau_c_max:
                        shear_status, sv_req = "Fail: Redesign Sec", "N/A"
                    elif tau_v <= tau_c_assumed / 2:
                        shear_status, sv_req = "Min Shear Steel", min(300, 0.75 * d_beam * 1000)
                    else:
                        shear_status = "Design Stirrups"
                        V_us = (tau_v - tau_c_assumed) * b_beam * d_beam * 1e6 / 1000
                        if V_us <= 0:
                            sv_calc = 0.87 * fy * A_sv / (0.4 * b_beam * 1000)
                        else:
                            sv_calc = 0.87 * fy * A_sv * (d_beam * 1000) / (V_us * 1000)
                        sv_req = min(sv_calc, 300, 0.75 * d_beam * 1000)

                    beam_results.append({
                        "ID": el['id'],
                        "Max M (kN-m)": round(Mu_max, 1),
                        "Flexure Status": status,
                        "Ast Bottom (mm²)": round(Ast_req, 1) if Ast_req else "Fail",
                        "Max V (kN)": round(Vu_max, 1),
                        "Shear Status": shear_status,
                        "8mm Stirrup c/c": round(sv_req, 0) if isinstance(sv_req, float) else sv_req
                    })
            st.dataframe(beam_results, use_container_width=True)

        # --- TAB 3: COLUMNS ---
        with tab3:
            col_results = []
            Ag = b_col * h_col * 1e6 
            Asc_min = 0.008 * Ag
            Asc_max = 0.040 * Ag
            Pu_conc = 0.4 * fck * Ag / 1000 
            
            for el in elements:
                if el['type'] == 'Column':
                    Pu_max = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
                    My_max = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
                    Mz_max = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
                    
                    status, Asc_req = "", 0.0
                    
                    if Pu_max <= Pu_conc:
                        status, Asc_req = "Safe: Min Steel", Asc_min
                    else:
                        Pu_steel = Pu_max - Pu_conc
                        stress_diff = (0.67 * fy) - (0.4 * fck)
                        Asc_calc = (Pu_steel * 1000) / stress_diff
                        
                        if Asc_calc <= Asc_max:
                            status, Asc_req = "Safe: Designed", max(Asc_calc, Asc_min)
                        else:
                            status, Asc_req = "Overstressed (>4%)", None
                            
                    col_results.append({
                        "ID": el['id'],
                        "Pu (kN)": round(Pu_max, 1),
                        "My (kN-m)": round(My_max, 1),
                        "Mz (kN-m)": round(Mz_max, 1),
                        "Column Status": status,
                        "Req. Steel (mm²)": round(Asc_req, 1) if Asc_req else "Fail"
                    })
            st.dataframe(col_results, use_container_width=True)

        # --- TAB 4: FOOTINGS ---
        with tab4:
            st.caption(f"Designing isolated pad footings based on SBC = {sbc} kN/m².")
            footing_results = []
            
            # Find base columns (z=0)
            for el in elements:
                if el['type'] == 'Column':
                    ni_node = next(n for n in nodes if n['id'] == el['ni'])
                    if ni_node['z'] == 0:
                        # Un-factor the load for sizing
                        Pu = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
                        P_service = Pu / 1.5 
                        
                        # Add 10% for footing self-weight
                        A_req = (P_service * 1.1) / sbc
                        B_side = math.ceil(math.sqrt(A_req) / 0.1) * 0.1 # Round up to nearest 100mm
                        
                        # Factored upward soil pressure
                        q_up = Pu / (B_side**2) 
                        
                        # Max Flexure (Face of Column)
                        c_dim = max(b_col, h_col)
                        M_u = q_up * B_side * ((B_side - c_dim)**2) / 8
                        
                        # Req effective depth for flexure
                        d_req = math.sqrt((M_u * 1000) / (0.138 * fck * B_side))
                        D_provided = math.ceil((d_req + 50) / 50) * 50 # Adding cover, rounding to nearest 50mm
                        
                        footing_results.append({
                            "Col ID": el['id'],
                            "Base Pu (kN)": round(Pu, 1),
                            "Req Area (m²)": round(A_req, 2),
                            "Provided Size (m)": f"{B_side:.1f} x {B_side:.1f}",
                            "Design M_u (kN-m)": round(M_u, 1),
                            "Req Depth D (mm)": round(D_provided, 0)
                        })
                        
            st.dataframe(footing_results, use_container_width=True)
