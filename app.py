import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(page_title="3D Building Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & Design")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Floor Elevations")
default_floors = pd.DataFrame({"Floor": [1, 2, 3], "Height (m)": [3.2, 3.0, 3.0]})
floor_data = st.sidebar.data_editor(default_floors, num_rows="dynamic", use_container_width=True)

# Calculate cumulative Z elevations
z_elevations = {0: 0.0}
current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z
num_stories = len(floor_data)

st.sidebar.header("2. Structural Grids (From Plan)")
st.sidebar.caption("Extracted from Gaidhane Residence Centerline")

with st.sidebar.expander("Define X-Grids (Vertical Lines)", expanded=True):
    default_x_grids = pd.DataFrame({
        "Grid_ID": ["A", "B", "C", "D", "E", "F"],
        "X_Coord (m)": [0.000, 0.115, 4.112, 4.331, 8.039, 9.449]
    })
    x_grid_data = st.data_editor(default_x_grids, num_rows="dynamic", use_container_width=True, key="x_grids")

with st.sidebar.expander("Define Y-Grids (Horizontal Lines)", expanded=True):
    default_y_grids = pd.DataFrame({
        "Grid_ID": ["1", "2", "3", "4", "5", "6", "7"],
        "Y_Coord (m)": [0.000, 2.630, 4.999, 8.343, 9.660, 13.220, 14.326]
    })
    y_grid_data = st.data_editor(default_y_grids, num_rows="dynamic", use_container_width=True, key="y_grids")

st.sidebar.header("3. Column Placement (Grid Intersections)")
st.sidebar.caption("Place columns at grid nodes. Add offsets if not perfectly centered.")

# Build dictionary maps for quick coordinate lookup
x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations & Orientations", expanded=True):
    default_cols = pd.DataFrame({
        "Col_ID": ["C1", "C2", "C3", "C4", "C5"],
        "X_Grid": ["A", "B", "C", "D", "E"],
        "Y_Grid": ["1", "2", "3", "4", "5"],
        "X_Offset (m)": [0.0, 0.0, 0.0, 0.0, 0.0],
        "Y_Offset (m)": [0.0, 0.0, 0.0, 0.0, 0.0],
        "Angle (deg)": [0, 90, 90, 0, 90]
    })
    col_data = st.data_editor(default_cols, num_rows="dynamic", use_container_width=True)

st.sidebar.header("4. Design & Load Parameters")
col_dim = st.sidebar.text_input("Init Column Size (mm)", "230x450")
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", "230x400")
fck = st.sidebar.number_input("fck (MPa)", value=25.0, step=5.0)
fy = st.sidebar.number_input("fy (MPa)", value=500.0, step=85.0)
sbc = st.sidebar.number_input("SBC (kN/m²)", value=200.0, step=10.0)
lateral_coeff = st.sidebar.slider("Lateral Load Coeff (% of W)", 0.0, 20.0, 5.0) / 100.0
auto_optimize = st.sidebar.checkbox("Enable Auto-Sizing", value=True)

# Helper function to safely convert empty/null table cells to floats
def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val is None or str(val).strip() == "": return default
        return float(val)
    except (ValueError, TypeError): return default

# --- GEOMETRY GENERATOR (GRID-BASED) ---
nodes = []
elements = []
node_id = 0

# 1. Generate Nodes based on Grid Intersections
for floor_idx in range(num_stories + 1):
    z_val = z_elevations.get(floor_idx, 0.0)
    for idx, row in col_data.iterrows():
        xg = str(row.get('X_Grid', '')).strip()
        yg = str(row.get('Y_Grid', '')).strip()
        
        # Look up coordinates, apply offsets
        if xg in x_map and yg in y_map:
            calc_x = x_map[xg] + safe_float(row.get('X_Offset (m)'))
            calc_y = y_map[yg] + safe_float(row.get('Y_Offset (m)'))
            
            nodes.append({
                'id': node_id, 
                'x': calc_x, 
                'y': calc_y, 
                'z': z_val, 
                'floor': floor_idx,
                'angle': safe_float(row.get('Angle (deg)'))
            })
            node_id += 1

# 2. Generate Columns
element_id = 0
for z in range(num_stories):
    bottom_nodes = [n for n in nodes if n['floor'] == z]
    top_nodes = [n for n in nodes if n['floor'] == z + 1]
    
    for bn in bottom_nodes:
        tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
        if tn:
            elements.append({'id': element_id, 'ni': bn['id'], 'nj': tn['id'], 'type': 'Column', 'floor': z, 'size': col_dim, 'angle': bn['angle']})
            element_id += 1

# 3. Generate Beams (Auto-Routing via Proximity)
tolerance = 0.5 
max_span_x = 0.1
max_span_y = 0.1

for z in range(1, num_stories + 1):
    floor_nodes = [n for n in nodes if n['floor'] == z]
    
    # Route X-Beams
    y_groups = {}
    for n in floor_nodes:
        matched = False
        for y_key in y_groups.keys():
            if abs(n['y'] - y_key) <= tolerance:
                y_groups[y_key].append(n)
                matched = True; break
        if not matched: y_groups[n['y']] = [n]
            
    for y_key, group in y_groups.items():
        group = sorted(group, key=lambda k: k['x'])
        for i in range(len(group)-1):
            span = abs(group[i]['x'] - group[i+1]['x'])
            if span > max_span_x: max_span_x = span
            elements.append({'id': element_id, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': beam_dim, 'angle': 0})
            element_id += 1
            
    # Route Y-Beams
    x_groups = {}
    for n in floor_nodes:
        matched = False
        for x_key in x_groups.keys():
            if abs(n['x'] - x_key) <= tolerance:
                x_groups[x_key].append(n)
                matched = True; break
        if not matched: x_groups[n['x']] = [n]
            
    for x_key, group in x_groups.items():
        group = sorted(group, key=lambda k: k['y'])
        for i in range(len(group)-1):
            span = abs(group[i]['y'] - group[i+1]['y'])
            if span > max_span_y: max_span_y = span
            elements.append({'id': element_id, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': beam_dim, 'angle': 0})
            element_id += 1

# --- 3D VISUALIZATION WITH GRIDS ---
st.subheader("Structural Model Viewport")

col_view1, col_view2 = st.columns(2)
show_arch_grids = col_view1.checkbox("Show Architectural Grids (Base)", value=True)
show_axis = col_view2.checkbox("Show 3D Axis Mesh & Background", value=True)

fig = go.Figure()

for el in elements:
    ni = next(n for n in nodes if n['id'] == el['ni'])
    nj = next(n for n in nodes if n['id'] == el['nj'])
    color = 'blue' if el['type'] == 'Column' else 'red'
    fig.add_trace(go.Scatter3d(
        x=[ni['x'], nj['x']], y=[ni['y'], nj['y']], z=[ni['z'], nj['z']],
        mode='lines', line=dict(color=color, width=4), hoverinfo='text', text=f"{el['type']} ID: {el['id']}", showlegend=False
    ))

# Plot Architectural Grids at Z=0
if show_arch_grids and x_map and y_map:
    min_x, max_x = min(x_map.values()), max(x_map.values())
    min_y, max_y = min(y_map.values()), max(y_map.values())
    grid_extension = 1.5 
    
    for grid_id, y_val in y_map.items():
        fig.add_trace(go.Scatter3d(
            x=[min_x - grid_extension, max_x + grid_extension], y=[y_val, y_val], z=[0, 0],
            mode='lines+text', line=dict(color='gray', width=2, dash='dash'),
            text=[f"Grid {grid_id}", ''], textposition='middle left',
            hoverinfo='none', showlegend=False
        ))
        
    for grid_id, x_val in x_map.items():
        fig.add_trace(go.Scatter3d(
            x=[x_val, x_val], y=[min_y - grid_extension, max_y + grid_extension], z=[0, 0],
            mode='lines+text', line=dict(color='gray', width=2, dash='dash'),
            text=[f"Grid {grid_id}", ''], textposition='bottom center',
            hoverinfo='none', showlegend=False
        ))

x_coords = [n['x'] for n in nodes]
y_coords = [n['y'] for n in nodes]
z_coords = [n['z'] for n in nodes]
fig.add_trace(go.Scatter3d(
    x=x_coords, y=y_coords, z=z_coords, mode='markers', 
    marker=dict(size=4, color='black'), hoverinfo='text', 
    text=[f"Node: {n['id']}" for n in nodes], showlegend=False
))

# Configure Axis Mesh Visibility safely
if show_axis:
    axis_config = dict(showbackground=True, showgrid=True, zeroline=True)
else:
    axis_config = dict(showbackground=False, showgrid=False, zeroline=False, showticklabels=False)

fig.update_layout(
    scene=dict(
        xaxis=dict(**axis_config, title='X (m)' if show_axis else ''),
        yaxis=dict(**axis_config, title='Y (m)' if show_axis else ''),
        zaxis=dict(**axis_config, title='Z (m)' if show_axis else ''),
        aspectmode='data'
    ), 
    margin=dict(l=0, r=0, b=0, t=0), 
    height=600
)
st.plotly_chart(fig, use_container_width=True)

# --- ANALYSIS ENGINE ---
slab_thickness = 150
dl_area = (slab_thickness / 1000.0) * 25.0 + 1.5 
ll_area = 3.0
q_factored = 1.5 * (dl_area + ll_area)

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

def run_analysis(current_elements):
    num_nodes = len(nodes)
    if num_nodes == 0: return current_elements, 0.0
    F_global = np.zeros(num_nodes * 6)
    E_conc = 5000 * math.sqrt(fck) * 1e3
    G_conc = E_conc / 2.4 
    
    # 1. Distribute Gravity Loads
    for el in current_elements:
        el['load_kN_m'] = 0.0
        if el['type'] == 'Beam':
            ni = next(n for n in nodes if n['id'] == el['ni'])
            nj = next(n for n in nodes if n['id'] == el['nj'])
            L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
            el['load_kN_m'] = q_factored * (L / 2.0) 

    # 2. Distribute Lateral Loads
    total_weight = sum([el['load_kN_m'] * el['length'] for el in current_elements if el['type'] == 'Beam' and 'length' in el] + [0]) * 1.5
    if total_weight == 0: total_weight = 1000 
    V_base = lateral_coeff * total_weight
    
    floor_weights = {z: total_weight / num_stories for z in range(1, num_stories + 1)}
    sum_wh2 = sum([floor_weights[z] * (z_elevations[z]**2) for z in floor_weights])
    floor_forces = {z: V_base * (floor_weights[z] * (z_elevations[z]**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_weights}

    for n in nodes:
        if n['z'] > 0:
            nodes_this_floor = len([nd for nd in nodes if nd['floor'] == n['floor']])
            F_global[n['id'] * 6] += (floor_forces[n['floor']] / nodes_this_floor) if nodes_this_floor > 0 else 0

    # 3. Assemble Matrices
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        el['length'] = L
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
        A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
        J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))

        T_matrix = get_transformation_matrix(ni_data, nj_data)
        k_local = get_local_stiffness(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        el['k_global'] = np.dot(np.dot(T_matrix.T, k_local), T_matrix)

        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * L) / 2.0, (w * L**2) / 12.0
            F_local_ENL = np.zeros(12)
            F_local_ENL[2], F_local_ENL[4], F_local_ENL[8], F_local_ENL[10] = -V, -M, -V, M
            P_global = np.dot(T_matrix.T, F_local_ENL)
            F_global[el['ni']*6 : el['ni']*6+6] += P_global[0:6]
            F_global[el['nj']*6 : el['nj']*6+6] += P_global[6:12]

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
    
    try:
        U_free = np.linalg.solve(K_global[np.ix_(free_dofs, free_dofs)], F_global[free_dofs])
    except np.linalg.LinAlgError:
        raise Exception("Matrix is singular. Check if columns are isolated or not connected properly.")
        
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    # 4. Internal Forces
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        T_matrix = get_transformation_matrix(ni_data, nj_data)
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
        k_local = get_local_stiffness(E_conc, G_conc, b*h, (b*h**3)/12.0, (h*b**3)/12.0, (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4))), el['length'])
        
        i_dof, j_dof = el['ni'] * 6, el['nj'] * 6
        u_local = np.dot(T_matrix, np.concatenate((U_global[i_dof:i_dof+6], U_global[j_dof:j_dof+6])))
        
        F_local_ENL = np.zeros(12)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            V, M = (w * el['length']) / 2.0, (w * el['length']**2) / 12.0
            F_local_ENL[2], F_local_ENL[4], F_local_ENL[8], F_local_ENL[10] = -V, -M, -V, M
            
        el['F_internal'] = np.dot(k_local, u_local) - F_local_ENL

    return current_elements, np.max(np.abs(U_global))

def perform_design(elements_to_design):
    design_status = True
    for el in elements_to_design:
        b, h = map(lambda x: float(x), el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
        
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
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Mu_max (kN.m)': round(Mu_max, 2), 'Vu_max (kN)': round(Vu_max, 2),
                'Shear τv (MPa)': round(tau_v, 2), 'Status': 'Pass' if el['pass'] else 'Fail (Resizing...)'
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
                if Asc_calc > 0.04 * Ag: 
                    el['pass'] = False
                    design_status = False
                    
            el['design_details'] = {
                'Member ID': el['id'], 'Floor': el['floor'], 'Size (mm)': el['size'],
                'Orientation': f"{el.get('angle', 0)}°", 'Pu_max (kN)': round(Pu_max, 2),
                'Req Asc (mm²)': round(max(Asc_calc, 0.008 * Ag), 2),
                'Status': 'Pass' if el['pass'] else 'Fail (Resizing...)'
            }
                    
    return elements_to_design, design_status

def group_elements(elements_list, elem_type):
    df = pd.DataFrame([el['design_details'] for el in elements_list if el['type'] == elem_type])
    if df.empty: return df
    if elem_type == 'Column':
        grouped = df.groupby(['Floor', 'Size (mm)', 'Orientation']).agg(
            Max_Pu=('Pu_max (kN)', 'max'), Max_Req_Asc=('Req Asc (mm²)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"C{i+1}" for i in range(len(grouped))]
        return grouped
    elif elem_type == 'Beam':
        grouped = df.groupby(['Floor', 'Size (mm)']).agg(
            Max_Mu=('Mu_max (kN.m)', 'max'), Max_Vu=('Vu_max (kN)', 'max'), Member_Count=('Member ID', 'count')
        ).reset_index()
        grouped['Group ID'] = [f"B{i+1}" for i in range(len(grouped))]
        return grouped


if st.button("Run AI Optimization & Analysis", type="primary", use_container_width=True):
    with st.spinner("Analyzing Unsymmetric Grid Framing..."):
        iteration = 1
        max_iters = 5 if auto_optimize else 1
        passed = False
        
        if len(nodes) < 2:
            st.error("Not enough valid nodes generated. Please check your grid definitions.")
            st.stop()
            
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
                st.error(f"Solver Error: {e}")
                st.stop()
                
        if not passed and auto_optimize:
            st.warning("⚠️ Reached max iterations, some elements still overstressed. Review model geometry.")

        # --- SLABS ---
        slabs = []
        slab_ratio = max_span_y / max_span_x if max_span_x > 0 else 1.0
        slab_type = "One-Way" if slab_ratio > 2.0 else "Two-Way"
        approx_Mx = (q_factored * max_span_x**2) / (8 if slab_type == "One-Way" else 12)
        
        for z in range(1, num_stories + 1):
            slabs.append({
                'Floor': z, 'Max Dim Found (m)': f"{round(max_span_x,2)} x {round(max_span_y,2)}",
                'Behavior': slab_type, 'Thickness (mm)': slab_thickness,
                'Critical Design B.M (kN.m)': round(approx_Mx, 2), 'Status': 'Pass'
            })
                    
        # --- FOOTINGS ---
        base_nodes = [n for n in nodes if n['z'] == 0]
        footings = []
        pad_footings_dict = {}

        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                P_work = Pu / 1.5
                req_area = (P_work * 1.1) / sbc
                side = math.ceil(math.sqrt(req_area) * 10) / 10
                pad_footings_dict[n['id']] = {'Pu': Pu, 'side': side, 'x': n['x'], 'y': n['y']}

        processed_nodes = set()
        footing_id = 1

        for n1_id, f1 in pad_footings_dict.items():
            if n1_id in processed_nodes: continue
                
            combined_with = []
            for n2_id, f2 in pad_footings_dict.items():
                if n1_id != n2_id and n2_id not in processed_nodes:
                    dist = math.sqrt((f1['x'] - f2['x'])**2 + (f1['y'] - f2['y'])**2)
                    if dist < (f1['side'] / 2 + f2['side'] / 2): combined_with.append(n2_id)
            
            if combined_with:
                group = [n1_id] + combined_with
                total_Pu = sum(pad_footings_dict[nid]['Pu'] for nid in group)
                total_area = sum((pad_footings_dict[nid]['Pu'] / 1.5 * 1.1) / sbc for nid in group)
                
                L_comb = max([pad_footings_dict[nid]['x'] for nid in group]) - min([pad_footings_dict[nid]['x'] for nid in group]) + max([pad_footings_dict[nid]['side'] for nid in group])
                B_comb = max(total_area / L_comb, max([pad_footings_dict[nid]['side'] for nid in group]))
                
                footings.append({
                    'ID': f"CF-{footing_id}", 'Support Nodes': str(group), 'Type': 'Combined',
                    'Total Pu (kN)': round(total_Pu, 2), 'Provided L x B (m)': f"{round(L_comb,1)} x {round(B_comb,1)}",
                    'Depth (mm)': max(400, int(B_comb * 1000 / 3))
                })
                processed_nodes.update(group)
            else:
                footings.append({
                    'ID': f"F-{footing_id}", 'Support Nodes': str([n1_id]), 'Type': 'Isolated Pad',
                    'Total Pu (kN)': round(f1['Pu'], 2), 'Provided L x B (m)': f"{f1['side']} x {f1['side']}",
                    'Depth (mm)': max(300, int(f1['side'] * 1000 / 4))
                })
            processed_nodes.add(n1_id)
            footing_id += 1

        # --- 5. BOQ ---
        st.divider()
        st.header("5. Material Abstract & BoQ")
        materials = []
        total_conc, total_steel = 0, 0
        
        X_coords, Y_coords = [n['x'] for n in nodes], [n['y'] for n in nodes]
        approx_floor_area = (max(X_coords) - min(X_coords)) * (max(Y_coords) - min(Y_coords)) * 0.8 if X_coords else 0
        
        for z in range(num_stories + 1):
            conc_vol, steel_wt = 0, 0
            for el in [el for el in elements if el['floor'] == z]:
                b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
                vol = b * h * el['length']
                conc_vol += vol
                steel_wt += vol * 7850 * (0.015 if el['type'] == 'Column' else 0.012)
            
            slab_vol = approx_floor_area * (slab_thickness/1000) if z > 0 else 0
            slab_steel = slab_vol * 7850 * 0.008
            
            conc_vol += slab_vol
            steel_wt += slab_steel
            total_conc += conc_vol
            total_steel += steel_wt
            
            if conc_vol > 0: materials.append({"Floor": f"Level {z}", "Concrete (m³)": round(conc_vol, 2), "Steel (kg)": round(steel_wt, 2)})
                
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
        tab2.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam']), use_container_width=True)
        tab3.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column']), use_container_width=True)
        tab4.dataframe(pd.DataFrame(footings), use_container_width=True)

        # --- 7. FOUNDATION ECONOMICS ---
        st.divider()
        st.header("7. Foundation Economics: Pad vs. Pile")
        col_rates1, col_rates2, col_rates3 = st.columns(3)
        rate_conc = col_rates1.number_input("Concrete Rate (per m³)", value=6000.0)
        rate_steel = col_rates2.number_input("Steel Rate (per kg)", value=65.0)
        d_pile = col_rates3.selectbox("Pile Shaft Dia (m)", [0.25, 0.30, 0.40], index=1)

        vol_pad_total = sum([float(f['Provided L x B (m)'].split(' x ')[0]) * float(f['Provided L x B (m)'].split(' x ')[1]) * (f['Depth (mm)']/1000) for f in footings])
        steel_pad_total = vol_pad_total * 7850 * 0.008 
        cost_pad = (vol_pad_total * rate_conc) + (steel_pad_total * rate_steel)

        FOS, N_c, alpha = 2.5, 9.0, 0.5 
        c_u = (sbc * FOS) / N_c 
        d_bulb = 2.5 * d_pile
        safe_end_bearing = (c_u * N_c * ((math.pi / 4) * (d_bulb**2))) / FOS
        safe_friction_per_m = (alpha * c_u * (math.pi * d_pile)) / FOS

        vol_pile_total = 0.0
        pile_details = []

        for n in base_nodes:
            conn_col = next((e for e in elements if e['ni'] == n['id'] and e['type'] == 'Column'), None)
            if conn_col:
                Pu = max(abs(conn_col['F_internal'][0]), abs(conn_col['F_internal'][6]))
                L_req = (Pu - safe_end_bearing) / safe_friction_per_m if (Pu - safe_end_bearing) > 0 else 0
                L_pile = max(3.0, round(L_req, 1)) 
                
                v_total_node = ((math.pi / 4) * (d_pile**2) * L_pile) + ((math.pi / 6) * (d_bulb**3 - d_pile**3))
                vol_pile_total += v_total_node
                pile_details.append({'Node': n['id'], 'Pu (kN)': round(Pu,1), 'Req. Length (m)': L_pile, 'Vol (m³)': round(v_total_node, 2)})

        steel_pile_total = vol_pile_total * 7850 * 0.015 
        cost_pile = (vol_pile_total * rate_conc) + (steel_pile_total * rate_steel)

        st.write(f"**Pad/Combined Foundation Est.:** ₹ {cost_pad:,.2f} (Vol: {vol_pad_total:.1f} m³)")
        st.write(f"**Under-Reamed Pile Foundation Est.:** ₹ {cost_pile:,.2f} (Vol: {vol_pile_total:.1f} m³)")

        if cost_pile < cost_pad: st.success("💡 Recommendation: Under-Reamed Piles are more economical.")
        else: st.info("💡 Recommendation: Standard Pad/Combined footings are more economical.")
            
        with st.expander("View Dynamic Pile Lengths per Column"):
            st.dataframe(pd.DataFrame(pile_details), use_container_width=True)
