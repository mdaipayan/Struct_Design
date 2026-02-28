import streamlit as st
import numpy as np
import plotly.graph_objects as go
import math
import pandas as pd

# --- PAGE SETUP ---
st.set_page_config(page_title="3D Building Frame Designer", layout="wide")
st.title("🏢 3D Building Frame Analysis & Design")

# --- SIDEBAR: PARAMETRIC INPUTS ---
st.sidebar.header("1. Building Geometry & Layout")
h_story = st.sidebar.number_input("Story Ht (m)", value=3.0)
num_stories = st.sidebar.number_input("Stories", min_value=1, value=3)

st.sidebar.subheader("Custom Column Coordinates")
st.sidebar.caption("Define unsymmetric column positions and orientations (0 or 90 deg).")
# Default unsymmetric layout to demonstrate functionality
default_cols = pd.DataFrame({
    "Col_ID": ["C1", "C2", "C3", "C4", "C5"],
    "X (m)": [0.0, 4.0, 4.2, 0.0, 8.0],
    "Y (m)": [0.0, 0.0, 3.5, 4.5, 4.5],
    "Angle (deg)": [0, 90, 90, 0, 0]
})
col_data = st.sidebar.data_editor(default_cols, num_rows="dynamic", use_container_width=True)

st.sidebar.header("2. Base Section Properties")
col_dim = st.sidebar.text_input("Init Column Size (mm)", "230x450")
beam_dim = st.sidebar.text_input("Init Beam Size (mm)", "230x400")

col3, col4 = st.sidebar.columns(2)
with col3:
    fck = st.number_input("fck (MPa)", value=25.0, step=5.0)
with col4:
    fy = st.number_input("fy (MPa)", value=500.0, step=85.0)

st.sidebar.header("3. Loading & Geotech")
sbc = st.sidebar.number_input("Soil Bearing Capacity (kN/m²)", value=200.0, step=10.0)
lateral_coeff = st.sidebar.slider("Lateral Load Coeff (% of Gravity)", 0.0, 20.0, 5.0) / 100.0

st.sidebar.header("4. AI Optimization")
auto_optimize = st.sidebar.checkbox("Enable Auto-Sizing (Iterative Redesign)", value=True)

# --- GEOMETRY GENERATOR (UNSYMMETRIC LOGIC) ---
nodes = []
elements = []
node_id = 0

# 1. Generate Nodes from Custom Table
for z in range(int(num_stories) + 1):
    for idx, row in col_data.iterrows():
        nodes.append({
            'id': node_id, 
            'x': float(row['X (m)']), 
            'y': float(row['Y (m)']), 
            'z': z * h_story, 
            'floor': z,
            'angle': float(row.get('Angle (deg)', 0))
        })
        node_id += 1

# 2. Generate Columns (Connecting vertical nodes)
element_id = 0
for z in range(int(num_stories)):
    bottom_nodes = [n for n in nodes if n['floor'] == z]
    top_nodes = [n for n in nodes if n['floor'] == z + 1]
    
    for bn in bottom_nodes:
        # Find corresponding top node (same X, Y)
        tn = next((n for n in top_nodes if abs(n['x'] - bn['x']) < 0.01 and abs(n['y'] - bn['y']) < 0.01), None)
        if tn:
            elements.append({
                'id': element_id, 'ni': bn['id'], 'nj': tn['id'], 
                'type': 'Column', 'floor': z, 'size': col_dim, 'angle': bn['angle']
            })
            element_id += 1

# 3. Generate Beams (Auto-routing based on orthogonal proximity)
tolerance = 0.5 # meters, snaps beams to columns that are slightly off-grid
for z in range(1, int(num_stories) + 1):
    floor_nodes = [n for n in nodes if n['floor'] == z]
    
    # X-Direction Beams (Group by Y coordinate)
    y_groups = {}
    for n in floor_nodes:
        matched = False
        for y_key in y_groups.keys():
            if abs(n['y'] - y_key) <= tolerance:
                y_groups[y_key].append(n)
                matched = True
                break
        if not matched: y_groups[n['y']] = [n]
            
    for y_key, group in y_groups.items():
        group = sorted(group, key=lambda k: k['x'])
        for i in range(len(group)-1):
            elements.append({'id': element_id, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': beam_dim, 'angle': 0})
            element_id += 1
            
    # Y-Direction Beams (Group by X coordinate)
    x_groups = {}
    for n in floor_nodes:
        matched = False
        for x_key in x_groups.keys():
            if abs(n['x'] - x_key) <= tolerance:
                x_groups[x_key].append(n)
                matched = True
                break
        if not matched: x_groups[n['x']] = [n]
            
    for x_key, group in x_groups.items():
        group = sorted(group, key=lambda k: k['y'])
        for i in range(len(group)-1):
            elements.append({'id': element_id, 'ni': group[i]['id'], 'nj': group[i+1]['id'], 'type': 'Beam', 'floor': z, 'size': beam_dim, 'angle': 0})
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

mid_x = [(next(n for n in nodes if n['id'] == el['ni'])['x'] + next(n for n in nodes if n['id'] == el['nj'])['x'])/2 for el in elements]
mid_y = [(next(n for n in nodes if n['id'] == el['ni'])['y'] + next(n for n in nodes if n['id'] == el['nj'])['y'])/2 for el in elements]
mid_z = [(next(n for n in nodes if n['id'] == el['ni'])['z'] + next(n for n in nodes if n['id'] == el['nj'])['z'])/2 for el in elements]
el_labels = [str(el['id']) for el in elements]

fig.add_trace(go.Scatter3d(x=mid_x, y=mid_y, z=mid_z, mode='text', text=el_labels, textfont=dict(color='darkgreen', size=10), showlegend=False))

x_coords = [n['x'] for n in nodes]
y_coords = [n['y'] for n in nodes]
z_coords = [n['z'] for n in nodes]
fig.add_trace(go.Scatter3d(x=x_coords, y=y_coords, z=z_coords, mode='markers', marker=dict(size=4, color='black'), hoverinfo='text', text=[f"Node: {n['id']}" for n in nodes], showlegend=False))

fig.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=500)
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
    
    # Distribute approximate gravity loads on beams
    for el in current_elements:
        el['load_kN_m'] = 0.0
        if el['type'] == 'Beam':
            ni = next(n for n in nodes if n['id'] == el['ni'])
            nj = next(n for n in nodes if n['id'] == el['nj'])
            L = math.sqrt((nj['x']-ni['x'])**2 + (nj['y']-ni['y'])**2)
            # Simplistic tributary assignment based on length
            el['load_kN_m'] = q_factored * (L / 2.0) 

    # Lateral Loads
    total_weight = sum([el.get('load_kN_m', 0) * math.sqrt((next(n for n in nodes if n['id'] == el['nj'])['x']-next(n for n in nodes if n['id'] == el['ni'])['x'])**2 + (next(n for n in nodes if n['id'] == el['nj'])['y']-next(n for n in nodes if n['id'] == el['ni'])['y'])**2) for el in current_elements if el['type'] == 'Beam']) * 1.5
    V_base = lateral_coeff * total_weight
    
    floor_weights = {z: total_weight / num_stories for z in range(1, int(num_stories) + 1)}
    floor_heights = {z: z * h_story for z in range(1, int(num_stories) + 1)}
    sum_wh2 = sum([floor_weights[z] * (floor_heights[z]**2) for z in floor_weights])
    floor_forces = {z: V_base * (floor_weights[z] * (floor_heights[z]**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_weights}

    for n in nodes:
        if n['z'] > 0:
            nodes_this_floor = len([nd for nd in nodes if nd['floor'] == n['floor']])
            F_global[n['id'] * 6] += (floor_forces[n['floor']] / nodes_this_floor) if nodes_this_floor > 0 else 0

    # Assemble Global Matrices
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        
        # --- ORIENTATION LOGIC: Swap b and h if angle is 90 degrees ---
        if el.get('angle', 0) == 90:
            b, h = h, b 
            
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
    
    U_free = np.linalg.solve(K_global[np.ix_(free_dofs, free_dofs)], F_global[free_dofs])
    U_global = np.zeros(num_nodes * 6)
    U_global[free_dofs] = U_free
    
    # Extract Internal Forces
    for el in current_elements:
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
        T_matrix = get_transformation_matrix(ni_data, nj_data)
        
        b, h = map(lambda x: float(x)/1000, el['size'].split('x'))
        if el.get('angle', 0) == 90: b, h = h, b 
            
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
                'Status': 'Pass' if el['pass'] else 'Fail'
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
                'Status': 'Pass' if el['pass'] else 'Fail'
            }
                    
    return elements_to_design, design_status

if st.button("Run Custom Layout Analysis & Design", type="primary", use_container_width=True):
    with st.spinner("Analyzing custom grid framing..."):
        iteration = 1
        max_iters = 5 if auto_optimize else 1
        
        while iteration <= max_iters:
            try:
                elements, max_def = run_analysis(elements)
                elements, passed = perform_design(elements)
                
                if passed or not auto_optimize:
                    st.success(f"✅ Analysis Converged! Max Deflection: {max_def * 1000:.2f} mm")
                    break
                else:
                    for el in elements:
                        if not el['pass']:
                            b, h = map(int, el['size'].split('x'))
                            el['size'] = f"{b}x{h+50}" if el['type'] == 'Beam' else f"{b+50}x{h+50}"
                    iteration += 1
            except Exception as e:
                st.error(f"Solver Error (Likely Unstable Grid Geometry): {e}")
                st.stop()

        # Detailed Outputs
        st.divider()
        st.header("Results Summary")
        
        tab1, tab2 = st.tabs(["Columns", "Beams"])
        with tab1:
            st.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Column']), use_container_width=True)
                    with tab2:
            st.dataframe(pd.DataFrame([el['design_details'] for el in elements if el['type'] == 'Beam']), use_container_width=True)
