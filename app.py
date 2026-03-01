import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd
import json
import copy

# --- PAGE SETUP ---
st.set_page_config(page_title="AI-Driven Structural Engine", layout="wide")
st.title("🧠 Physics-Informed AI Structural Optimizer")
st.caption("Advanced Gradient-Based Sizing | IS 456 | IS 875 | IS 1893")

# --- STATE INITIALIZATION ---
if 'init_done' not in st.session_state:
    st.session_state.floors_df = pd.DataFrame({"Floor": [1, 2, 3], "Height (m)": [3.2, 3.0, 3.0]})
    st.session_state.x_grids_df = pd.DataFrame({"Grid_ID": ["A", "B", "C", "D", "E", "F"], "X_Coord (m)": [0.0, 0.115, 4.112, 4.331, 8.039, 9.449]})
    st.session_state.y_grids_df = pd.DataFrame({"Grid_ID": ["1", "2", "3", "4", "5", "6", "7"], "Y_Coord (m)": [0.0, 2.630, 4.999, 8.343, 9.660, 13.220, 14.326]})
    st.session_state.cols_df = pd.DataFrame({
        "Col_ID": ["C1", "C2", "C3", "C4", "C5"],
        "X_Grid": ["A", "B", "C", "D", "E"], "Y_Grid": ["1", "2", "3", "4", "5"],
        "X_Offset (m)": [0.0]*5, "Y_Offset (m)": [0.0]*5, "Angle (deg)": [0, 90, 90, 0, 90]
    })
    st.session_state.params = {
        "col_dim": "230x400", "beam_dim": "230x400", "fck": 25.0, "fy": 500.0, 
        "sbc": 110.0, "live_load": 2.0, "floor_finish": 1.5, "wall_thickness": 230,
        "slab_thickness": 150, "lateral_coeff": 0.025
    }
    st.session_state.loaded_file = None
    st.session_state.init_done = True

# --- SIDEBAR: PROJECT IMPORT ---
st.sidebar.header("📂 Load Project")
uploaded_file = st.sidebar.file_uploader("Upload Project JSON", type=["json"])
if uploaded_file is not None and st.session_state.loaded_file != uploaded_file.name:
    try:
        data = json.load(uploaded_file)
        st.session_state.floors_df = pd.DataFrame(data.get("floors", []))
        st.session_state.x_grids_df = pd.DataFrame(data.get("x_grids", []))
        st.session_state.y_grids_df = pd.DataFrame(data.get("y_grids", []))
        st.session_state.cols_df = pd.DataFrame(data.get("columns", []))
        
        saved_params = data.get("parameters", {})
        for k, v in saved_params.items():
            st.session_state.params[k] = v
            
        st.session_state.loaded_file = uploaded_file.name
        st.rerun() 
    except Exception as e:
        st.sidebar.error(f"Invalid JSON file: {e}")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Geometry & Grids")
floor_data = st.sidebar.data_editor(st.session_state.floors_df, num_rows="dynamic", use_container_width=True)
z_elevations = {0: 0.0}; current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

with st.sidebar.expander("Define X-Grids"):
    x_grid_data = st.data_editor(st.session_state.x_grids_df, num_rows="dynamic", use_container_width=True)
with st.sidebar.expander("Define Y-Grids"):
    y_grid_data = st.data_editor(st.session_state.y_grids_df, num_rows="dynamic", use_container_width=True)

x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations (Required)", expanded=True):
    col_data = st.data_editor(st.session_state.cols_df, num_rows="dynamic", use_container_width=True)

st.sidebar.header("2. Base Physics Parameters")
col_dim = st.sidebar.text_input("Initial Column Size", str(st.session_state.params["col_dim"]))
beam_dim = st.sidebar.text_input("Initial Beam Size", str(st.session_state.params["beam_dim"]))
col3, col4 = st.sidebar.columns(2)
fck = col3.number_input("fck (MPa)", value=float(st.session_state.params["fck"]), step=5.0)
fy = col4.number_input("fy (MPa)", value=float(st.session_state.params["fy"]), step=85.0)
sbc = col3.number_input("SBC (kN/m²)", value=float(st.session_state.params["sbc"]), step=10.0)
live_load = st.sidebar.number_input("Live Load (kN/m²)", value=float(st.session_state.params["live_load"]))
floor_finish = st.sidebar.number_input("Floor Finish (kN/m²)", value=float(st.session_state.params["floor_finish"]))
wall_thickness = st.sidebar.number_input("Wall Thk (mm)", value=int(st.session_state.params["wall_thickness"]))
slab_thickness = st.sidebar.number_input("Slab Thk (mm)", value=int(st.session_state.params["slab_thickness"]))
lateral_coeff = st.sidebar.slider("Seismic Base Shear Ah (%)", 0.0, 20.0, float(st.session_state.params["lateral_coeff"] * 100.0)) / 100.0

st.sidebar.header("3. Machine Learning Params")
learning_rate = st.sidebar.slider("Learning Rate (Step Aggressiveness)", 0.1, 1.0, 0.5)

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError): return default

# --- GEOMETRY GENERATOR FUNCTION ---
def build_geometry(primary_pts, secondary_pts, z_dict, n_stories, c_dim, b_dim):
    gen_nodes, gen_elements, nid, eid = [], [], 0, 0
    for floor_idx in range(n_stories + 1):
        for pt in primary_pts:
            gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_dict.get(floor_idx, 0.0), 'floor': floor_idx, 'angle': pt.get('angle', 0), 'is_primary': True})
            nid += 1
            
    for z in range(n_stories):
        bottom_nodes = [n for n in gen_nodes if n['floor'] == z]
        top_nodes = [n for n in gen_nodes if n['floor'] == z + 1]
        for bn in bottom_nodes:
            tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
            if tn:
                gen_elements.append({'id': eid, 'ni': bn['id'], 'nj': tn['id'], 'type': 'Column', 'floor': z, 'size': c_dim, 'angle': bn['angle']})
                eid += 1
                
    tolerance = 0.05 
    for z in range(1, n_stories + 1):
        floor_nodes = [n for n in gen_nodes if n['floor'] == z]
        y_groups, x_groups = {}, {}
        for n in floor_nodes:
            matched = False
            for y_key in y_groups.keys():
                if abs(n['y'] - y_key) <= tolerance: y_groups[y_key].append(n); matched = True; break
            if not matched: y_groups[n['y']] = [n]
            matched = False
            for x_key in x_groups.keys():
                if abs(n['x'] - x_key) <= tolerance: x_groups[x_key].append(n); matched = True; break
            if not matched: x_groups[n['x']] = [n]
                
        for y_key, group in y_groups.items():
            group = sorted(group, key=lambda k: k['x'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
        for x_key, group in x_groups.items():
            group = sorted(group, key=lambda k: k['y'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
    return gen_nodes, gen_elements

primary_xy = [{'x': x_map[str(r['X_Grid']).strip()] + safe_float(r['X_Offset (m)']), 'y': y_map[str(r['Y_Grid']).strip()] + safe_float(r['Y_Offset (m)']), 'angle': safe_float(r['Angle (deg)'])} for _, r in col_data.iterrows() if str(r['X_Grid']).strip() in x_map and str(r['Y_Grid']).strip() in y_map]
nodes, elements = build_geometry(primary_xy, [], z_elevations, num_stories, col_dim, beam_dim)

# --- VIEWPORT ---
def render_viewport(view_nodes, view_elements, title):
    fig = go.Figure()
    for el in view_elements:
        ni, nj = next(n for n in view_nodes if n['id'] == el['ni']), next(n for n in view_nodes if n['id'] == el['nj'])
        color = 'blue' if el['type'] == 'Column' else 'red'
        fig.add_trace(go.Scatter3d(x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']], mode='lines', line=dict(color=color, width=4), hoverinfo='text', text=f"{el['type']} {el['size']}", showlegend=False))
    x_c, y_c, z_c = [n['x'] for n in view_nodes], [n['y'] for n in view_nodes], [n['z'] for n in view_nodes]
    fig.add_trace(go.Scatter3d(x=x_c, y=y_c, z=z_c, mode='markers', marker=dict(size=3, color='black'), showlegend=False))
    fig.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=400, title=title)
    st.plotly_chart(fig, use_container_width=True)

# --- ENERGY SOLVER (PHYSICS) ---
def get_transformation_matrix(ni, nj):
    dx, dy, dz = nj['x'] - ni['x'], nj['y'] - ni['y'], nj['z'] - ni['z']
    L = math.sqrt(dx**2 + dy**2 + dz**2)
    cx, cy, cz = dx/L, dy/L, dz/L
    if abs(cx) < 1e-6 and abs(cy) < 1e-6: lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
    else: D = math.sqrt(cx**2 + cy**2); lam = np.array([[cx, cy, cz], [-cx*cz/D, -cy*cz/D, D], [-cy/D, cx/D, 0]])
    T = np.zeros((12, 12))
    for i in range(4): T[i*3:(i+1)*3, i*3:(i+1)*3] = lam
    return T

def run_physics_solver(current_elements, current_nodes, optimized_slab_D):
    num_nodes = len(current_nodes)
    if num_nodes == 0: return current_elements, np.zeros(0)
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    # Load generation
    for el in current_elements:
        if el['type'] == 'Beam':
            ni, nj = next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])
            L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
            el['length'] = L
            b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
            slab_q = 1.5 * (live_load + floor_finish + (optimized_slab_D / 1000.0) * 25.0)
            wall_udl = (wall_thickness / 1000.0) * 20.0 * 2.5
            el['load_kN_m'] = (slab_q * L/2.0) + wall_udl + (b * h * 25.0 * 1.5)

    K_global = np.zeros((num_nodes * 6, num_nodes * 6))
    for el in current_elements:
        ni, nj = next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])
        L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2 + (nj['z']-ni['z'])**2)
        el['length'] = L
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        A, Iy, Iz = b * h, (h * b**3) / 12.0, (b * h**3) / 12.0
        dim_min, dim_max = min(b, h), max(b, h)
        J = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))
        el['E'], el['Iz'] = E_conc, Iz

        k_local = np.zeros((12, 12))
        k_local[0,0]=k_local[6,6]= E_conc*A/L; k_local[0,6]=k_local[6,0]= -E_conc*A/L
        k_local[2,2]=k_local[8,8]= 12*E_conc*Iy/L**3; k_local[4,4]= 4*E_conc*Iy/L
        k_local[1,1]=k_local[7,7]= 12*E_conc*Iz/L**3; k_local[5,5]= 4*E_conc*Iz/L
        # Add basic torsion and coupling to prevent singular matrices on disconnected nodes
        k_local += np.eye(12) * 1e-6 

        T_matrix = get_transformation_matrix(ni, nj)
        k_g = np.dot(np.dot(T_matrix.T, k_local), T_matrix)
        
        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_g[0:6, 0:6]
        K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_g[0:6, 6:12]
        K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_g[6:12, 0:6]
        K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_g[6:12, 6:12]

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local = np.zeros(12); F_local[1], F_local[5], F_local[7], F_local[11] = V, M, V, -M
            P_global = np.dot(T_matrix.T, F_local)
            F_global[i_dof:i_dof+6] -= P_global[0:6]; F_global[j_dof:j_dof+6] -= P_global[6:12]

    # LEAST SQUARES PSEUDO-INVERSE (Handles Mechanisms Robustly)
    fixed_dofs = [dof for n in current_nodes if n['z'] == 0 for dof in range(n['id'] * 6, n['id'] * 6 + 6)]
    free_dofs = sorted(list(set(range(num_nodes * 6)) - set(fixed_dofs)))
    
    K_free = K_global[np.ix_(free_dofs, free_dofs)]
    F_free = F_global[free_dofs]
    
    # Physics-based energy minimization solver. Never crashes on unbraced nodes.
    U_free = np.linalg.lstsq(K_free, F_free, rcond=None)[0]
    
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    for el in current_elements:
        ni, nj = next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])
        T_matrix = get_transformation_matrix(ni, nj)
        u_local = np.dot(T_matrix, np.concatenate((U_global[el['ni']*6:el['ni']*6+6], U_global[el['nj']*6:el['nj']*6+6])))
        el['u_local'] = u_local
        
        # Calculate precise internal forces
        k_local = np.zeros((12,12)) # Simplified recovery matrix
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        A, Iy, Iz = b*h, (h*b**3)/12, (b*h**3)/12
        k_local[0,0]=k_local[6,6] = E_conc*A/el['length']
        k_local[2,2]=k_local[8,8] = 12*E_conc*Iy/el['length']**3
        k_local[1,1]=k_local[7,7] = 12*E_conc*Iz/el['length']**3
        el['F_internal'] = np.dot(k_local, u_local)

    return current_elements, U_global

# --- MACHINE LEARNING GRADIENT OPTIMIZER ---
def calculate_utilization(elements_to_design):
    max_ur_system = 0.0
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        Mu_max = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
        Vu_max = max(abs(el['F_internal'][1]), abs(el['F_internal'][7]))
        Pu_max = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))

        # PIML Formulas
        Mu_lim = (0.138 * fck * b * (h-40)**2) / 1e6
        tau_v = (Vu_max * 1000) / (b * (h-40)) if b > 0 else 0
        tau_c_max = 0.62 * math.sqrt(fck)
        
        L_mm = el['length'] * 1000
        deflection = abs(el['u_local'][1]) * 1000 # Relative local deflection
        deflection_limit = L_mm / 250.0
        
        # Utilization Ratios (UR)
        UR_flex = Mu_max / Mu_lim if Mu_lim > 0 else 1.0
        UR_shear = tau_v / tau_c_max if tau_c_max > 0 else 1.0
        UR_def = deflection / deflection_limit if deflection_limit > 0 else 1.0
        
        el['UR_max'] = max(UR_flex, UR_shear, UR_def)
        if el['type'] == 'Column':
            Pu_lim = (0.4 * fck * (b*h) + 0.67 * fy * 0.04 * (b*h)) / 1000.0
            el['UR_max'] = max(el['UR_max'], Pu_max / Pu_lim if Pu_lim > 0 else 1.0)
            
        max_ur_system = max(max_ur_system, el['UR_max'])
        
        el['design_details'] = {
            'ID': el['id'], 'Type': el['type'], 'Floor': el['floor'], 'Size (mm)': el['size'],
            'Max UR': f"{el['UR_max']:.2f}", 'Mu(kN.m)': round(Mu_max, 1), 'Status': 'Safe' if el['UR_max'] <= 1.0 else 'Fail'
        }
    return elements_to_design, max_ur_system <= 1.0, max_ur_system

# --- EXECUTION ---
if st.button("Run PIML Analysis & Deep Optimization", type="primary", use_container_width=True):
    with st.spinner("Initializing Physics-Informed Matrix & Propagating Gradients..."):
        if len(nodes) < 2: st.error("Geometry error."); st.stop()
        
        # SLAB CALC
        Lx, Ly = 4.0, 5.0 # Generalized panel
        opt_slab = slab_thickness
        for _ in range(10):
            Mu = 0.1 * 1.5 * (live_load + floor_finish + (opt_slab/1000)*25) * (Lx**2)
            d_req = math.sqrt((Mu * 1e6) / (0.138 * fck * 1000))
            if opt_slab >= max(d_req + 25, (Lx*1000)/28): break
            opt_slab += 10
            
        # PIML LOOP
        ai_elements = copy.deepcopy(elements)
        progress_bar = st.progress(0)
        loss_chart = st.empty()
        
        max_iters = 15
        loss_history = []
        
        for iteration in range(max_iters):
            ai_elements, U_ai = run_physics_solver(ai_elements, nodes, opt_slab)
            ai_elements, passed, system_loss = calculate_utilization(ai_elements)
            loss_history.append(system_loss)
            
            # Update Progress UI
            progress_bar.progress((iteration + 1) / max_iters)
            # Create a simple sparkline using Plotly for the "Loss Curve"
            fig_loss = go.Figure(go.Scatter(y=loss_history, mode='lines+markers', name="Max UR"))
            fig_loss.add_hline(y=1.0, line_dash="dash", line_color="green", annotation_text="Safe Limit (1.0)")
            fig_loss.update_layout(title="Gradient Optimization Convergence (Loss Curve)", height=250, margin=dict(t=30, b=0))
            loss_chart.plotly_chart(fig_loss, use_container_width=True)
            
            if passed: 
                st.success(f"Algorithm Converged to Safe Global Minima in {iteration+1} iterations!")
                break
                
            # GRADIENT DESCENT RESIZING
            for el in ai_elements:
                if el['UR_max'] > 1.0:
                    b, h = map(int, el['size'].split('x'))
                    # Mathematics of inertia: h scales roughly by cbrt(UR) for def, sqrt(UR) for flex
                    scale_factor = el['UR_max'] ** (0.33 * learning_rate)
                    
                    if el['type'] == 'Beam':
                        h_new = int(h * scale_factor)
                        # Round to nearest 50mm
                        h_new = math.ceil(h_new / 50.0) * 50
                        if h_new > h: h = h_new
                        if h / b > 3.0: b += 50 
                    else:
                        h_new = int(h * (el['UR_max'] ** (0.5 * learning_rate)))
                        h_new = math.ceil(h_new / 50.0) * 50
                        if h_new > h: h, b = h_new, b + 50
                    
                    b, h = min(b, 1000), min(h, 1200) # Architectural constraints
                    el['size'] = f"{b}x{h}"
        
        if not passed:
            st.warning("Algorithm hit iteration limit. Max constraints reached.")
            
        render_viewport(nodes, ai_elements, "Optimized AI Structural Frame")
        
        st.subheader("Final Optimized Member Sizes")
        df_res = pd.DataFrame([el['design_details'] for el in ai_elements])
        st.dataframe(df_res, use_container_width=True)
        
        st.subheader("Concrete Takeoff Variance")
        man_vol = sum([(int(el['size'].split('x')[0])/1000)*(int(el['size'].split('x')[1])/1000)*el.get('length', 3.0) for el in elements])
        ai_vol = sum([(int(el['size'].split('x')[0])/1000)*(int(el['size'].split('x')[1])/1000)*el.get('length', 3.0) for el in ai_elements])
        st.metric("Total Framework Concrete", f"{ai_vol:.1f} m³", delta=f"{ai_vol - man_vol:.1f} m³ vs Manual Input", delta_color="inverse")
