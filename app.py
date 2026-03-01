import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd
import json

# --- PAGE SETUP ---
st.set_page_config(page_title="IS Code Compliant 3D Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & IS-Code Auto-Design")
st.caption("Strict Compliance: IS 456, IS 875, IS 1893 (Dynamic Sa/g, Soft Storey, CoM Drift)")

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
        "col_dim": "230x450", "beam_dim": "230x400", "fck": 25.0, "fy": 500.0, 
        "sbc": 200.0, "live_load": 2.0, "floor_finish": 1.5, "wall_thickness": 230,
        "slab_thickness": 150, "zone": 0.16, "soil": 2, "I_factor": 1.0, "R_factor": 5.0
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
        for k, v in data.get("parameters", {}).items(): st.session_state.params[k] = v
        st.session_state.loaded_file = uploaded_file.name
        st.rerun() 
    except Exception as e:
        st.sidebar.error(f"Invalid JSON: {e}")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Floor Elevations")
floor_data = st.sidebar.data_editor(st.session_state.floors_df, num_rows="dynamic", use_container_width=True)

z_elevations = {0: 0.0}
current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

st.sidebar.header("2. Structural Grids")
x_grid_data = st.data_editor(st.session_state.x_grids_df, num_rows="dynamic", use_container_width=True)
y_grid_data = st.data_editor(st.session_state.y_grids_df, num_rows="dynamic", use_container_width=True)
x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

st.sidebar.header("3. Column Placement")
col_data = st.data_editor(st.session_state.cols_df, num_rows="dynamic", use_container_width=True)

st.sidebar.header("4. Design & Load Parameters")
col_dim = st.sidebar.text_input("Init Column Size (mm)", str(st.session_state.params["col_dim"]))
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", str(st.session_state.params["beam_dim"]))

col3, col4 = st.sidebar.columns(2)
fck = col3.number_input("fck (MPa)", value=float(st.session_state.params["fck"]), step=5.0)
fy = col4.number_input("fy (MPa)", value=float(st.session_state.params["fy"]), step=85.0)
sbc = col3.number_input("SBC (kN/m²)", value=float(st.session_state.params["sbc"]), step=10.0)

st.sidebar.subheader("IS 875 Gravity Loads")
live_load = st.sidebar.number_input("Live Load (kN/m²)", value=float(st.session_state.params["live_load"]))
floor_finish = st.sidebar.number_input("Floor Finish (kN/m²)", value=float(st.session_state.params["floor_finish"]))
wall_thickness = st.sidebar.number_input("Wall Thk (mm)", value=int(st.session_state.params["wall_thickness"]))
slab_thickness = st.sidebar.number_input("Slab Thk (mm)", value=int(st.session_state.params["slab_thickness"]))

st.sidebar.subheader("IS 1893 Seismic Parameters")
z_factor = st.sidebar.selectbox("Seismic Zone (Z)", [0.10, 0.16, 0.24, 0.36], index=[0.10, 0.16, 0.24, 0.36].index(st.session_state.params["zone"]), format_func=lambda x: f"Zone {['II','III','IV','V'][[0.10, 0.16, 0.24, 0.36].index(x)]} (Z={x})")
soil_type = st.sidebar.selectbox("Soil Type", [1, 2, 3], index=st.session_state.params["soil"]-1, format_func=lambda x: ["I (Hard)", "II (Medium)", "III (Soft)"][x-1])
i_factor = st.sidebar.selectbox("Importance Factor (I)", [1.0, 1.2, 1.5], index=[1.0, 1.2, 1.5].index(st.session_state.params["I_factor"]))
r_factor = st.sidebar.selectbox("Response Reduction (R)", [3.0, 4.0, 5.0], index=[3.0, 4.0, 5.0].index(st.session_state.params["R_factor"]), format_func=lambda x: f"SMRF (R=5)" if x==5.0 else f"OMRF (R=3)" if x==3.0 else str(x))

st.sidebar.header("5. AI Optimization")
auto_optimize = st.sidebar.checkbox("Enable IS 456 Auto-Sizing", value=True)
allow_ai_restructure = st.sidebar.checkbox("Allow AI Restructuring (3-Stage)", value=True)

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError): return default

# --- GEOMETRY BUILDER ---
def build_geometry(primary_pts, secondary_pts, z_dict, n_stories, c_dim, b_dim):
    gen_nodes, gen_elements, nid, eid = [], [], 0, 0
    for floor_idx in range(n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in primary_pts:
            gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': pt.get('angle', 0), 'is_primary': True}); nid += 1
    for floor_idx in range(1, n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in secondary_pts:
            if pt['floor'] == floor_idx:
                gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': 0, 'is_primary': False}); nid += 1

    for z in range(n_stories):
        bottom_nodes = [n for n in gen_nodes if n['floor'] == z and n.get('is_primary', True)]
        top_nodes = [n for n in gen_nodes if n['floor'] == z + 1 and n.get('is_primary', True)]
        for bn in bottom_nodes:
            tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
            if tn:
                gen_elements.append({'id': eid, 'ni': bn['id'], 'nj': tn['id'], 'type': 'Column', 'floor': z, 'size': c_dim, 'angle': bn['angle']}); eid += 1
                
    tolerance = 0.05 
    for z in range(1, n_stories + 1):
        floor_nodes = [n for n in gen_nodes if n['floor'] == z]
        y_groups, x_groups = {}, {}
        for n in floor_nodes:
            matched = False
            for y_key in y_groups.keys():
                if abs(n['y'] - y_key) <= tolerance: y_groups[y_key].append(n); matched = True; break
            if not matched: y_groups[n['y']] = [n]
        for y_key, group in y_groups.items():
            group = sorted(group, key=lambda k: k['x'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0}); eid += 1
                
        for n in floor_nodes:
            matched = False
            for x_key in x_groups.keys():
                if abs(n['x'] - x_key) <= tolerance: x_groups[x_key].append(n); matched = True; break
            if not matched: x_groups[n['x']] = [n]
        for x_key, group in x_groups.items():
            group = sorted(group, key=lambda k: k['y'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0}); eid += 1
                
    return gen_nodes, gen_elements

primary_xy = []
for idx, row in col_data.iterrows():
    xg, yg = str(row.get('X_Grid', '')).strip(), str(row.get('Y_Grid', '')).strip()
    if xg in x_map and yg in y_map:
        primary_xy.append({'x': x_map[xg] + safe_float(row.get('X_Offset (m)')), 'y': y_map[yg] + safe_float(row.get('Y_Offset (m)')), 'angle': safe_float(row.get('Angle (deg)'))})

nodes, elements = build_geometry(primary_xy, [], z_elevations, num_stories, col_dim, beam_dim)

# --- MATRICES ---
def get_transformation_matrix(ni, nj):
    dx, dy, dz = nj['x'] - ni['x'], nj['y'] - ni['y'], nj['z'] - ni['z']
    L = math.sqrt(dx**2 + dy**2 + dz**2)
    cx, cy, cz = dx/L, dy/L, dz/L
    lam = np.zeros((3, 3))
    if abs(cx) < 1e-6 and abs(cy) < 1e-6: lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
    else: lam = np.array([[cx, cy, cz], [-cx*cz/math.sqrt(cx**2+cy**2), -cy*cz/math.sqrt(cx**2+cy**2), math.sqrt(cx**2+cy**2)], [-cy/math.sqrt(cx**2+cy**2), cx/math.sqrt(cx**2+cy**2), 0]])
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
    if num_nodes == 0: return current_elements, np.zeros(0), {}
    
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3 
    
    X_coords, Y_coords = [n['x'] for n in current_nodes], [n['y'] for n in current_nodes]
    dx = (max(X_coords) - min(X_coords)) if len(X_coords)>0 else 1.0
    dy = (max(Y_coords) - min(Y_coords)) if len(Y_coords)>0 else 1.0
    floor_area = dx * dy * 0.85
    
    total_dl_per_m2 = ((optimized_slab_D / 1000.0) * 25.0) + floor_finish
    total_floor_dl = floor_area * total_dl_per_m2
    total_floor_ll = floor_area * live_load
    total_beam_len = sum([math.sqrt((next(n for n in current_nodes if n['id'] == el['nj'])['x']-next(n for n in current_nodes if n['id'] == el['ni'])['x'])**2 + (next(n for n in current_nodes if n['id'] == el['nj'])['y']-next(n for n in current_nodes if n['id'] == el['ni'])['y'])**2) for el in current_elements if el['type'] == 'Beam']) or 1.0

    seismic_weight_total = 0.0
    seismic_mass_per_floor = total_floor_dl + ((0.25 if live_load <= 3.0 else 0.50) * total_floor_ll)

    # --- IS 1893 TIME PERIOD & Sa/g ---
    Ta_x = 0.09 * z_elevations[num_stories] / math.sqrt(dx)
    def get_sag(T, soil):
        if soil == 1: return 1+15*T if T<=0.1 else 2.5 if T<=0.4 else 1.0/T
        elif soil == 2: return 1+15*T if T<=0.1 else 2.5 if T<=0.55 else 1.36/T
        else: return 1+15*T if T<=0.1 else 2.5 if T<=0.67 else 1.67/T
    
    Ah_x = (z_factor / 2.0) * (i_factor / r_factor) * get_sag(Ta_x, soil_type)

    for el in current_elements:
        el['load_kN_m'] = 0.0
        if el['type'] == 'Beam':
            ni, nj = next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])
            L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
            el['length'] = L
            b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
            if el.get('angle', 0) == 90: b, h = h, b 
            
            is_secondary = not (ni.get('is_primary', True) and nj.get('is_primary', True))
            wall_udl = (wall_thickness / 1000.0) * 20.0 * max(0.1, (z_elevations.get(ni['floor'], 3.0) - z_elevations.get(ni['floor']-1, 0.0)) - h) if not is_secondary else 0.0

            self_wt = b * h * 25.0
            el['load_kN_m'] = 1.5 * ((total_floor_dl / total_beam_len) + (total_floor_ll / total_beam_len) + wall_udl + self_wt)
            seismic_weight_total += (wall_udl + self_wt) * L

    seismic_weight_total += (seismic_mass_per_floor * num_stories)
    V_base = Ah_x * seismic_weight_total # IS 1893 Base Shear
    
    floor_weights = {z: seismic_weight_total / num_stories for z in range(1, num_stories + 1)}
    sum_wh2 = sum([floor_weights[z] * (z_elevations[z]**2) for z in floor_weights])
    floor_forces = {z: V_base * (floor_weights[z] * (z_elevations[z]**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_weights}

    for n in current_nodes:
        if n['z'] > 0:
            nodes_this_floor = len([nd for nd in current_nodes if nd['floor'] == n['floor']])
            F_global[n['id'] * 6] += (floor_forces[n['floor']] / nodes_this_floor) if nodes_this_floor > 0 else 0

    floor_stiffness = {z: 0.0 for z in range(1, num_stories + 1)}
    K_global = np.zeros((num_nodes * 6, num_nodes * 6))
    
    for el in current_elements:
        ni_data, nj_data = next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        el['length'] = L
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
        A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
        dim_min, dim_max = min(b, h), max(b, h)
        J_sec = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))

        el['E'], el['Iz'] = E_conc, Iz_sec
        if el['type'] == 'Column': floor_stiffness[el['floor'] + 1] += (12 * E_conc * max(Iy_sec, Iz_sec)) / (L**3)

        T_matrix = get_transformation_matrix(ni_data, nj_data)
        k_local = get_local_stiffness(E_conc, E_conc/2.4, A_sec, Iy_sec, Iz_sec, J_sec, L)
        el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL = np.zeros(12)
            F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = V, M, V, -M
            P_global = np.dot(T_matrix.T, F_local_ENL)
            F_global[el['ni']*6 : el['ni']*6+6] -= P_global[0:6]
            F_global[el['nj']*6 : el['nj']*6+6] -= P_global[6:12]

        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        k_g = el['k_global']
        K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_g[0:6, 0:6]; K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_g[0:6, 6:12]
        K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_g[6:12, 0:6]; K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_g[6:12, 6:12]

    fixed_dofs = [dof for n in current_nodes if n['z'] == 0 for dof in range(n['id'] * 6, n['id'] * 6 + 6)]
    free_dofs = sorted(list(set(range(num_nodes * 6)) - set(fixed_dofs)))
    
    try: U_free = np.linalg.solve(K_global[np.ix_(free_dofs, free_dofs)], F_global[free_dofs])
    except np.linalg.LinAlgError: raise Exception("Matrix is singular. Frame unstable.")
        
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    for el in current_elements:
        u_local = np.dot(get_transformation_matrix(next(n for n in current_nodes if n['id'] == el['ni']), next(n for n in current_nodes if n['id'] == el['nj'])), np.concatenate((U_global[el['ni']*6:el['ni']*6+6], U_global[el['nj']*6:el['nj']*6+6])))
        el['u_local'] = u_local
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0: F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = (w*el['length'])/2.0, (w*el['length']**2)/12.0, (w*el['length'])/2.0, -(w*el['length']**2)/12.0
            
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        dim_min, dim_max = min(b, h), max(b, h)
        J_sec = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))
        el['F_internal'] = np.dot(get_local_stiffness(E_conc, E_conc/2.4, b*h, (b*h**3)/12.0, (h*b**3)/12.0, J_sec, el['length']), u_local) - F_local_ENL

    return current_elements, U_global, floor_stiffness

def perform_design(elements_to_design, U_global, current_nodes, z_elevations, floor_stiffness):
    design_status = True
    mulim_coeff = 0.133 if fy >= 500 else 0.138 
    tau_c_max = 0.62 * math.sqrt(fck) 
    
    # IS 1893 Center of Mass Drift & Soft Storey Logic
    floor_drifts = {}
    soft_storeys = []
    
    for z in range(1, num_stories + 1):
        if z < num_stories and floor_stiffness.get(z, 0) < 0.7 * floor_stiffness.get(z+1, 0): soft_storeys.append(z)
            
        nodes_z = [n for n in current_nodes if n['floor'] == z]
        nodes_prev = [n for n in current_nodes if n['floor'] == z - 1]
        
        avg_x_z = sum([U_global[n['id']*6] for n in nodes_z])/len(nodes_z) if nodes_z else 0
        avg_x_prev = sum([U_global[n['id']*6] for n in nodes_prev])/len(nodes_prev) if nodes_prev else 0
        drift_x = abs(avg_x_z - avg_x_prev)
        
        h_story = z_elevations.get(z, 3.0) - z_elevations.get(z-1, 0.0)
        floor_drifts[z] = True if drift_x > (0.004 * h_story) else False
            
    for el in elements_to_design:
        b_mm, h_mm = map(lambda x: float(x), el['size'].split('x'))
        if el.get('angle', 0) == 90: b_mm, h_mm = h_mm, b_mm 
        
        el['pass'] = True
        el['failure_mode'] = "" 
        
        if el['type'] == 'Beam':
            Mu_max = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]), abs(el['F_internal'][5]), abs(el['F_internal'][11]))
            Vu_max = max(abs(el['F_internal'][1]), abs(el['F_internal'][7]), abs(el['F_internal'][2]), abs(el['F_internal'][8]))
            
            d_beam = h_mm - 40 
            if Mu_max > (mulim_coeff * fck * b_mm * (d_beam**2) / 1e6): el['failure_mode'] += "flexure "
            
            A_quad, B_quad, C_quad = (0.87 * fy * fy) / (b_mm * d_beam * fck), -0.87 * fy * d_beam, Mu_max * 1e6
            disc = B_quad**2 - 4*A_quad*C_quad
            num_bars = max(2, math.ceil(max(min((-B_quad + math.sqrt(disc))/(2*A_quad), (-B_quad - math.sqrt(disc))/(2*A_quad)) if disc >=0 else 0, (0.85 * b_mm * d_beam) / fy) / (math.pi * 16**2 / 4)))
            
            tau_v = (Vu_max * 1000) / (b_mm * d_beam)
            if tau_v > tau_c_max: el['failure_mode'] += "shear "
            
            delta_ss_m = (5 * el.get('load_kN_m', 0.0) * (el['length']**4)) / (384 * el['E'] * el['Iz']) if (el.get('E',0)*el.get('Iz',0)) != 0 else 0
            max_deflection = abs(delta_ss_m * 1000) + abs(((el['length'] / 8) * (el.get('u_local', np.zeros(12))[5] - el.get('u_local', np.zeros(12))[11])) * 1000)
            if max_deflection > (el['length'] * 1000 / 250): el['failure_mode'] += "deflection "
                
            if el['failure_mode']: el['pass'], design_status = False, False
                
            el['design_details'] = {
                'ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'], 'Mu_max (kN.m)': round(Mu_max, 2), 
                'Vu_max (kN)': round(Vu_max, 2), 'Bottom Rebars': f"{num_bars}-16Φ" if not 'flexure' in el['failure_mode'] else "FAIL", 
                'Status': 'Safe' if el['pass'] else el['failure_mode'].strip()
            }
                
        elif el['type'] == 'Column':
            Pu = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
            Mu_y = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]), Pu * max(el['length']*1000 / 500 + h_mm / 30, 20.0) / 1000.0)
            Mu_z = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]), Pu * max(el['length']*1000 / 500 + b_mm / 30, 20.0) / 1000.0)
            
            is_slender_z, is_slender_y = (el['length']*1000 / b_mm) > 12, (el['length']*1000 / h_mm) > 12
            if is_slender_z: Mu_z += (Pu * b_mm / 2000.0) * (el['length']*1000 / b_mm)**2 / 1000.0; el['failure_mode'] += "slender_z "
            if is_slender_y: Mu_y += (Pu * h_mm / 2000.0) * (el['length']*1000 / h_mm)**2 / 1000.0; el['failure_mode'] += "slender_y "

            Ag = b_mm * h_mm
            Asc_calc = (Pu * 1000 - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck) if (Pu * 1000 > 0.4 * fck * Ag) else 0 + (max(Mu_y, Mu_z) * 1e6) / (0.87 * fy * 0.8 * (h_mm - 40)) if max(Mu_y, Mu_z) > 0 else 0
            
            if floor_drifts.get(el['floor'], False) or el['floor'] in soft_storeys: el['failure_mode'] += "drift/soft_storey "; el['pass'], design_status = False, False
            if Pu > (0.4 * fck * Ag + 0.67 * fy * 0.04 * Ag) / 1000.0: el['failure_mode'] += "axial_crush "; el['pass'], design_status = False, False
            elif Asc_calc > 0.04 * Ag: el['failure_mode'] += "steel_limit "; el['pass'], design_status = False, False
                    
            el['design_details'] = {
                'ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'], 'Orientation': f"{el.get('angle', 0)}°", 
                'Pu_max (kN)': round(Pu, 2), 'Req Asc (mm²)': round(max(Asc_calc, 0.008 * Ag), 2),
                'Status': 'Safe (Slender)' if (is_slender_y or is_slender_z) and el['pass'] else 'Safe' if el['pass'] else el['failure_mode'].strip()
            }
                    
    return elements_to_design, design_status

if st.button("Run 3-Stage AI Optimization & Design", type="primary", use_container_width=True):
    with st.spinner("Executing IS 1893 Spectral Analysis & Optimization..."):
        if len(nodes) < 2: st.error("Not enough nodes."); st.stop()
        
        opt_slab_thickness = slab_thickness
        passed_phase1, iteration, max_iters = False, 1, 12 
        
        while iteration <= max_iters:
            try:
                elements, U_global_res, floor_stiff = run_analysis_dynamic(elements, nodes, opt_slab_thickness)
                elements, passed_phase1 = perform_design(elements, U_global_res, nodes, z_elevations, floor_stiff)
                
                if passed_phase1 or not auto_optimize:
                    if passed_phase1: st.success(f"✅ Phase 1: Topology achieved 100% Safe Design in {iteration} iteration(s).")
                    break
                else:
                    for el in elements:
                        if not el['pass']:
                            b, h = map(int, el['size'].split('x'))
                            if el['type'] == 'Beam': b, h = (b, h+50) if 'flexure' in el['failure_mode'] else (b+50, h+50)
                            else: b, h = (b+50, h) if 'slender_z' in el['failure_mode'] else (b, h+50) if 'slender_y' in el['failure_mode'] else (b+50, h+50)
                            el['size'] = f"{min(b, 1000)}x{min(h, 1200)}"
                    iteration += 1
            except Exception as e: st.error(f"Solver Error: {e}"); st.stop()

        if not passed_phase1 and allow_ai_restructure:
            st.warning("⚠️ Phase 1 limits reached. Injecting Secondary Beams...")
            added_sec = 0
            for el in elements:
                if el['type'] == 'Beam' and not el['pass'] and el['length'] > 4.5:
                    ni, nj = next(n for n in nodes if n['id'] == el['ni']), next(n for n in nodes if n['id'] == el['nj'])
                    mx, my = (ni['x'] + nj['x'])/2.0, (ni['y'] + nj['y'])/2.0
                    if not any(math.sqrt((p['x']-mx)**2 + (p['y']-my)**2) < 1.0 for p in secondary_xy if p['floor'] == ni['floor']):
                        secondary_xy.append({'x': mx, 'y': my, 'floor': ni['floor']}); added_sec += 1
            if added_sec > 0:
                ai_nodes, ai_elements = build_geometry(primary_xy, secondary_xy, z_elevations, num_stories, col_dim, beam_dim)
                for _ in range(10): 
                    ai_elements, U_global_res, floor_stiff = run_analysis_dynamic(ai_elements, ai_nodes, opt_slab_thickness)
                    ai_elements, passed_phase2 = perform_design(ai_elements, U_global_res, ai_nodes, z_elevations, floor_stiff)
                    if passed_phase2: nodes, elements = ai_nodes, ai_elements; break
                    for el in ai_elements:
                        if not el['pass']: el['size'] = f"{min(int(el['size'].split('x')[0])+50, 1000)}x{min(int(el['size'].split('x')[1])+50, 1200)}"
                if not passed_phase2: nodes, elements = ai_nodes, ai_elements 

        st.divider()
        tab1, tab2 = st.tabs(["Beams Schedule", "Columns Schedule"])
        tab1.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam']), use_container_width=True)
        tab2.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column']), use_container_width=True)
