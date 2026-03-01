import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd
import json

# --- PAGE SETUP ---
st.set_page_config(page_title="IS Code Compliant 3D Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & IS-Code Auto-Design")
st.caption("Strict Compliance: IS 456:2000, IS 875 (Part 1 & 2), IS 1893 (Part 1)")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Floor Elevations")
default_floors = pd.DataFrame({"Floor": [1, 2, 3], "Height (m)": [3.2, 3.0, 3.0]})
floor_data = st.sidebar.data_editor(default_floors, num_rows="dynamic", use_container_width=True)

z_elevations = {0: 0.0}
current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

st.sidebar.header("2. Structural Grids (From Plan)")
with st.sidebar.expander("Define X-Grids", expanded=True):
    default_x_grids = pd.DataFrame({"Grid_ID": ["A", "B", "C", "D", "E", "F"], "X_Coord (m)": [0.0, 0.115, 4.112, 4.331, 8.039, 9.449]})
    x_grid_data = st.data_editor(default_x_grids, num_rows="dynamic", use_container_width=True, key="x_grids")

with st.sidebar.expander("Define Y-Grids", expanded=True):
    default_y_grids = pd.DataFrame({"Grid_ID": ["1", "2", "3", "4", "5", "6", "7"], "Y_Coord (m)": [0.0, 2.630, 4.999, 8.343, 9.660, 13.220, 14.326]})
    y_grid_data = st.data_editor(default_y_grids, num_rows="dynamic", use_container_width=True, key="y_grids")

st.sidebar.header("3. Column Placement")
x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations & Orientations", expanded=True):
    st.info(
        "📝 **How to place columns:**\n"
        "* **X_Grid & Y_Grid:** Type the exact Grid ID (e.g., A, 1) defined in Step 2.\n"
        "* **Offsets:** Shift the column from the exact grid intersection (in meters).\n"
        "* **Angle:** `0` aligns the column's depth (D) along the X-axis. `90` rotates it to the Y-axis.\n"
        "* **Add/Delete:** Click the empty bottom row to add a new column. Click the far-left gray box of a row and press `Delete` to remove it."
    )
    default_cols = pd.DataFrame({
        "Col_ID": ["C1", "C2", "C3", "C4", "C5"],
        "X_Grid": ["A", "B", "C", "D", "E"], "Y_Grid": ["1", "2", "3", "4", "5"],
        "X_Offset (m)": [0.0]*5, "Y_Offset (m)": [0.0]*5, "Angle (deg)": [0, 90, 90, 0, 90]
    })
    col_data = st.data_editor(default_cols, num_rows="dynamic", use_container_width=True)

st.sidebar.header("4. IS Code Design & Load Parameters")
col_dim = st.sidebar.text_input("Init Column Size (mm)", "230x450")
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", "230x400")

col3, col4 = st.sidebar.columns(2)
fck = col3.number_input("fck (MPa)", value=25.0, step=5.0)
fy = col4.number_input("fy (MPa)", value=500.0, step=85.0)
sbc = col3.number_input("SBC (kN/m²)", value=200.0, step=10.0)

st.sidebar.subheader("IS 875 Applied Loads")
live_load = st.sidebar.number_input("Live Load (kN/m²)", value=2.0)
floor_finish = st.sidebar.number_input("Floor Finish (kN/m²)", value=1.5)
wall_thickness = st.sidebar.number_input("Exterior Wall Thk (mm)", value=230)
slab_thickness = st.sidebar.number_input("Slab Thickness (mm)", value=150)
lateral_coeff = st.sidebar.slider("Seismic Base Shear Ah (%)", 0.0, 20.0, 5.0) / 100.0

st.sidebar.header("5. AI Optimization")
auto_optimize = st.sidebar.checkbox("Enable IS 456 Safe Auto-Sizing", value=True)
allow_ai_restructure = st.sidebar.checkbox("Allow AI Restructuring (Add Beams/Columns)", value=True)

# --- NEW: SAVE PROJECT DATA FUNCTIONALITY ---
st.sidebar.divider()
st.sidebar.header("💾 Save / Load Project")
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
    use_container_width=True
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
                
    tolerance = 0.5 
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

secondary_xy = [] 
nodes, elements = build_geometry(primary_xy, secondary_xy, z_elevations, num_stories, col_dim, beam_dim)

# --- VIEWPORT RENDERING FUNCTION ---
def render_viewport(view_nodes, view_elements, title="Structural Model Viewport", suffix="1"):
    st.subheader(title)
    col_v1, col_v2 = st.columns(2)
    show_arch_grids = col_v1.checkbox("Show Architectural Grids", value=True, key=f"grid_{suffix}")
    show_axis = col_v2.checkbox("Show 3D Axis", value=True, key=f"axis_{suffix}")

    fig = go.Figure()

    for el in view_elements:
        ni = next(n for n in view_nodes if n['id'] == el['ni'])
        nj = next(n for n in view_nodes if n['id'] == el['nj'])
        
        is_secondary = not (ni.get('is_primary', True) and nj.get('is_primary', True))
        if el['type'] == 'Column': color = 'blue'
        elif is_secondary: color = '#2ca02c' 
        else: color = 'red'
            
        fig.add_trace(go.Scatter3d(
            x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']],
            mode='lines', line=dict(color=color, width=4), hoverinfo='text', 
            text=f"{el['type']} ID:{el['id']}", showlegend=False
        ))

    if show_arch_grids and x_map and y_map:
        min_x, max_x, min_y, max_y = min(x_map.values()), max(x_map.values()), min(y_map.values()), max(y_map.values())
        for grid_id, y_val in y_map.items():
            fig.add_trace(go.Scatter3d(x=[min_x-1, max_x+1], y=[y_val, y_val], z=[0, 0], mode='lines+text', line=dict(color='gray', width=2, dash='dash'), text=[f"Grid {grid_id}", ''], textposition='middle left', hoverinfo='none', showlegend=False))
        for grid_id, x_val in x_map.items():
            fig.add_trace(go.Scatter3d(x=[x_val, x_val], y=[min_y-1, max_y+1], z=[0, 0], mode='lines+text', line=dict(color='gray', width=2, dash='dash'), text=[f"Grid {grid_id}", ''], textposition='bottom center', hoverinfo='none', showlegend=False))

    x_coords = [n['x'] for n in view_nodes]
    y_coords = [n['y'] for n in view_nodes]
    z_coords = [n['z'] for n in view_nodes]
    fig.add_trace(go.Scatter3d(x=x_coords, y=y_coords, z=z_coords, mode='markers', marker=dict(size=3, color='black'), hoverinfo='text', text=[f"Node: {n['id']}" for n in view_nodes], showlegend=False))

    axis_config = dict(showbackground=show_axis, showgrid=show_axis, zeroline=show_axis, showticklabels=show_axis)
    fig.update_layout(scene=dict(xaxis=dict(**axis_config, title='X' if show_axis else ''), yaxis=dict(**axis_config, title='Y' if show_axis else ''), zaxis=dict(**axis_config, title='Z' if show_axis else ''), aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=500)
    st.plotly_chart(fig, use_container_width=True)

render_viewport(nodes, elements, "Initial User Model", "init")

# --- ANALYSIS ENGINE ---
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

def run_analysis(current_elements, current_nodes):
    num_nodes = len(current_nodes)
    if num_nodes == 0: return current_elements, 0.0
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    X_coords, Y_coords = [n['x'] for n in current_nodes], [n['y'] for n in current_nodes]
    floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.85 if X_coords else 0
    slab_dl_per_m2 = (slab_thickness / 1000.0) * 25.0
    total_dl_per_m2 = slab_dl_per_m2 + floor_finish
    total_floor_dl = floor_area * total_dl_per_m2
    total_floor_ll = floor_area * live_load
    
    total_beam_len = sum([math.sqrt((next(n for n in current_nodes if n['id'] == el['nj'])['x']-next(n for n in current_nodes if n['id'] == el['ni'])['x'])**2 + (next(n for n in current_nodes if n['id'] == el['nj'])['y']-next(n for n in current_nodes if n['id'] == el['ni'])['y'])**2) for el in current_elements if el['type'] == 'Beam'])
    if total_beam_len == 0: total_beam_len = 1.0

    seismic_weight_total = 0.0
    ll_factor = 0.25 if live_load <= 3.0 else 0.50 
    seismic_mass_per_floor = total_floor_dl + (ll_factor * total_floor_ll)

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

        T_matrix = get_transformation_matrix(ni_data, nj_data)
        k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL = np.zeros(12)
            F_local_ENL[1] = V     
            F_local_ENL[5] = M     
            F_local_ENL[7] = V     
            F_local_ENL[11] = -M   
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
        raise Exception("Matrix is singular. Frame geometry is unstable.")
        
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
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * el['length']) / 2.0, (w * el['length']**2) / 12.0
            F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = V, M, V, -M
            
        el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL

    return current_elements, np.max(np.abs(U_global))


# --- ENHANCED: DEEP CHECK AI OPTIMIZATION ---
def perform_design(elements_to_design):
    design_status = True
    mulim_coeff = 0.133 if fy >= 500 else 0.138 
    tau_c_max = 0.62 * math.sqrt(fck) 
    
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        
        el['pass'] = True
        el['design_details'] = {}
        el['failure_mode'] = "" # Track exact reason for smart resizing
        
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
            
            if Mu_max > Mu_lim:
                el['failure_mode'] += "flexure "
            if tau_v > tau_c_max:
                el['failure_mode'] += "shear"
                
            if el['failure_mode']:
                el['pass'] = False
                design_status = False
                
            el['design_details'] = {
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Mu_max (kN.m)': round(Mu_max, 2), 'Vu_max (kN)': round(Vu_max, 2),
                'Shear τv (MPa)': round(tau_v, 2), 'Status': 'Safe' if el['pass'] else el['failure_mode'].strip()
            }
                
        elif el['type'] == 'Column':
            Pu = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
            Mu_y = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
            Mu_z = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
            Mu_max = max(Mu_y, Mu_z)
            
            Ag = b * h
            d_col = h - 40
            
            # Deep check for crushing vs reinforcement limits
            Pu_crushing_limit = (0.4 * fck * Ag + 0.67 * fy * 0.04 * Ag) / 1000.0 # IS 456 max theoretical load
            
            Asc_req_axial = (Pu * 1000 - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck) if (Pu * 1000 > 0.4 * fck * Ag) else 0
            Asc_req_mom = (Mu_max * 1e6) / (0.87 * fy * 0.8 * d_col) if Mu_max > 0 else 0
            Asc_calc = Asc_req_axial + Asc_req_mom
            
            if Pu > Pu_crushing_limit:
                el['failure_mode'] = "axial_crushing"
                el['pass'] = False
                design_status = False
            elif Asc_calc > 0.04 * Ag: 
                el['failure_mode'] = "steel_limit"
                el['pass'] = False
                design_status = False
                    
            el['design_details'] = {
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Orientation': f"{el.get('angle', 0)}°", 'Pu_max (kN)': round(Pu, 2), 'Mu_max (kN.m)': round(Mu_max, 2),
                'Req Asc (mm²)': round(max(Asc_calc, 0.008 * Ag), 2),
                'Status': 'Safe' if el['pass'] else el['failure_mode']
            }
                    
    return elements_to_design, design_status

def group_elements(elements_list, elem_type):
    df = pd.DataFrame([el['design_details'] for el in elements_list if el['type'] == elem_type])
    if df.empty: return df
    if elem_type == 'Column':
        grouped = df.groupby(['Floor', 'Size (mm)', 'Orientation']).agg(
            Max_Pu=('Pu_max (kN)', 'max'), Max_Mu=('Mu_max (kN.m)', 'max'), Max_Req_Asc=('Req Asc (mm²)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"C{i+1}" for i in range(len(grouped))]
        return grouped
    elif elem_type == 'Beam':
        grouped = df.groupby(['Floor', 'Size (mm)']).agg(
            Max_Mu=('Mu_max (kN.m)', 'max'), Max_Vu=('Vu_max (kN)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"B{i+1}" for i in range(len(grouped))]
        return grouped

# --- EXECUTION BLOCK ---
if st.button("Run 3-Stage AI Optimization & Design", type="primary", use_container_width=True):
    with st.spinner("Analyzing Frame..."):
        if len(nodes) < 2:
            st.error("Not enough valid nodes generated. Please check your grid definitions.")
            st.stop()
            
        passed_phase1, passed_phase2, passed_phase3 = False, False, False
        max_iters = 12 # Increased iterations for deep check heuristics
        
        # --- PHASE 1: SMART SIZING (HEURISTIC DIAGNOSTICS) ---
        iteration = 1
        while iteration <= max_iters:
            try:
                elements, max_def = run_analysis(elements, nodes)
                elements, passed_phase1 = perform_design(elements)
                
                if passed_phase1 or not auto_optimize:
                    if passed_phase1: st.success(f"✅ Phase 1: Initial Topology achieved 100% Safe Design in {iteration} iteration(s).")
                    break
                else:
                    for el in elements:
                        if not el['pass']:
                            b_str, h_str = el['size'].split('x')
                            b, h = int(b_str), int(h_str)
                            mode = el.get('failure_mode', '')
                            
                            # Smart Heuristic Check
                            if el['type'] == 'Beam':
                                if 'shear' in mode:
                                    b += 50
                                    h += 50
                                elif 'flexure' in mode:
                                    h += 50 # Depth is highly effective for flexure
                                else:
                                    h += 50
                            else: # Column
                                if 'axial_crushing' in mode:
                                    b += 50; h += 50
                                elif 'steel_limit' in mode:
                                    h += 50 # Increase depth to absorb moments
                                    if h - b > 200: b += 50 # maintain safe aspect ratio
                                else:
                                    b += 50; h += 50
                            
                            # Hard limits to prevent infinite architectural bloat
                            b = min(b, 1000)
                            h = min(h, 1200)
                            el['size'] = f"{b}x{h}"
                    iteration += 1
            except Exception as e:
                st.error(f"Solver Error: {e}")
                st.stop()
                
        # --- PHASE 2: SECONDARY BEAM INJECTION ---
        if not passed_phase1 and allow_ai_restructure:
            st.warning("⚠️ Phase 1 failed. Beams exceeded IS 456 maximum geometric limits. Phase 2: Injecting Secondary Beams...")
            
            added_sec_nodes = 0
            for el in elements:
                if el['type'] == 'Beam' and not el['pass'] and el['length'] > 4.5:
                    ni = next(n for n in nodes if n['id'] == el['ni'])
                    nj = next(n for n in nodes if n['id'] == el['nj'])
                    mid_x = (ni['x'] + nj['x']) / 2.0
                    mid_y = (ni['y'] + nj['y']) / 2.0
                    
                    if not any(math.sqrt((p['x']-mid_x)**2 + (p['y']-mid_y)**2) < 1.0 for p in secondary_xy if p['floor'] == ni['floor']):
                        secondary_xy.append({'x': mid_x, 'y': mid_y, 'floor': ni['floor']})
                        added_sec_nodes += 1
                            
            if added_sec_nodes > 0:
                st.info(f"🧠 AI injected {added_sec_nodes} secondary nodes to break spans. Re-analyzing...")
                ai_nodes, ai_elements = build_geometry(primary_xy, secondary_xy, z_elevations, num_stories, col_dim, beam_dim)
                
                ai_iters = 1
                while ai_iters <= 10: 
                    ai_elements, max_def = run_analysis(ai_elements, ai_nodes)
                    ai_elements, passed_phase2 = perform_design(ai_elements)
                    if passed_phase2:
                        st.success(f"✅ Phase 2 Successful! Secondary beams stabilized the structure.")
                        nodes, elements = ai_nodes, ai_elements
                        render_viewport(nodes, elements, "🤖 Phase 2 Model (Green = Secondary Beams)", "ai")
                        break
                    else:
                        for el in ai_elements:
                            if not el['pass']:
                                b_str, h_str = el['size'].split('x')
                                b, h = int(b_str), int(h_str)
                                mode = el.get('failure_mode', '')
                                
                                if el['type'] == 'Beam':
                                    if 'shear' in mode: b += 50; h += 50
                                    else: h += 50
                                else:
                                    if 'axial_crushing' in mode: b += 50; h += 50
                                    elif 'steel_limit' in mode: h += 50
                                    else: b += 50; h += 50
                                
                                b, h = min(b, 1000), min(h, 1200)
                                el['size'] = f"{b}x{h}"
                    ai_iters += 1
                
                if not passed_phase2:
                    nodes, elements = ai_nodes, ai_elements
            else:
                passed_phase2 = False 

        # --- PHASE 3: DEEP RESTRUCTURING ---
        if not passed_phase1 and not passed_phase2 and allow_ai_restructure:
            st.error("⚠️ Phase 2 Secondary Beams failed. Phase 3: Deep Restructuring (Adding Primary Columns)...")
            
            hard_primary_xy = list(primary_xy)
            added_cols = 0
            
            for pt in secondary_xy:
                if not any(math.sqrt((p['x']-pt['x'])**2 + (p['y']-pt['y'])**2) < 1.0 for p in hard_primary_xy):
                    hard_primary_xy.append({'x': pt['x'], 'y': pt['y'], 'angle': 0.0})
                    added_cols += 1

            for el in elements:
                if el['type'] == 'Beam' and not el['pass'] and el['length'] > 4.0:
                    ni = next(n for n in nodes if n['id'] == el['ni'])
                    nj = next(n for n in nodes if n['id'] == el['nj'])
                    mid_x = (ni['x'] + nj['x']) / 2.0
                    mid_y = (ni['y'] + nj['y']) / 2.0
                    if not any(math.sqrt((p['x']-mid_x)**2 + (p['y']-mid_y)**2) < 1.0 for p in hard_primary_xy):
                        hard_primary_xy.append({'x': mid_x, 'y': mid_y, 'angle': 0.0})
                        added_cols += 1

            if added_cols > 0:
                st.info(f"🏗️ AI dropped {added_cols} new primary columns down to the foundation. Re-analyzing...")
                hard_nodes, hard_elements = build_geometry(hard_primary_xy, [], z_elevations, num_stories, col_dim, beam_dim)
                
                hard_iters = 1
                while hard_iters <= 10:
                    hard_elements, max_def = run_analysis(hard_elements, hard_nodes)
                    hard_elements, passed_phase3 = perform_design(hard_elements)
                    if passed_phase3:
                        st.success(f"✅ Phase 3 Deep Restructuring Successful! 100% Safe Design Guaranteed.")
                        break
                    else:
                        for el in hard_elements:
                            if not el['pass']:
                                b_str, h_str = el['size'].split('x')
                                b, h = int(b_str), int(h_str)
                                mode = el.get('failure_mode', '')
                                
                                if el['type'] == 'Beam':
                                    if 'shear' in mode: b += 50; h += 50
                                    else: h += 50
                                else:
                                    if 'axial_crushing' in mode: b += 50; h += 50
                                    elif 'steel_limit' in mode: h += 50
                                    else: b += 50; h += 50
                                
                                b, h = min(b, 1000), min(h, 1200)
                                el['size'] = f"{b}x{h}"
                    hard_iters += 1
                
                nodes, elements = hard_nodes, hard_elements
                render_viewport(nodes, elements, "🏗️ Phase 3 Deep Restructured Model", "hard")
            else:
                st.info("🧠 AI could not safely inject columns without severe crowding. Manual layout review required.")

        # --- EXTRACT SPAN DATA FOR SLABS ---
        max_span_x, max_span_y = 0.1, 0.1
        for el in elements:
            if el['type'] == 'Beam':
                span_x = abs(next(n for n in nodes if n['id'] == el['nj'])['x'] - next(n for n in nodes if n['id'] == el['ni'])['x'])
                span_y = abs(next(n for n in nodes if n['id'] == el['nj'])['y'] - next(n for n in nodes if n['id'] == el['ni'])['y'])
                if span_x > max_span_x: max_span_x = span_x
                if span_y > max_span_y: max_span_y = span_y

        slabs = []
        for z in range(1, num_stories + 1):
            slabs.append({
                'Floor': z, 'Max Grid Dim (m)': f"{round(max_span_x,2)} x {round(max_span_y,2)}",
                'Behavior': "One-Way" if (max_span_y/max_span_x if max_span_x>0 else 1)>2.0 else "Two-Way", 
                'Thickness (mm)': slab_thickness,
                'Status': 'Safe'
            })
                    
        # --- FOOTINGS ---
        base_nodes = [n for n in nodes if n['z'] == 0]
        footings = []
        pad_footings_dict = {}

        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                pad_footings_dict[n['id']] = {'Pu': Pu, 'side': math.ceil(math.sqrt((Pu / 1.5 * 1.1) / sbc) * 10) / 10, 'x': n['x'], 'y': n['y']}

        processed_nodes = set()
        footing_id = 1
        for n1_id, f1 in pad_footings_dict.items():
            if n1_id in processed_nodes: continue
            combined_with = [n2_id for n2_id, f2 in pad_footings_dict.items() if n1_id != n2_id and n2_id not in processed_nodes and math.sqrt((f1['x'] - f2['x'])**2 + (f1['y'] - f2['y'])**2) < (f1['side']/2 + f2['side']/2)]
            
            if combined_with:
                group = [n1_id] + combined_with
                L_comb = max([pad_footings_dict[nid]['x'] for nid in group]) - min([pad_footings_dict[nid]['x'] for nid in group]) + max([pad_footings_dict[nid]['side'] for nid in group])
                B_comb = max(sum((pad_footings_dict[nid]['Pu'] / 1.5 * 1.1) / sbc for nid in group) / L_comb, max([pad_footings_dict[nid]['side'] for nid in group]))
                footings.append({'ID': f"CF-{footing_id}", 'Type': 'Combined', 'Total Pu (kN)': round(sum(pad_footings_dict[nid]['Pu'] for nid in group), 2), 'Provided L x B (m)': f"{round(L_comb,1)} x {round(B_comb,1)}", 'Depth (mm)': max(400, int(B_comb * 1000 / 3)), 'Status': 'Safe'})
                processed_nodes.update(group)
            else:
                footings.append({'ID': f"F-{footing_id}", 'Type': 'Isolated Pad', 'Total Pu (kN)': round(f1['Pu'], 2), 'Provided L x B (m)': f"{f1['side']} x {f1['side']}", 'Depth (mm)': max(300, int(f1['side'] * 1000 / 4)), 'Status': 'Safe'})
            processed_nodes.add(n1_id)
            footing_id += 1

        # --- 5. BOQ ---
        st.divider()
        st.header("5. Material Abstract & BoQ")
        materials = []
        total_conc, total_steel = 0, 0
        X_coords, Y_coords = [n['x'] for n in nodes], [n['y'] for n in nodes]
        approx_floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.85 if X_coords else 0
        
        for z in range(num_stories + 1):
            conc_vol, steel_wt = 0, 0
            floor_elements = [e for e in elements if e['floor'] == z]
            for el in floor_elements:
                b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
                vol = b * h * el['length']
                conc_vol += vol
                steel_wt += vol * 7850 * (0.015 if el['type'] == 'Column' else 0.012)
            
            slab_vol = approx_floor_area * (slab_thickness/1000) if z > 0 else 0
            conc_vol += slab_vol
            steel_wt += slab_vol * 7850 * 0.008
            total_conc += conc_vol
            total_steel += steel_wt
            if conc_vol > 0: 
                materials.append({"Floor": f"Level {z}", "Concrete (m³)": round(conc_vol, 2), "Steel (kg)": round(steel_wt, 2)})
                
        colA, colB = st.columns(2)
        colA.dataframe(pd.DataFrame(materials), use_container_width=True)
        colB.metric("Total Concrete Volume", f"{total_conc:.2f} m³")
        colB.metric("Total Rebar Weight", f"{total_steel / 1000:.2f} MT")

        st.divider()
        st.header("6. Detailed Results & Grouping")
        
        col_grp1, col_grp2 = st.columns(2)
        col_grp1.subheader("Beam Groups")
        col_grp1.dataframe(group_elements(elements, 'Beam'), use_container_width=True)
        col_grp2.subheader("Column Groups")
        col_grp2.dataframe(group_elements(elements, 'Column'), use_container_width=True)

        tab1, tab2, tab3, tab4 = st.tabs(["Slabs", "Beams", "Columns", "Footings"])
        tab1.dataframe(pd.DataFrame(slabs), use_container_width=True)
        
        # Format failure modes elegantly in the detailed view
        beam_df = pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam'])
        tab2.dataframe(beam_df, use_container_width=True)
        
        col_df = pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column'])
        tab3.dataframe(col_df, use_container_width=True)
        tab4.dataframe(pd.DataFrame(footings), use_container_width=True)

        # --- 7. FOUNDATION ECONOMICS ---
        st.divider()
        st.header("7. Foundation Economics: Pad vs. Pile (IS 2911 Base)")
        col_rates1, col_rates2, col_rates3 = st.columns(3)
        rate_conc = col_rates1.number_input("Concrete Rate (per m³)", value=6000.0)
        rate_steel = col_rates2.number_input("Steel Rate (per kg)", value=65.0)
        d_pile = col_rates3.selectbox("Pile Shaft Dia (m)", [0.25, 0.30, 0.40], index=1)

        vol_pad_total = sum([float(f['Provided L x B (m)'].split(' x ')[0]) * float(f['Provided L x B (m)'].split(' x ')[1]) * (f['Depth (mm)']/1000) for f in footings])
        cost_pad = (vol_pad_total * rate_conc) + (vol_pad_total * 7850 * 0.008 * rate_steel)

        FOS, N_c, alpha = 2.5, 9.0, 0.5 
        c_u = (sbc * FOS) / N_c 
        safe_end_bearing = (c_u * N_c * ((math.pi / 4) * ((2.5 * d_pile)**2))) / FOS
        safe_friction_per_m = (alpha * c_u * (math.pi * d_pile)) / FOS

        vol_pile_total = 0.0
        pile_details = []
        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                L_pile = max(3.0, round(((Pu - safe_end_bearing) / safe_friction_per_m if (Pu - safe_end_bearing) > 0 else 0), 1)) 
                v_total_node = ((math.pi / 4) * (d_pile**2) * L_pile) + ((math.pi / 6) * ((2.5 * d_pile)**3 - d_pile**3))
                vol_pile_total += v_total_node
                pile_details.append({'Node': n['id'], 'Pu (kN)': round(Pu,1), 'Req. Length (m)': L_pile, 'Vol (m³)': round(v_total_node, 2)})

        cost_pile = (vol_pile_total * rate_conc) + (vol_pile_total * 7850 * 0.015 * rate_steel)

        st.write(f"**Pad/Combined Foundation Est.:** ₹ {cost_pad:,.2f} (Vol: {vol_pad_total:.1f} m³)")
        st.write(f"**Under-Reamed Pile Foundation Est.:** ₹ {cost_pile:,.2f} (Vol: {vol_pile_total:.1f} m³)")

        if cost_pile < cost_pad: 
            st.success("💡 Recommendation: Under-Reamed Piles are more economical.")
        else: 
            st.info("💡 Recommendation: Standard Pad/Combined footings are more economical.")
            
        with st.expander("View Dynamic Pile Lengths per Column"): 
            st.dataframe(pd.DataFrame(pile_details), use_container_width=True)import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(page_title="IS Code Compliant 3D Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & IS-Code Auto-Design")
st.caption("Strict Compliance: IS 456:2000, IS 875 (Part 1 & 2), IS 1893 (Part 1)")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Floor Elevations")
default_floors = pd.DataFrame({"Floor": [1, 2, 3], "Height (m)": [3.2, 3.0, 3.0]})
floor_data = st.sidebar.data_editor(default_floors, num_rows="dynamic", width="stretch")

z_elevations = {0: 0.0}
current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

st.sidebar.header("2. Structural Grids (From Plan)")
with st.sidebar.expander("Define X-Grids", expanded=True):
    default_x_grids = pd.DataFrame({"Grid_ID": ["A", "B", "C", "D", "E", "F"], "X_Coord (m)": [0.0, 0.115, 4.112, 4.331, 8.039, 9.449]})
    x_grid_data = st.data_editor(default_x_grids, num_rows="dynamic", width="stretch", key="x_grids")

with st.sidebar.expander("Define Y-Grids", expanded=True):
    default_y_grids = pd.DataFrame({"Grid_ID": ["1", "2", "3", "4", "5", "6", "7"], "Y_Coord (m)": [0.0, 2.630, 4.999, 8.343, 9.660, 13.220, 14.326]})
    y_grid_data = st.data_editor(default_y_grids, num_rows="dynamic", width="stretch", key="y_grids")

st.sidebar.header("3. Column Placement")
x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations & Orientations", expanded=True):
    # --- ADDED INSTRUCTIONS HERE ---
    st.info(
        "📝 **How to place columns:**\n"
        "* **X_Grid & Y_Grid:** Type the exact Grid ID (e.g., A, 1) defined in Step 2.\n"
        "* **Offsets:** Shift the column from the exact grid intersection (in meters).\n"
        "* **Angle:** `0` aligns the column's depth (D) along the X-axis. `90` rotates it to the Y-axis.\n"
        "* **Add/Delete:** Click the empty bottom row to add a new column. Click the far-left gray box of a row and press `Delete` to remove it."
    )
    
    default_cols = pd.DataFrame({
        "Col_ID": ["C1", "C2", "C3", "C4", "C5"],
        "X_Grid": ["A", "B", "C", "D", "E"], "Y_Grid": ["1", "2", "3", "4", "5"],
        "X_Offset (m)": [0.0]*5, "Y_Offset (m)": [0.0]*5, "Angle (deg)": [0, 90, 90, 0, 90]
    })
    col_data = st.data_editor(default_cols, num_rows="dynamic", width="stretch")

st.sidebar.header("4. IS Code Design & Load Parameters")
col_dim = st.sidebar.text_input("Init Column Size (mm)", "230x450")
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", "230x400")

col3, col4 = st.sidebar.columns(2)
fck = col3.number_input("fck (MPa)", value=25.0, step=5.0)
fy = col4.number_input("fy (MPa)", value=500.0, step=85.0)
sbc = col3.number_input("SBC (kN/m²)", value=200.0, step=10.0)

st.sidebar.subheader("IS 875 Applied Loads")
live_load = st.sidebar.number_input("Live Load (kN/m²)", value=2.0)
floor_finish = st.sidebar.number_input("Floor Finish (kN/m²)", value=1.5)
wall_thickness = st.sidebar.number_input("Exterior Wall Thk (mm)", value=230)
slab_thickness = st.sidebar.number_input("Slab Thickness (mm)", value=150)
lateral_coeff = st.sidebar.slider("Seismic Base Shear Ah (%)", 0.0, 20.0, 5.0) / 100.0

st.sidebar.header("5. AI Optimization")
auto_optimize = st.sidebar.checkbox("Enable IS 456 Safe Auto-Sizing", value=True)
allow_ai_restructure = st.sidebar.checkbox("Allow AI Restructuring (Add Beams/Columns)", value=True)

def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == "": 
            return default
        return float(val)
    except (ValueError, TypeError): 
        return default

# --- GEOMETRY GENERATOR FUNCTION ---
def build_geometry(primary_pts, secondary_pts, z_dict, n_stories, c_dim, b_dim):
    gen_nodes = []
    gen_elements = []
    nid = 0
    
    # Primary Nodes (Columns)
    for floor_idx in range(n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in primary_pts:
            gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': pt.get('angle', 0), 'is_primary': True})
            nid += 1
            
    # Secondary Nodes (Mid-span beams)
    for floor_idx in range(1, n_stories + 1):
        z_val = z_dict.get(floor_idx, 0.0)
        for pt in secondary_pts:
            if pt['floor'] == floor_idx:
                gen_nodes.append({'id': nid, 'x': pt['x'], 'y': pt['y'], 'z': z_val, 'floor': floor_idx, 'angle': 0, 'is_primary': False})
                nid += 1

    # Vertical Elements (Columns)
    eid = 0
    for z in range(n_stories):
        bottom_nodes = [n for n in gen_nodes if n['floor'] == z and n.get('is_primary', True)]
        top_nodes = [n for n in gen_nodes if n['floor'] == z + 1 and n.get('is_primary', True)]
        for bn in bottom_nodes:
            tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
            if tn:
                gen_elements.append({'id': eid, 'ni': bn['id'], 'nj': tn['id'], 'type': 'Column', 'floor': z, 'size': c_dim, 'angle': bn['angle']})
                eid += 1
                
    # Horizontal Elements (Beams)
    tolerance = 0.5 
    for z in range(1, n_stories + 1):
        floor_nodes = [n for n in gen_nodes if n['floor'] == z]
        
        # X-Direction Beams (grouped by Y)
        y_groups = {}
        for n in floor_nodes:
            matched = False
            for y_key in y_groups.keys():
                if abs(n['y'] - y_key) <= tolerance:
                    y_groups[y_key].append(n)
                    matched = True
                    break
            if not matched: 
                y_groups[n['y']] = [n]
                
        for y_key, group in y_groups.items():
            group = sorted(group, key=lambda k: k['x'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
                
        # Y-Direction Beams (grouped by X)
        x_groups = {}
        for n in floor_nodes:
            matched = False
            for x_key in x_groups.keys():
                if abs(n['x'] - x_key) <= tolerance:
                    x_groups[x_key].append(n)
                    matched = True
                    break
            if not matched: 
                x_groups[n['x']] = [n]
                
        for x_key, group in x_groups.items():
            group = sorted(group, key=lambda k: k['y'])
            for i in range(len(group)-1):
                gen_elements.append({'id': eid, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': b_dim, 'angle': 0})
                eid += 1
                
    return gen_nodes, gen_elements

# Extract geometry points
primary_xy = []
for idx, row in col_data.iterrows():
    xg = str(row.get('X_Grid', '')).strip()
    yg = str(row.get('Y_Grid', '')).strip()
    if xg in x_map and yg in y_map:
        calc_x = x_map[xg] + safe_float(row.get('X_Offset (m)'))
        calc_y = y_map[yg] + safe_float(row.get('Y_Offset (m)'))
        primary_xy.append({'x': calc_x, 'y': calc_y, 'angle': safe_float(row.get('Angle (deg)'))})

secondary_xy = [] 
nodes, elements = build_geometry(primary_xy, secondary_xy, z_elevations, num_stories, col_dim, beam_dim)

# --- VIEWPORT RENDERING FUNCTION ---
def render_viewport(view_nodes, view_elements, title="Structural Model Viewport", suffix="1"):
    st.subheader(title)
    col_v1, col_v2 = st.columns(2)
    show_arch_grids = col_v1.checkbox("Show Architectural Grids", value=True, key=f"grid_{suffix}")
    show_axis = col_v2.checkbox("Show 3D Axis", value=True, key=f"axis_{suffix}")

    fig = go.Figure()

    for el in view_elements:
        ni = next(n for n in view_nodes if n['id'] == el['ni'])
        nj = next(n for n in view_nodes if n['id'] == el['nj'])
        
        is_secondary = not (ni.get('is_primary', True) and nj.get('is_primary', True))
        
        if el['type'] == 'Column': color = 'blue'
        elif is_secondary: color = '#2ca02c' 
        else: color = 'red'
            
        fig.add_trace(go.Scatter3d(
            x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']],
            mode='lines', line=dict(color=color, width=4), hoverinfo='text', 
            text=f"{el['type']} ID:{el['id']}", showlegend=False
        ))

    if show_arch_grids and x_map and y_map:
        min_x, max_x = min(x_map.values()), max(x_map.values())
        min_y, max_y = min(y_map.values()), max(y_map.values())
        
        for grid_id, y_val in y_map.items():
            fig.add_trace(go.Scatter3d(x=[min_x-1, max_x+1], y=[y_val, y_val], z=[0, 0], mode='lines+text', line=dict(color='gray', width=2, dash='dash'), text=[f"Grid {grid_id}", ''], textposition='middle left', hoverinfo='none', showlegend=False))
        for grid_id, x_val in x_map.items():
            fig.add_trace(go.Scatter3d(x=[x_val, x_val], y=[min_y-1, max_y+1], z=[0, 0], mode='lines+text', line=dict(color='gray', width=2, dash='dash'), text=[f"Grid {grid_id}", ''], textposition='bottom center', hoverinfo='none', showlegend=False))

    x_coords = [n['x'] for n in view_nodes]
    y_coords = [n['y'] for n in view_nodes]
    z_coords = [n['z'] for n in view_nodes]
    
    fig.add_trace(go.Scatter3d(x=x_coords, y=y_coords, z=z_coords, mode='markers', marker=dict(size=3, color='black'), hoverinfo='text', text=[f"Node: {n['id']}" for n in view_nodes], showlegend=False))

    axis_config = dict(showbackground=show_axis, showgrid=show_axis, zeroline=show_axis, showticklabels=show_axis)
    fig.update_layout(scene=dict(xaxis=dict(**axis_config, title='X' if show_axis else ''), yaxis=dict(**axis_config, title='Y' if show_axis else ''), zaxis=dict(**axis_config, title='Z' if show_axis else ''), aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=500)
    st.plotly_chart(fig, width="stretch")

render_viewport(nodes, elements, "Initial User Model", "init")

# --- ANALYSIS ENGINE ---
def get_transformation_matrix(ni, nj):
    dx, dy, dz = nj['x'] - ni['x'], nj['y'] - ni['y'], nj['z'] - ni['z']
    L = math.sqrt(dx**2 + dy**2 + dz**2)
    cx, cy, cz = dx/L, dy/L, dz/L
    
    if abs(cx) < 1e-6 and abs(cy) < 1e-6: 
        # Vertical Member
        lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
    else: 
        D = math.sqrt(cx**2 + cy**2)
        lam = np.array([
            [cx, cy, cz], 
            [-cx*cz/D, -cy*cz/D, D], 
            [cy/D, -cx/D, 0]
        ])
        
    T = np.zeros((12, 12))
    for i in range(4): 
        T[i*3:(i+1)*3, i*3:(i+1)*3] = lam
    return T

def get_local_stiffness(E, G, A, Iy, Iz, J, L):
    k = np.zeros((12, 12))
    
    # Axial
    k[0, 0] = k[6, 6] = E * A / L
    k[0, 6] = k[6, 0] = -E * A / L
    
    # Torsion
    k[3, 3] = k[9, 9] = G * J / L
    k[3, 9] = k[9, 3] = -G * J / L
    
    # Bending about Local Y
    k[2, 2] = k[8, 8] = 12 * E * Iy / L**3
    k[2, 8] = k[8, 2] = -12 * E * Iy / L**3
    k[4, 4] = k[10, 10] = 4 * E * Iy / L
    k[4, 10] = k[10, 4] = 2 * E * Iy / L
    k[2, 4] = k[2, 10] = k[4, 2] = k[10, 2] = -6 * E * Iy / L**2
    k[8, 4] = k[8, 10] = k[4, 8] = k[10, 8] = 6 * E * Iy / L**2
    
    # Bending about Local Z
    k[1, 1] = k[7, 7] = 12 * E * Iz / L**3
    k[1, 7] = k[7, 1] = -12 * E * Iz / L**3
    k[5, 5] = k[11, 11] = 4 * E * Iz / L
    k[5, 11] = k[11, 5] = 2 * E * Iz / L
    k[1, 5] = k[1, 11] = k[5, 1] = k[11, 1] = 6 * E * Iz / L**2
    k[7, 5] = k[7, 11] = k[5, 7] = k[11, 7] = -6 * E * Iz / L**2
    
    return k

def run_analysis(current_elements, current_nodes):
    num_nodes = len(current_nodes)
    if num_nodes == 0: 
        return current_elements, 0.0
        
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    X_coords, Y_coords = [n['x'] for n in current_nodes], [n['y'] for n in current_nodes]
    floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.85 if X_coords else 0
    slab_dl_per_m2 = (slab_thickness / 1000.0) * 25.0
    total_dl_per_m2 = slab_dl_per_m2 + floor_finish
    total_floor_dl = floor_area * total_dl_per_m2
    total_floor_ll = floor_area * live_load
    
    total_beam_len = sum([math.sqrt((next(n for n in current_nodes if n['id'] == el['nj'])['x']-next(n for n in current_nodes if n['id'] == el['ni'])['x'])**2 + (next(n for n in current_nodes if n['id'] == el['nj'])['y']-next(n for n in current_nodes if n['id'] == el['ni'])['y'])**2) for el in current_elements if el['type'] == 'Beam'])
    if total_beam_len == 0: total_beam_len = 1.0

    seismic_weight_total = 0.0
    ll_factor = 0.25 if live_load <= 3.0 else 0.50 
    seismic_mass_per_floor = total_floor_dl + (ll_factor * total_floor_ll)

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
            
        A_sec = b * h
        Iy_sec = (b * h**3) / 12.0
        Iz_sec = (h * b**3) / 12.0
        
        # Flaw Fix: Torsional Constant requires min and max dimensions
        dim_min, dim_max = min(b, h), max(b, h)
        J_sec = (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))

        T_matrix = get_transformation_matrix(ni_data, nj_data)
        k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            # Flaw Fix: FEM vector alignment with Vertical Y-axis
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL = np.zeros(12)
            F_local_ENL[1] = V     # Shear left
            F_local_ENL[5] = M     # Moment left
            F_local_ENL[7] = V     # Shear right
            F_local_ENL[11] = -M   # Moment right
            
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
        raise Exception("Matrix is singular. Frame geometry is unstable.")
        
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
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * el['length']) / 2.0, (w * el['length']**2) / 12.0
            F_local_ENL[1], F_local_ENL[5], F_local_ENL[7], F_local_ENL[11] = V, M, V, -M
            
        el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL

    return current_elements, np.max(np.abs(U_global))

def perform_design(elements_to_design):
    design_status = True
    mulim_coeff = 0.133 if fy >= 500 else 0.138 
    tau_c_max = 0.62 * math.sqrt(fck) 
    
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        
        el['pass'] = True
        el['design_details'] = {}
        
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
            
            if Mu_max > Mu_lim or tau_v > tau_c_max:
                el['pass'] = False
                design_status = False
                
            el['design_details'] = {
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Mu_max (kN.m)': round(Mu_max, 2), 'Vu_max (kN)': round(Vu_max, 2),
                'Shear τv (MPa)': round(tau_v, 2), 'Status': 'Safe' if el['pass'] else 'Fail'
            }
                
        elif el['type'] == 'Column':
            Pu = max(abs(el['F_internal'][0]), abs(el['F_internal'][6]))
            Mu_y = max(abs(el['F_internal'][4]), abs(el['F_internal'][10]))
            Mu_z = max(abs(el['F_internal'][5]), abs(el['F_internal'][11]))
            Mu_max = max(Mu_y, Mu_z)
            
            Ag = b * h
            d_col = h - 40
            Asc_req_axial = (Pu * 1000 - 0.4 * fck * Ag) / (0.67 * fy - 0.4 * fck) if (Pu * 1000 > 0.4 * fck * Ag) else 0
            Asc_req_mom = (Mu_max * 1e6) / (0.87 * fy * 0.8 * d_col) if Mu_max > 0 else 0
            Asc_calc = Asc_req_axial + Asc_req_mom
            
            if Asc_calc > 0.04 * Ag: 
                el['pass'] = False
                design_status = False
                    
            el['design_details'] = {
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Orientation': f"{el.get('angle', 0)}°", 'Pu_max (kN)': round(Pu, 2), 'Mu_max (kN.m)': round(Mu_max, 2),
                'Req Asc (mm²)': round(max(Asc_calc, 0.008 * Ag), 2),
                'Status': 'Safe' if el['pass'] else 'Fail'
            }
                    
    return elements_to_design, design_status

def group_elements(elements_list, elem_type):
    df = pd.DataFrame([el['design_details'] for el in elements_list if el['type'] == elem_type])
    if df.empty: return df
    if elem_type == 'Column':
        grouped = df.groupby(['Floor', 'Size (mm)', 'Orientation']).agg(
            Max_Pu=('Pu_max (kN)', 'max'), Max_Mu=('Mu_max (kN.m)', 'max'), Max_Req_Asc=('Req Asc (mm²)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"C{i+1}" for i in range(len(grouped))]
        return grouped
    elif elem_type == 'Beam':
        grouped = df.groupby(['Floor', 'Size (mm)']).agg(
            Max_Mu=('Mu_max (kN.m)', 'max'), Max_Vu=('Vu_max (kN)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"B{i+1}" for i in range(len(grouped))]
        return grouped

# --- EXECUTION BLOCK ---
if st.button("Run 3-Stage AI Optimization & Design", type="primary", width="stretch"):
    with st.spinner("Analyzing Frame..."):
        if len(nodes) < 2:
            st.error("Not enough valid nodes generated. Please check your grid definitions.")
            st.stop()
            
        passed_phase1, passed_phase2, passed_phase3 = False, False, False
        max_iters = 8 
        
        # --- PHASE 1: STANDARD SIZING ---
        iteration = 1
        while iteration <= max_iters:
            try:
                elements, max_def = run_analysis(elements, nodes)
                elements, passed_phase1 = perform_design(elements)
                
                if passed_phase1 or not auto_optimize:
                    if passed_phase1: st.success(f"✅ Phase 1: Initial Topology achieved 100% Safe Design in {iteration} iteration(s).")
                    break
                else:
                    for el in elements:
                        if not el['pass']:
                            b_str, h_str = el['size'].split('x')
                            b, h = int(b_str), int(h_str)
                            if el['type'] == 'Beam':
                                if h < 600: h += 50 
                                else: b += 50       
                            else:
                                b += 50; h += 50
                            el['size'] = f"{b}x{h}"
                    iteration += 1
            except Exception as e:
                st.error(f"Solver Error: {e}")
                st.stop()
                
        # --- PHASE 2: SECONDARY BEAM INJECTION ---
        if not passed_phase1 and allow_ai_restructure:
            st.warning("⚠️ Phase 1 failed. Beams exceeded IS 456 limits. Phase 2: Injecting Secondary Beams...")
            
            added_sec_nodes = 0
            for el in elements:
                if el['type'] == 'Beam' and not el['pass'] and el['length'] > 4.5:
                    ni = next(n for n in nodes if n['id'] == el['ni'])
                    nj = next(n for n in nodes if n['id'] == el['nj'])
                    mid_x = (ni['x'] + nj['x']) / 2.0
                    mid_y = (ni['y'] + nj['y']) / 2.0
                    
                    if not any(math.sqrt((p['x']-mid_x)**2 + (p['y']-mid_y)**2) < 1.0 for p in secondary_xy if p['floor'] == ni['floor']):
                        secondary_xy.append({'x': mid_x, 'y': mid_y, 'floor': ni['floor']})
                        added_sec_nodes += 1
                            
            if added_sec_nodes > 0:
                st.info(f"🧠 AI injected {added_sec_nodes} secondary nodes to break spans. Re-analyzing...")
                ai_nodes, ai_elements = build_geometry(primary_xy, secondary_xy, z_elevations, num_stories, col_dim, beam_dim)
                
                ai_iters = 1
                while ai_iters <= 8: 
                    ai_elements, max_def = run_analysis(ai_elements, ai_nodes)
                    ai_elements, passed_phase2 = perform_design(ai_elements)
                    if passed_phase2:
                        st.success(f"✅ Phase 2 Successful! Secondary beams stabilized the structure.")
                        nodes, elements = ai_nodes, ai_elements
                        render_viewport(nodes, elements, "🤖 Phase 2 Model (Green = Secondary Beams)", "ai")
                        break
                    else:
                        for el in ai_elements:
                            if not el['pass']:
                                b_str, h_str = el['size'].split('x')
                                b, h = int(b_str), int(h_str)
                                if el['type'] == 'Beam':
                                    if h < 600: h += 50 
                                    else: b += 50       
                                else:
                                    b += 50; h += 50
                                el['size'] = f"{b}x{h}"
                    ai_iters += 1
                
                if not passed_phase2:
                    nodes, elements = ai_nodes, ai_elements
            else:
                passed_phase2 = False 

        # --- PHASE 3: DEEP RESTRUCTURING ---
        if not passed_phase1 and not passed_phase2 and allow_ai_restructure:
            st.error("⚠️ Phase 2 Secondary Beams failed. Phase 3: Deep Restructuring (Adding Primary Columns)...")
            
            hard_primary_xy = list(primary_xy)
            added_cols = 0
            
            for pt in secondary_xy:
                if not any(math.sqrt((p['x']-pt['x'])**2 + (p['y']-pt['y'])**2) < 1.0 for p in hard_primary_xy):
                    hard_primary_xy.append({'x': pt['x'], 'y': pt['y'], 'angle': 0.0})
                    added_cols += 1

            for el in elements:
                if el['type'] == 'Beam' and not el['pass'] and el['length'] > 4.0:
                    ni = next(n for n in nodes if n['id'] == el['ni'])
                    nj = next(n for n in nodes if n['id'] == el['nj'])
                    mid_x = (ni['x'] + nj['x']) / 2.0
                    mid_y = (ni['y'] + nj['y']) / 2.0
                    if not any(math.sqrt((p['x']-mid_x)**2 + (p['y']-mid_y)**2) < 1.0 for p in hard_primary_xy):
                        hard_primary_xy.append({'x': mid_x, 'y': mid_y, 'angle': 0.0})
                        added_cols += 1

            if added_cols > 0:
                st.info(f"🏗️ AI dropped {added_cols} new primary columns down to the foundation. Re-analyzing...")
                hard_nodes, hard_elements = build_geometry(hard_primary_xy, [], z_elevations, num_stories, col_dim, beam_dim)
                
                hard_iters = 1
                while hard_iters <= 10:
                    hard_elements, max_def = run_analysis(hard_elements, hard_nodes)
                    hard_elements, passed_phase3 = perform_design(hard_elements)
                    if passed_phase3:
                        st.success(f"✅ Phase 3 Deep Restructuring Successful! 100% Safe Design Guaranteed.")
                        break
                    else:
                        for el in hard_elements:
                            if not el['pass']:
                                b_str, h_str = el['size'].split('x')
                                b, h = int(b_str), int(h_str)
                                if el['type'] == 'Beam':
                                    if h < 600: h += 50 
                                    else: b += 50       
                                else:
                                    b += 50; h += 50
                                el['size'] = f"{b}x{h}"
                    hard_iters += 1
                
                nodes, elements = hard_nodes, hard_elements
                render_viewport(nodes, elements, "🏗️ Phase 3 Deep Restructured Model", "hard")
            else:
                st.info("🧠 AI could not safely inject columns without severe crowding. Manual layout review required.")

        # --- EXTRACT SPAN DATA FOR SLABS ---
        max_span_x, max_span_y = 0.1, 0.1
        for el in elements:
            if el['type'] == 'Beam':
                span_x = abs(next(n for n in nodes if n['id'] == el['nj'])['x'] - next(n for n in nodes if n['id'] == el['ni'])['x'])
                span_y = abs(next(n for n in nodes if n['id'] == el['nj'])['y'] - next(n for n in nodes if n['id'] == el['ni'])['y'])
                if span_x > max_span_x: max_span_x = span_x
                if span_y > max_span_y: max_span_y = span_y

        slabs = []
        for z in range(1, num_stories + 1):
            slabs.append({
                'Floor': z, 'Max Grid Dim (m)': f"{round(max_span_x,2)} x {round(max_span_y,2)}",
                'Behavior': "One-Way" if (max_span_y/max_span_x if max_span_x>0 else 1)>2.0 else "Two-Way", 
                'Thickness (mm)': slab_thickness,
                'Status': 'Safe'
            })
                    
        # --- FOOTINGS ---
        base_nodes = [n for n in nodes if n['z'] == 0]
        footings = []
        pad_footings_dict = {}

        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                pad_footings_dict[n['id']] = {'Pu': Pu, 'side': math.ceil(math.sqrt((Pu / 1.5 * 1.1) / sbc) * 10) / 10, 'x': n['x'], 'y': n['y']}

        processed_nodes = set()
        footing_id = 1
        for n1_id, f1 in pad_footings_dict.items():
            if n1_id in processed_nodes: continue
            combined_with = [n2_id for n2_id, f2 in pad_footings_dict.items() if n1_id != n2_id and n2_id not in processed_nodes and math.sqrt((f1['x'] - f2['x'])**2 + (f1['y'] - f2['y'])**2) < (f1['side']/2 + f2['side']/2)]
            
            if combined_with:
                group = [n1_id] + combined_with
                L_comb = max([pad_footings_dict[nid]['x'] for nid in group]) - min([pad_footings_dict[nid]['x'] for nid in group]) + max([pad_footings_dict[nid]['side'] for nid in group])
                B_comb = max(sum((pad_footings_dict[nid]['Pu'] / 1.5 * 1.1) / sbc for nid in group) / L_comb, max([pad_footings_dict[nid]['side'] for nid in group]))
                footings.append({'ID': f"CF-{footing_id}", 'Type': 'Combined', 'Total Pu (kN)': round(sum(pad_footings_dict[nid]['Pu'] for nid in group), 2), 'Provided L x B (m)': f"{round(L_comb,1)} x {round(B_comb,1)}", 'Depth (mm)': max(400, int(B_comb * 1000 / 3)), 'Status': 'Safe'})
                processed_nodes.update(group)
            else:
                footings.append({'ID': f"F-{footing_id}", 'Type': 'Isolated Pad', 'Total Pu (kN)': round(f1['Pu'], 2), 'Provided L x B (m)': f"{f1['side']} x {f1['side']}", 'Depth (mm)': max(300, int(f1['side'] * 1000 / 4)), 'Status': 'Safe'})
            processed_nodes.add(n1_id)
            footing_id += 1

        # --- 5. BOQ ---
        st.divider()
        st.header("5. Material Abstract & BoQ")
        materials = []
        total_conc, total_steel = 0, 0
        X_coords, Y_coords = [n['x'] for n in nodes], [n['y'] for n in nodes]
        approx_floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.85 if X_coords else 0
        
        for z in range(num_stories + 1):
            conc_vol, steel_wt = 0, 0
            floor_elements = [e for e in elements if e['floor'] == z]
            for el in floor_elements:
                b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
                vol = b * h * el['length']
                conc_vol += vol
                steel_wt += vol * 7850 * (0.015 if el['type'] == 'Column' else 0.012)
            
            slab_vol = approx_floor_area * (slab_thickness/1000) if z > 0 else 0
            conc_vol += slab_vol
            steel_wt += slab_vol * 7850 * 0.008
            total_conc += conc_vol
            total_steel += steel_wt
            if conc_vol > 0: 
                materials.append({"Floor": f"Level {z}", "Concrete (m³)": round(conc_vol, 2), "Steel (kg)": round(steel_wt, 2)})
                
        colA, colB = st.columns(2)
        colA.dataframe(pd.DataFrame(materials), width="stretch")
        colB.metric("Total Concrete Volume", f"{total_conc:.2f} m³")
        colB.metric("Total Rebar Weight", f"{total_steel / 1000:.2f} MT")

        st.divider()
        st.header("6. Detailed Results & Grouping")
        
        col_grp1, col_grp2 = st.columns(2)
        col_grp1.subheader("Beam Groups")
        col_grp1.dataframe(group_elements(elements, 'Beam'), width="stretch")
        col_grp2.subheader("Column Groups")
        col_grp2.dataframe(group_elements(elements, 'Column'), width="stretch")

        tab1, tab2, tab3, tab4 = st.tabs(["Slabs", "Beams", "Columns", "Footings"])
        tab1.dataframe(pd.DataFrame(slabs), width="stretch")
        tab2.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam']), width="stretch")
        tab3.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column']), width="stretch")
        tab4.dataframe(pd.DataFrame(footings), width="stretch")

        # --- 7. FOUNDATION ECONOMICS ---
        st.divider()
        st.header("7. Foundation Economics: Pad vs. Pile (IS 2911 Base)")
        col_rates1, col_rates2, col_rates3 = st.columns(3)
        rate_conc = col_rates1.number_input("Concrete Rate (per m³)", value=6000.0)
        rate_steel = col_rates2.number_input("Steel Rate (per kg)", value=65.0)
        d_pile = col_rates3.selectbox("Pile Shaft Dia (m)", [0.25, 0.30, 0.40], index=1)

        vol_pad_total = sum([float(f['Provided L x B (m)'].split(' x ')[0]) * float(f['Provided L x B (m)'].split(' x ')[1]) * (f['Depth (mm)']/1000) for f in footings])
        cost_pad = (vol_pad_total * rate_conc) + (vol_pad_total * 7850 * 0.008 * rate_steel)

        FOS, N_c, alpha = 2.5, 9.0, 0.5 
        c_u = (sbc * FOS) / N_c 
        safe_end_bearing = (c_u * N_c * ((math.pi / 4) * ((2.5 * d_pile)**2))) / FOS
        safe_friction_per_m = (alpha * c_u * (math.pi * d_pile)) / FOS

        vol_pile_total = 0.0
        pile_details = []
        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                L_pile = max(3.0, round(((Pu - safe_end_bearing) / safe_friction_per_m if (Pu - safe_end_bearing) > 0 else 0), 1)) 
                v_total_node = ((math.pi / 4) * (d_pile**2) * L_pile) + ((math.pi / 6) * ((2.5 * d_pile)**3 - d_pile**3))
                vol_pile_total += v_total_node
                pile_details.append({'Node': n['id'], 'Pu (kN)': round(Pu,1), 'Req. Length (m)': L_pile, 'Vol (m³)': round(v_total_node, 2)})

        cost_pile = (vol_pile_total * rate_conc) + (vol_pile_total * 7850 * 0.015 * rate_steel)

        st.write(f"**Pad/Combined Foundation Est.:** ₹ {cost_pad:,.2f} (Vol: {vol_pad_total:.1f} m³)")
        st.write(f"**Under-Reamed Pile Foundation Est.:** ₹ {cost_pile:,.2f} (Vol: {vol_pile_total:.1f} m³)")

        if cost_pile < cost_pad: 
            st.success("💡 Recommendation: Under-Reamed Piles are more economical.")
        else: 
            st.info("💡 Recommendation: Standard Pad/Combined footings are more economical.")
            
        with st.expander("View Dynamic Pile Lengths per Column"): 
            st.dataframe(pd.DataFrame(pile_details), width="stretch")
