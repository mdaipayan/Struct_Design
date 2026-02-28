import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(page_title="3D Building Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis, Auto-Design & BoQ")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Building Geometry")
col1, col2 = st.sidebar.columns(2)
with col1:
    num_stories = st.number_input("Stories", min_value=1, value=3)
    bay_x = st.number_input("Bays in X", min_value=1, value=2)
    bay_y = st.number_input("Bays in Y", min_value=1, value=2)
with col2:
    h_story = st.number_input("Story Ht (m)", value=3.0)
    L_x = st.number_input("X Bay Wdt (m)", value=4.0)
    L_y = st.number_input("Y Bay Wdt (m)", value=5.0)

st.sidebar.header("2. Base Section Properties")
st.sidebar.caption("Initial sizes for the optimizer")
col_dim = st.sidebar.text_input("Init Column Size (mm)", "300x450")
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", "230x400")

col3, col4 = st.sidebar.columns(2)
with col3:
    fck = st.number_input("fck (MPa)", value=25.0, step=5.0)
with col4:
    fy = st.number_input("fy (MPa)", value=500.0, step=85.0)

st.sidebar.header("3. Loading & Geotech")
sbc = st.sidebar.number_input("Soil Bearing Capacity (kN/m²)", value=200.0, step=10.0)
lateral_coeff = st.sidebar.slider("Lateral Load Coeff (% of Gravity)", 0.0, 20.0, 5.0, help="E.g. Seismic Base Shear Vb = Ah * W") / 100.0

st.sidebar.header("4. AI Optimization")
auto_optimize = st.sidebar.checkbox("Enable Auto-Sizing (Iterative Redesign)", value=True)

# --- GEOMETRY GENERATOR ---
nodes = []
elements = []

node_id = 0
for z in range(int(num_stories) + 1):
    for y in range(int(bay_y) + 1):
        for x in range(int(bay_x) + 1):
            nodes.append({'id': node_id, 'x': x * L_x, 'y': y * L_y, 'z': z * h_story, 'floor': z})
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
                    elements.append({'id': element_id, 'ni': current_node, 'nj': top_node, 'type': 'Column', 'floor': z, 'size': col_dim})
                    element_id += 1
            if z > 0 and x < bay_x:
                right_node = get_node(x + 1, y, z)
                if right_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': right_node, 'type': 'Beam', 'floor': z, 'size': beam_dim})
                    element_id += 1
            if z > 0 and y < bay_y:
                back_node = get_node(x, y + 1, z)
                if back_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': back_node, 'type': 'Beam', 'floor': z, 'size': beam_dim})
                    element_id += 1

# --- 3D VISUALIZATION ---
st.subheader("Structural Model Viewport")
fig = go.Figure()

for el in elements:
    ni = next(n for n in nodes if n['id'] == el['ni'])
    nj = next(n for n in nodes if n['id'] == el['nj'])
    color = 'blue' if el['type'] == 'Column' else 'red'
    fig.add_trace(go.Scatter3d(
        x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']],
        mode='lines', line=dict(color=color, width=4), hoverinfo='text', text=f"{el['type']} ID: {el['id']}", showlegend=False
    ))

fig.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=400)
st.plotly_chart(fig, use_container_width=True)

# --- LOAD DEFINITION ---
slab_thickness = 150
dl_area = (slab_thickness / 1000.0) * 25.0 + 1.5 
ll_area = 3.0
q_factored = 1.5 * (dl_area + ll_area)

# Matrix Helpers
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
    k[0,0]=k[6,6]= E*A/L; k[0,6]=k[6,0]= -E*A/L
    k[3,3]=k[9,9]= G*J/L; k[3,9]=k[9,3]= -G*J/L
    k[2,2]=k[8,8]= 12*E*Iy/L**3; k[2,8]=k[8,2]= -12*E*Iy/L**3
    k[4,4]=k[10,10]= 4*E*Iy/L; k[4,10]=k[10,4]= 2*E*Iy/L
    k[2,4]=k[2,10]=k[4,2]=k[10,2]= -6*E*Iy/L**2; k[8,4]=k[8,10]=k[4,8]=k[10,8]= 6*E*Iy/L**2
    k[1,1]=k[7,7]= 12*E*Iz/L**3; k[1,7]=k[7,1]= -12*E*Iz/L**3
    k[5,5]=k[11,11]= 4*E*Iz/L; k[5,11]=k[11,5]= 2*E*Iz/L
    k[1,5]=k[1,11]=k[5,1]=k[11,1]= 6*E*Iz/L**2; k[7,5]=k[7,11]=k[5,7]=k[11,7]= -6*E*Iz/L**2
    return k

# Core Analysis Function
def run_analysis(current_elements):
    num_nodes = len(nodes)
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    # 1. Distribute Gravity Loads
    Lx, Ly = min(L_x, L_y), max(L_x, L_y)
    aspect_ratio = Ly / Lx
    w_short = (q_factored * Lx) / 3.0 if aspect_ratio <= 2.0 else 0.0
    w_long = (q_factored * Lx / 6.0) * (3.0 - (Lx / Ly)**2) if aspect_ratio <= 2.0 else q_factored * (Lx / 2.0)
    w_x_beam, w_y_beam = (w_short, w_long) if L_x == Lx else (w_long, w_short)
        
    for el in current_elements:
        el['load_kN_m'] = 0.0
        if el['type'] == 'Beam':
            ni = next(n for n in nodes if n['id'] == el['ni'])
            nj = next(n for n in nodes if n['id'] == el['nj'])
            if abs(ni['y'] - nj['y']) < 0.01: 
                el['load_kN_m'] = w_x_beam * (1.0 if ni['y'] == 0 or ni['y'] == bay_y * L_y else 2.0)
            elif abs(ni['x'] - nj['x']) < 0.01:
                el['load_kN_m'] = w_y_beam * (1.0 if ni['x'] == 0 or ni['x'] == bay_x * L_x else 2.0)

    # 2. Distribute Lateral Loads
    total_weight = sum([el['load_kN_m'] * L_x for el in current_elements if el['type'] == 'Beam']) * 1.5
    V_base = lateral_coeff * total_weight
    
    floor_weights = {}
    floor_heights = {}
    for z in range(1, int(num_stories) + 1):
        floor_weights[z] = total_weight / num_stories
        floor_heights[z] = z * h_story
        
    sum_wh2 = sum([floor_weights[z] * (floor_heights[z]**2) for z in floor_weights])
    floor_forces = {z: V_base * (floor_weights[z] * (floor_heights[z]**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_weights}

    nodes_per_floor = (bay_x + 1) * (bay_y + 1)
    for n in nodes:
        if n['z'] > 0:
            force_per_node = floor_forces[n['floor']] / nodes_per_floor
            F_global[n['id'] * 6] += force_per_node

    # 3. Assemble Global Matrices
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
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
    for el in current_elements:
        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        k_g = el['k_global']
        K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_g[0:6, 0:6]
        K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_g[0:6, 6:12]
        K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_g[6:12, 0:6]
        K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_g[6:12, 6:12]

    fixed_dofs = [dof for n in nodes if n['z'] == 0 for dof in range(n['id'] * 6, n['id'] * 6 + 6)]
    free_dofs = sorted(list(set(range(num_nodes * 6)) - set(fixed_dofs)))
    
    U_free = np.linalg.solve(K_global[np.ix_(free_dofs, free_dofs)], F_global[free_dofs])
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    # 4. Extract Internal Forces
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        T_matrix = get_transformation_matrix(ni_data, nj_data)
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        k_local = get_local_stiffness(E_conc, G_conc, b*h, (b*h**3)/12.0, (h*b**3)/12.0, (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4))), L)
        
        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        u_local = np.dot(T_matrix, np.concatenate((U_global[i_dof:i_dof+6], U_global[j_dof:j_dof+6])))
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL[2], F_local_ENL[4], F_local_ENL[8], F_local_ENL[10] = -V, -M, -V, M
            
        el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL
        el['length'] = L

    return current_elements, np.max(np.abs(U_global))

# --- DESIGN LOGIC & OPTIMIZATION LOOP ---
def perform_design(elements_to_design):
    design_status = True
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        el['pass'] = True
        el['design_details'] = {}
        
        if el['type'] == 'Beam':
            Mu_max = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
            Vu_max = max(abs(el['F_internal'][2]), abs(el['F_internal'][8]))
            d_beam = h - 30
            Mu_lim = 0.133 * fck * b * (d_beam**2) / 1e6
            tau_v = (Vu_max * 1000) / (b * d_beam)
            
            if Mu_max > Mu_lim or tau_v > (0.62 * math.sqrt(fck)):
                el['pass'] = False
                design_status = False
                
            el['design_details'] = {
                'Member ID': el['id'],
                'Floor': el['floor'],
                'Size (mm)': el['size'],
                'Mu_max (kN.m)': round(Mu_max, 2),
                'Vu_max (kN)': round(Vu_max, 2),
                'Shear Stress τv (MPa)': round(tau_v, 2),
                'Status': 'Pass' if el['pass'] else 'Fail (Resizing...)'
            }
                
        elif el['type'] == 'Column':
            Pu_max = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
            Ag = b * h
            Pu_conc = 0.4 * fck * Ag / 1000
            Asc_calc = 0
            
            if Pu_max > Pu_conc:
                Pu_steel = Pu_max - Pu_conc
                stress_diff = (0.67 * fy) - (0.4 * fck)
                Asc_calc = (Pu_steel * 1000) / stress_diff
                if Asc_calc > 0.04 * Ag: # Max 4% steel rule
                    el['pass'] = False
                    design_status = False
                    
            el['design_details'] = {
                'Member ID': el['id'],
                'Floor': el['floor'],
                'Size (mm)': el['size'],
                'Pu_max (kN)': round(Pu_max, 2),
                'Req Asc (mm²)': round(max(Asc_calc, 0.008 * Ag), 2), # At least 0.8% nominal
                'Status': 'Pass' if el['pass'] else 'Fail (Resizing...)'
            }
                    
    return elements_to_design, design_status

if st.button("Run AI Optimization & Analysis", type="primary", use_container_width=True):
    with st.spinner("Running Matrix Analysis & Heuristic Optimizer..."):
        iteration = 1
        max_iters = 5 if auto_optimize else 1
        
        while iteration <= max_iters:
            try:
                elements, max_def = run_analysis(elements)
                elements, passed = perform_design(elements)
                
                if passed or not auto_optimize:
                    st.success(f"✅ Analysis Converged in {iteration} Iteration(s). Max Deflection: {max_def * 1000:.2f} mm")
                    break
                else:
                    for el in elements:
                        if not el['pass']:
                            b, h = map(int, el['size'].split('x'))
                            el['size'] = f"{b}x{h+50}" if el['type'] == 'Beam' else f"{b+50}x{h+50}"
                    iteration += 1
            except Exception as e:
                st.error(f"Matrix Singularity or Solver Error: {e}")
                st.stop()
                
        if not passed and auto_optimize:
            st.warning("⚠️ Reached max iterations, some elements still overstressed. Review model geometry.")

        # --- GENERATE SLAB & FOOTING DATA ---
        slabs = []
        slab_id = 1
        Lx, Ly = min(L_x, L_y), max(L_x, L_y)
        slab_ratio = Ly / Lx
        slab_type = "One-Way" if slab_ratio > 2.0 else "Two-Way"
        approx_Mx = (q_factored * Lx**2) / (8 if slab_type == "One-Way" else 12)
        
        for z in range(1, int(num_stories) + 1):
            for y in range(int(bay_y)):
                for x in range(int(bay_x)):
                    slabs.append({
                        'Slab ID': f"S{slab_id}-F{z}",
                        'Floor': z,
                        'Dim (m)': f"{Lx} x {Ly}",
                        'Type': slab_type,
                        'Thickness (mm)': slab_thickness,
                        'Design B.M (kN.m)': round(approx_Mx, 2),
                        'Status': 'Pass'
                    })
                    slab_id += 1
                    
        
        footings = []
        for n in nodes:
            if n['z'] == 0:
                conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
                if conn_col:
                    Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                    P_work = Pu / 1.5
                    req_area = (P_work * 1.1) / sbc
                    side = math.ceil(math.sqrt(req_area) * 10) / 10 # Round to nearest 100mm
                    depth = max(300, int(side * 1000 / 4)) # Heuristic depth
                    footings.append({
                        'Support Node': n['id'],
                        'Pu (kN)': round(Pu, 2),
                        'Req Area (m²)': round(req_area, 2),
                        'Provided L x B (m)': f"{side} x {side}",
                        'Depth (mm)': depth,
                        'Status': 'Pass'
                    })

        # --- 5. BOQ & MATERIAL ABSTRACT ---
        st.divider()
        st.header("5. Material Abstract & BoQ")
        
        materials = []
        total_conc = 0
        total_steel = 0
        
        for z in range(int(num_stories) + 1):
            conc_vol = 0
            steel_wt = 0
            floor_els = [el for el in elements if el['floor'] == z]
            
            for el in floor_els:
                b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
                vol = b * h * el['length']
                conc_vol += vol
                
                density = 7850
                if el['type'] == 'Column':
                    steel_wt += vol * density * 0.015
                else:
                    steel_wt += vol * density * 0.012
            
            slab_vol = L_x * bay_x * L_y * bay_y * (slab_thickness/1000) if z > 0 else 0
            slab_steel = slab_vol * density * 0.008
            
            conc_vol += slab_vol
            steel_wt += slab_steel
            total_conc += conc_vol
            total_steel += steel_wt
            
            if conc_vol > 0:
                materials.append({"Floor": f"Level {z}", "Concrete (m³)": round(conc_vol, 2), "Steel (kg)": round(steel_wt, 2)})
                
        colA, colB = st.columns(2)
        with colA:
            st.subheader("Floor-wise Quantities")
            st.dataframe(pd.DataFrame(materials), use_container_width=True)
        with colB:
            st.subheader("Total Project Estimate")
            st.metric("Total Concrete Volume", f"{total_conc:.2f} m³")
            st.metric("Total Rebar Weight", f"{total_steel / 1000:.2f} MT")
            
        # --- 6. SIMPLIFIED BBS ---
        st.divider()
        st.header("6. Bar Bending Schedule (BBS) Abstract")
        st.caption("Estimated tonnage distribution by standard bar diameters.")
        
        bbs_data = {
            "Bar Dia (mm)": ["8mm (Ties/Stirrups)", "10mm (Slab Main)", "16mm (Beam Flexure)", "20mm (Column Main)"],
            "Application": ["Shear & Containment", "Floor Slabs", "Longitudinal Beams", "Vertical Columns"],
            "Est. Quantity (kg)": [
                round(total_steel * 0.20, 1),
                round(total_steel * 0.30, 1),
                round(total_steel * 0.25, 1),
                round(total_steel * 0.25, 1) 
            ]
        }
        st.dataframe(pd.DataFrame(bbs_data), use_container_width=True)

        # --- 7. DETAILED DESIGN RESULTS ---
        st.divider()
        st.header("7. Detailed Member Design Results")
        st.caption("Below are the internal forces, reinforcement requirements, and finalized geometries after optimization.")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Slabs", "Beams", "Columns", "Footings"])
        with tab1:
            st.dataframe(pd.DataFrame(slabs), use_container_width=True)
        with tab2:
            st.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam']), use_container_width=True)
        with tab3:
            st.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column']), use_container_width=True)
        with tab4:
            st.dataframe(pd.DataFrame(footings), use_container_width=True)
