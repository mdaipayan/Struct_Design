import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd
import json
import copy

# --- PAGE SETUP ---
st.set_page_config(page_title="IS Code Compliant 3D Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & IS-Code Auto-Design")
st.caption("Strict Compliance: IS 456 (Flexure, Shear, Deflection), IS 875, IS 1893 (Storey Drift)")

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
        "sbc": 150.0, "live_load": 2.0, "floor_finish": 1.5, "wall_thickness": 230,
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
st.sidebar.header("1. Floor Elevations")
floor_data = st.sidebar.data_editor(st.session_state.floors_df, num_rows="dynamic", width="stretch")

z_elevations = {0: 0.0}
current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

st.sidebar.header("2. Structural Grids (From Plan)")
with st.sidebar.expander("Define X-Grids", expanded=True):
    x_grid_data = st.data_editor(st.session_state.x_grids_df, num_rows="dynamic", width="stretch", key="x_grids")

with st.sidebar.expander("Define Y-Grids", expanded=True):
    y_grid_data = st.data_editor(st.session_state.y_grids_df, num_rows="dynamic", width="stretch", key="y_grids")

st.sidebar.header("3. Column Placement")
x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations & Orientations", expanded=True):
    col_data = st.data_editor(st.session_state.cols_df, num_rows="dynamic", width="stretch")

st.sidebar.header("4. IS Code Design Parameters")
col_dim = st.sidebar.text_input("Manual Column Size (mm)", str(st.session_state.params["col_dim"]))
beam_dim = st.sidebar.text_input("Manual Beam Size (mm)", str(st.session_state.params["beam_dim"]))

col3, col4 = st.sidebar.columns(2)
fck = col3.number_input("fck (MPa)", value=float(st.session_state.params["fck"]), step=5.0)
fy = col4.number_input("fy (MPa)", value=float(st.session_state.params["fy"]), step=85.0)
sbc = col3.number_input("SBC (kN/m²)", value=float(st.session_state.params["sbc"]), step=10.0)

st.sidebar.subheader("Applied Loads (IS 875/1893)")
live_load = st.sidebar.number_input("Live Load (kN/m²)", value=float(st.session_state.params["live_load"]))
floor_finish = st.sidebar.number_input("Floor Finish (kN/m²)", value=float(st.session_state.params["floor_finish"]))
wall_thickness = st.sidebar.number_input("Exterior Wall Thk (mm)", value=int(st.session_state.params["wall_thickness"]))
slab_thickness = st.sidebar.number_input("Manual Slab Thk (mm)", value=int(st.session_state.params["slab_thickness"]))
lateral_coeff_input = st.sidebar.slider("Seismic Base Shear Ah (%)", 0.0, 20.0, float(st.session_state.params["lateral_coeff"] * 100.0))
lateral_coeff = lateral_coeff_input / 100.0

# --- SIDEBAR: PROJECT EXPORT ---
st.sidebar.divider()
st.sidebar.header("💾 Save Project")
def export_project_data():
    project_data = {
        "floors": floor_data.to_dict(orient="records"),
        "x_grids": x_grid_data.to_dict(orient="records"),
        "y_grids": y_grid_data.to_dict(orient="records"),
        "columns": col_data.to_dict(orient="records"),
        "parameters": {
            "fck": fck, "fy": fy, "sbc": sbc, "col_dim": col_dim, "beam_dim": beam_dim,
            "live_load": live_load, "floor_finish": floor_finish, "wall_thickness": wall_thickness,
            "slab_thickness": slab_thickness, "lateral_coeff": lateral_coeff
        }
    }
    return json.dumps(project_data, indent=4)

st.sidebar.download_button(
    label="⬇️ Download Project Inputs (JSON)",
    data=export_project_data(),
    file_name="structural_project_data.json",
    mime="application/json",
    width="stretch"
)

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError): return default

# --- GEOMETRY GENERATOR FUNCTION ---
def build_geometry(primary_pts, secondary_pts, z_dict, n_stories, c_dim, b_dim):
    gen_nodes = []
    gen_elements = []
    nid = 0
    
    for floor_idx in range(n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in primary_pts:
            gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': pt.get('angle', 0), 'is_primary': True})
            nid += 1
            
    for floor_idx in range(1, n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in secondary_pts:
            if pt['floor'] == floor_idx:
                gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': 0, 'is_primary': False})
                nid += 1

    eid = 0
    for z in range(n_stories):
        bottom_nodes = [n for n in gen_nodes if n['floor'] == z and n.get('is_primary', True)]
        top_nodes = [n for n in gen_nodes if n['floor'] == z + 1 and n.get('is_primary', True)]
        for bn in bottom_nodes:
            tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
            if tn:
                gen_elements.append({'id': eid, 'ni': bn['id'], 'nj': tn['id'], 'type': 'Column', 'floor': z, 'size': c_dim, 'angle': bn['angle']})
                eid += 1
                
    tolerance = 0.05 
    for z in range(1, n_stories + 1):
        floor_nodes = [n for n in gen_nodes if n['floor'] == z]
        
        y_groups = {}
        for n in floor_nodes:
            matched = False
            for y_key in y_groups.keys():
                if abs(n['y'] - y_key) <= tolerance:
                    y_groups[y_key].append(n); matched = True; break
            if not matched: y_groups[n['y']] = [n]
                
        for y_key, group in y_groups.items():
            group = sorted(group, key=lambda k: k['x'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
                
        x_groups = {}
        for n in floor_nodes:
            matched = False
            for x_key in x_groups.keys():
                if abs(n['x'] - x_key) <= tolerance:
                    x_groups[x_key].append(n); matched = True; break
            if not matched: x_groups[n['x']] = [n]
                
        for x_key, group in x_groups.items():
            group = sorted(group, key=lambda k: k['y'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
                
    return gen_nodes, gen_elements

primary_xy = []
for idx, row in col_data.iterrows():
    xg = str(row.get('X_Grid', '')).strip()
    yg = str(row.get('Y_Grid', '')).strip()
    if xg in x_map and yg in y_map:
        calc_x = x_map[xg] + safe_float(row.get('X_Offset (m)'))
        calc_y = y_map[yg] + safe_float(row.get('Y_Offset (m)'))
        primary_xy.append({'x': calc_x, 'y': calc_y, 'angle': safe_float(row.get('Angle (deg)'))})

nodes, elements = build_geometry(primary_xy, [], z_elevations, num_stories, col_dim, beam_dim)

# --- VIEWPORT RENDERING FUNCTION ---
def render_viewport(view_nodes, view_elements, title="Structural Model Viewport", suffix="1"):
    st.subheader(title)
    fig = go.Figure()
    for el in view_elements:
        ni = next(n for n in view_nodes if n['id'] == el['ni'])
        nj = next(n for n in view_nodes if n['id'] == el['nj'])
        color = 'blue' if el['type'] == 'Column' else 'red'
        fig.add_trace(go.Scatter3d(x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']], mode='lines', line=dict(color=color, width=4), hoverinfo='text', text=f"{el['type']} ID:{el['id']}", showlegend=False))

    x_coords = [n['x'] for n in view_nodes]
    y_coords = [n['y'] for n in view_nodes]
    z_coords = [n['z'] for n in view_nodes]
    fig.add_trace(go.Scatter3d(x=x_coords, y=y_coords, z=z_coords, mode='markers', marker=dict(size=3, color='black'), hoverinfo='text', text=[f"Node: {n['id']}" for n in view_nodes], showlegend=False))
    fig.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=400)
    st.plotly_chart(fig, width="stretch")

render_viewport(nodes, elements, "Initial Input Model", "init")

# --- ANALYSIS ENGINE FUNCTIONS ---
def get_transformation_matrix(ni, nj):
    dx, dy, dz = nj['x'] - ni['x'], nj['y'] - ni['y'], nj['z'] - ni['z']
    L = math.sqrt(dx**2 + dy**2 + dz**2)
    cx, cy, cz = dx/L, dy/L, dz/L
    lam = np.zeros((3, 3))
    if abs(cx) < 1e-6 and abs(cy) < 1e-6: lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
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

def run_analysis_dynamic(current_elements, current_nodes, optimized_slab_D):
    num_nodes = len(current_nodes)
    if num_nodes == 0: return current_elements, np.zeros(0)
    
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    X_coords, Y_coords = [n['x'] for n in current_nodes], [n['y'] for n in current_nodes]
    floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.85 if X_coords else 0
    total_dl_per_m2 = ((optimized_slab_D / 1000.0) * 25.0) + floor_finish
    total_floor_dl = floor_area * total_dl_per_m2
    total_floor_ll = floor_area * live_load
    
    total_beam_len = sum([math.sqrt((next(n for n in current_nodes if n['id'] == el['nj'])['x']-next(n for n in current_nodes if n['id'] == el['ni'])['x'])**2 + (next(n for n in current_nodes if n['id'] == el['nj'])['y']-next(n for n in current_nodes if n['id'] == el['ni'])['y'])**2) for el in current_elements if el['type'] == 'Beam'])
    if total_beam_len == 0: total_beam_len = 1.0

    seismic_weight_total = 0.0
    seismic_mass_per_floor = total_floor_dl + ((0.25 if live_load <= 3.0 else 0.50) * total_floor_ll)

    for el in current_elements:
        el['load_kN_m'] = 0.0
        if el['type'] == 'Beam':
            ni = next(n for n in current_nodes if n['id'] == el['ni'])
            nj = next(n for n in current_nodes if n['id'] == el['nj'])
            L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
            el['length'] = L
            b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
            if el.get('angle', 0) == 90: b, h = h, b 
            
            is_secondary = not (ni.get('is_primary', True) and nj.get('is_primary', True))
            wall_udl = 0.0
            if not is_secondary: 
                h_story = (z_elevations.get(ni['floor'], 3.0) - z_elevations.get(ni['floor']-1, 0.0)) if ni['floor']>0 else 3.0
                wall_udl = (wall_thickness / 1000.0) * 20.0 * max(0.1, (h_story - h))

            area_dl_udl = total_floor_dl / total_beam_len
            area_ll_udl = total_floor_ll / total_beam_len
            self_wt = b * h * 25.0
            el['load_kN_m'] = 1.5 * (area_dl_udl + area_ll_udl + wall_udl + self_wt)
            seismic_weight_total += (wall_udl + self_wt) * L

    seismic_weight_total += (seismic_mass_per_floor * num_stories)
    V_base = lateral_coeff * seismic_weight_total
    
    floor_weights = {z: seismic_weight_total / num_stories for z in range(1, num_stories + 1)}
    sum_wh2 = sum([floor_weights[z] * (z_elevations[z]**2) for z in floor_weights])
    floor_forces = {z: V_base * (floor_weights[z] * (z_elevations[z]**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_weights}

    for n in current_nodes:
        if n['z'] > 0:
            nodes_this_floor = len([nd for nd in current_nodes if nd['floor'] == n['floor']])
            F_global[n['id'] * 6] += (floor_forces[n['floor']] / nodes_this_floor) if nodes_this_floor > 0 else 0

    for el in current_elements:
        ni_data = next(n for n in current_nodes if n['id'] == el['ni'])
        nj_data = next(n for n in current_nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        el['length'] = L
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
        A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
        dim_min, dim_max = min(b, h), max(b, h)
        J_sec = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))

        el['E'], el['Iz'] = E_conc, Iz_sec
        T_matrix = get_transformation_matrix(ni_data, nj_data)
        k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL = np.zeros(12)
            F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = V, M, V, -M
            P_global = np.dot(T_matrix.T, F_local_ENL)
            F_global[el['ni']*6 : el['ni']*6+6] -= P_global[0:6]
            F_global[el['nj']*6 : el['nj']*6+6] -= P_global[6:12]

    K_global = np.zeros((num_nodes * 6, num_nodes * 6))
    for el in current_elements:
        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        k_g = el['k_global']
        K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_g[0:6, 0:6]
        K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_g[0:6, 6:12]
        K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_g[6:12, 0:6]
        K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_g[6:12, 6:12]

    fixed_dofs = [dof for n in current_nodes if n['z'] == 0 for dof in range(n['id'] * 6, n['id'] * 6 + 6)]
    free_dofs = sorted(list(set(range(num_nodes * 6)) - set(fixed_dofs)))
    
    try:
        U_free = np.linalg.solve(K_global[np.ix_(free_dofs, free_dofs)], F_global[free_dofs])
    except np.linalg.LinAlgError:
        raise Exception("Matrix is Singular. Geometry is unstable (Missing/Unbraced Columns).")
        
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    for el in current_elements:
        ni_data = next(n for n in current_nodes if n['id'] == el['ni'])
        nj_data = next(n for n in current_nodes if n['id'] == el['nj'])
        T_matrix = get_transformation_matrix(ni_data, nj_data)
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
        dim_min, dim_max = min(b, h), max(b, h)
        J_sec = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))
        k_local = get_local_stiffness(E_conc, G_conc, b*h, (b*h**3)/12.0, (h*b**3)/12.0, J_sec, el['length'])
        u_local = np.dot(T_matrix, np.concatenate((U_global[el['ni']*6:el['ni']*6+6], U_global[el['nj']*6:el['nj']*6+6])))
        el['u_local'] = u_local
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * el['length']) / 2.0, (w * el['length']**2) / 12.0
            F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = V, M, V, -M
            
        el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL

    return current_elements, U_global

def perform_design(elements_to_design, U_global, current_nodes, z_elevations):
    design_status = True
    mulim_coeff = 0.133 if fy >= 500 else 0.138 
    tau_c_max = 0.62 * math.sqrt(fck) 
    
    floor_drifts = {}
    for z in range(1, num_stories + 1):
        nodes_z = [n for n in current_nodes if n['floor'] == z]
        nodes_prev = [n for n in current_nodes if n['floor'] == z - 1]
        
        max_x_z = max([abs(U_global[n['id']*6]) for n in nodes_z]) if nodes_z else 0
        max_x_prev = max([abs(U_global[n['id']*6]) for n in nodes_prev]) if nodes_prev else 0
        max_y_z = max([abs(U_global[n['id']*6 + 1]) for n in nodes_z]) if nodes_z else 0
        max_y_prev = max([abs(U_global[n['id']*6 + 1]) for n in nodes_prev]) if nodes_prev else 0
        
        drift_x = abs(max_x_z - max_x_prev)
        drift_y = abs(max_y_z - max_y_prev)
        h_story = z_elevations.get(z, 3.0) - z_elevations.get(z-1, 0.0)
        
        floor_drifts[z] = max(drift_x, drift_y) > (0.004 * h_story)
            
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        
        el['pass'] = True
        el['design_details'] = {}
        el['failure_mode'] = "" 
        
        if el['type'] == 'Beam':
            Mu_y = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
            Mu_z = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
            Mu_max = max(Mu_y, Mu_z)
            Vu_y = max(abs(el['F_internal'][1]), abs(el['F_internal'][7]))
            Vu_z = max(abs(el['F_internal'][2]), abs(el['F_internal'][8]))
            Vu_max = max(Vu_y, Vu_z)
            
            d_beam = h - 40 
            Mu_lim = mulim_coeff * fck * b * (d_beam**2) / 1e6
            tau_v = (Vu_max * 1000) / (b * d_beam)
            
            L_mm = el['length'] * 1000
            w_load = el.get('load_kN_m', 0.0)
            delta_ss = (5 * w_load * 1000 * (el['length']**4)) / (384 * el['E'] * el['Iz']) * 1000 if (el.get('E',0)*el.get('Iz',0)) != 0 else 0
            
            theta_1, theta_2 = el.get('u_local', np.zeros(12))[5], el.get('u_local', np.zeros(12))[11]
            delta_rot = abs((L_mm / 8) * (theta_1 - theta_2))
            max_deflection = delta_ss + delta_rot
            
            if max_deflection > (L_mm / 250): el['failure_mode'] += "deflection "
            if Mu_max > Mu_lim: el['failure_mode'] += "flexure "
            if tau_v > tau_c_max: el['failure_mode'] += "shear "
                
            if el['failure_mode']:
                el['pass'] = False; design_status = False
                
            el['design_details'] = {
                'ID': el['id'], 'Flr': el['floor'], 'Size (mm)': el['size'],
                'Mu(kN.m)': round(Mu_max, 2), 'Vu(kN)': round(Vu_max, 2),
                'τv(MPa)': round(tau_v, 2), 'Defl(mm)': round(max_deflection, 2), 
                'Status': 'Safe' if el['pass'] else el['failure_mode'].strip()
            }
                
        elif el['type'] == 'Column':
            Pu = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
            Mu_y = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
            Mu_z = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
            Mu_max = max(Mu_y, Mu_z)
            
            Ag = b * h
            d_col = h - 40
            
            Pu_crushing_limit = (0.4 * fck * Ag + 0.67 * fy * 0.04 * Ag) / 1000.0 
            Asc_req_axial = (Pu * 1000 - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck) if (Pu * 1000 > 0.4 * fck * Ag) else 0
            Asc_req_mom = (Mu_max * 1e6) / (0.87 * fy * 0.8 * d_col) if Mu_max > 0 else 0
            Asc_calc = Asc_req_axial + Asc_req_mom
            
            if floor_drifts.get(el['floor'], False): el['failure_mode'] += "drift "
            if Pu > Pu_crushing_limit: el['failure_mode'] += "axial_crushing "
            elif Asc_calc > 0.04 * Ag: el['failure_mode'] += "steel_limit "
                
            if el['failure_mode']:
                el['pass'] = False; design_status = False
                    
            el['design_details'] = {
                'ID': el['id'], 'Flr': el['floor'], 'Size (mm)': el['size'],
                'Orient': f"{el.get('angle', 0)}°", 'Pu(kN)': round(Pu, 2), 'Mu(kN.m)': round(Mu_max, 2),
                'Req Asc(mm²)': round(max(Asc_calc, 0.008 * Ag), 2),
                'Status': 'Safe' if el['pass'] else el['failure_mode'].strip()
            }
                    
    return elements_to_design, design_status

# --- CALCULATION BOQ ---
def get_boq(elements_list, slab_thick, area):
    total_conc, total_steel = 0, 0
    for z in range(num_stories + 1):
        for el in [e for e in elements_list if e['floor'] == z]:
            b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
            vol = b * h * el['length']
            total_conc += vol
            total_steel += vol * 7850 * (0.015 if el['type'] == 'Column' else 0.012)
        if z > 0:
            slab_vol = area * (slab_thick/1000)
            total_conc += slab_vol
            total_steel += slab_vol * 7850 * 0.008
    return total_conc, total_steel

# --- EXECUTION BLOCK ---
if st.button("Run Full Analysis & Deep AI Optimization", type="primary", width="stretch"):
    with st.spinner("Processing Structural Engine..."):
        if len(nodes) < 2:
            st.error("Not enough valid nodes. Please check grid geometry.")
            st.stop()
            
        # 1. SMART SLAB DESIGN
        x_coords, y_coords = sorted(list(x_map.values())), sorted(list(y_map.values()))
        x_spans = [x_coords[i+1] - x_coords[i] for i in range(len(x_coords)-1) if (x_coords[i+1] - x_coords[i]) > 0.5]
        y_spans = [y_coords[i+1] - y_coords[i] for i in range(len(y_coords)-1) if (y_coords[i+1] - y_coords[i]) > 0.5]
        Lx, Ly = min(max(x_spans) if x_spans else 1.0, max(y_spans) if y_spans else 1.0), max(max(x_spans) if x_spans else 1.0, max(y_spans) if y_spans else 1.0)
        
        ratio = Ly / Lx
        slab_behavior = "One-Way" if ratio > 2.0 else "Two-Way"
        alpha_x = np.interp(ratio, [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0], [0.062, 0.074, 0.084, 0.093, 0.099, 0.104, 0.113, 0.118]) if slab_behavior == "Two-Way" else 0.125
        R_max = 0.133 * fck if fy >= 500 else 0.138 * fck
        
        # Manual Slab Status
        w_u_man = 1.5 * (live_load + floor_finish + (slab_thickness / 1000.0) * 25.0)
        Mu_man = alpha_x * w_u_man * (Lx**2)
        req_d_flex = math.sqrt((Mu_man * 1e6) / (R_max * 1000))
        req_d_def = (Lx * 1000) / 28.0 
        man_slab_status = "Safe" if slab_thickness >= max(req_d_flex, req_d_def) + 25 else "Fail (Deflect/Flexure)"
        
        # AI Slab Status
        opt_slab_thickness = slab_thickness
        slab_Ast = 0.0
        for _ in range(10):
            w_u = 1.5 * (live_load + floor_finish + (opt_slab_thickness / 1000.0) * 25.0)
            slab_Mu = alpha_x * w_u * (Lx**2)
            d_req_flex = math.sqrt((slab_Mu * 1e6) / (R_max * 1000))
            if opt_slab_thickness >= max((Lx * 1000)/28.0, d_req_flex) + 25: break
            opt_slab_thickness += 10
            
        # 2. RUN MANUAL DESIGN CHECK
        try:
            manual_elements = copy.deepcopy(elements)
            manual_elements, U_man = run_analysis_dynamic(manual_elements, nodes, slab_thickness)
            manual_elements, man_passed = perform_design(manual_elements, U_man, nodes, z_elevations)
        except Exception as e:
            st.error(f"Manual Model Failed: {e}")
            st.stop()
             except Exception as e:
            st.error(f"Manual design failed: {e}")
            st.stop()

        # 3. RUN OPTIMIZED DESIGN CHECK
        try:
            optimized_elements = copy.deepcopy(elements)
            optimized_elements, U_opt = run_analysis_dynamic(
                optimized_elements, nodes, opt_slab_thickness
            )
            optimized_elements, opt_passed = perform_design(
                optimized_elements, U_opt, nodes, z_elevations
            )
        except Exception as e:
            st.error(f"Optimized design failed: {e}")
            st.stop()

        # ---------------------------------------------------
        # RESULTS DISPLAY
        # ---------------------------------------------------

        st.success("✅ Analysis Completed Successfully")

        col1, col2 = st.columns(2)

        # ---------- SLAB RESULT ----------
        with col1:
            st.subheader("Manual Slab Check (IS 456)")
            st.write(f"Behavior : **{slab_behavior} Slab**")
            st.write(f"Thickness Provided : **{slab_thickness} mm**")
            st.write(f"Status : **{man_slab_status}**")

        with col2:
            st.subheader("AI Optimized Slab")
            st.write(f"Optimized Thickness : **{opt_slab_thickness} mm**")
            st.write(
                "Status : ✅ Safe"
                if opt_passed
                else "❌ Needs Further Optimization"
            )

        # ---------- DESIGN TABLES ----------
        beam_results = [
            el["design_details"]
            for el in optimized_elements
            if el["type"] == "Beam"
        ]

        column_results = [
            el["design_details"]
            for el in optimized_elements
            if el["type"] == "Column"
        ]

        st.subheader("Beam Design Results (IS 456)")
        if beam_results:
            st.dataframe(pd.DataFrame(beam_results), use_container_width=True)

        st.subheader("Column Design Results (IS 456)")
        if column_results:
            st.dataframe(pd.DataFrame(column_results), use_container_width=True)

        # ---------- BOQ ----------
        X_coords = [n["x"] for n in nodes]
        Y_coords = [n["y"] for n in nodes]
        area = (
            (max(X_coords) - min(X_coords))
            * (max(Y_coords) - min(Y_coords))
            * 0.85
        )

        conc, steel = get_boq(
            optimized_elements,
            opt_slab_thickness,
            area,
        )

        st.subheader("📊 Quantity Takeoff (BOQ)")

        boq_df = pd.DataFrame(
            {
                "Item": ["Concrete Volume", "Steel Weight"],
                "Quantity": [round(conc, 2), round(steel / 1000, 2)],
                "Unit": ["m³", "Tonnes"],
            }
        )

        st.table(boq_df)

        # ---------- DEFORMED SHAPE ----------
        scale = 50
        deformed_nodes = copy.deepcopy(nodes)

        for n in deformed_nodes:
            n["x"] += U_opt[n["id"] * 6] * scale
            n["y"] += U_opt[n["id"] * 6 + 1] * scale
            n["z"] += U_opt[n["id"] * 6 + 2] * scale

        render_viewport(
            deformed_nodes,
            optimized_elements,
            "Deformed Shape (Scaled View)",
            "def",
        )
            
        # 3. RUN AI OPTIMIZATION LOOP
        ai_elements = copy.deepcopy(elements)
        ai_passed = False
        iteration = 1
        
        while iteration <= 15:
            ai_elements, U_ai = run_analysis_dynamic(ai_elements, nodes, opt_slab_thickness)
            ai_elements, ai_passed = perform_design(ai_elements, U_ai, nodes, z_elevations)
            if ai_passed: break
            
            for el in ai_elements:
                if not el['pass']:
                    b, h = map(int, el['size'].split('x'))
                    mode = el.get('failure_mode', '')
                    
                    if el['type'] == 'Beam':
                        if 'shear' in mode or 'deflection' in mode: h += 50
                        elif 'flexure' in mode: h += 50 
                        if h / b > 3.0: b += 50 
                    else: 
                        if 'drift' in mode or 'axial_crushing' in mode: b += 50; h += 50
                        elif 'steel_limit' in mode: h += 50
                        if h - b > 200: b += 50 
                    
                    b, h = min(b, 1000), min(h, 1200)
                    el['size'] = f"{b}x{h}"
            iteration += 1

        # --- RENDER RESULTS IN TABS ---
        st.success("Analysis Complete!")
        tab_man, tab_ai = st.tabs(["📝 Manual Design Results", "🤖 AI Optimized Design"])
        approx_floor_area = (max(x_coords) - min(x_coords)) * (max(y_coords) - min(y_coords)) * 0.85 if x_coords else 0

        with tab_man:
            if man_passed and man_slab_status == "Safe": st.success("Your Manual Design strictly passes all IS Codes.")
            else: st.error("Manual Design Fails IS Code constraints. Review detailed failures below.")
            
            st.subheader(f"Slab Status: {man_slab_status} (Provided {slab_thickness}mm)")
            
            col_b, col_c = st.columns(2)
            col_b.dataframe(pd.DataFrame([el['design_details'] for el in manual_elements if el['type'] == 'Beam']), width="stretch")
            col_c.dataframe(pd.DataFrame([el['design_details'] for el in manual_elements if el['type'] == 'Column']), width="stretch")

        with tab_ai:
            st.subheader(f"AI Selected Slab: {opt_slab_thickness} mm (Status: Safe)")
            
            if ai_passed: st.success(f"AI successfully optimized the structure in {iteration} iterations.")
            else: st.warning("AI reached max geometric limits but could not completely stabilize the structure.")
            
            mc, ms = get_boq(manual_elements, slab_thickness, approx_floor_area)
            ac, as_stl = get_boq(ai_elements, opt_slab_thickness, approx_floor_area)
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Concrete Variance", f"{ac:.1f} m³", delta=f"{(ac-mc):.1f} m³ vs Manual", delta_color="inverse")
            c2.metric("Steel Variance", f"{(as_stl/1000):.1f} MT", delta=f"{((as_stl-ms)/1000):.1f} MT vs Manual", delta_color="inverse")
            
            col_b2, col_c2 = st.columns(2)
            col_b2.dataframe(pd.DataFrame([el['design_details'] for el in ai_elements if el['type'] == 'Beam']), width="stretch")
            col_c2.dataframe(pd.DataFrame([el['design_details'] for el in ai_elements if el['type'] == 'Column']), width="stretch")
