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

st.sidebar.header("2. Section Properties")
col_dim = st.sidebar.text_input("Column Size (mm)", "300x450")
beam_dim = st.sidebar.text_input("Beam Size (mm)", "230x400")

# --- GEOMETRY GENERATOR ---
nodes = []
elements = []

# Generate Nodes
node_id = 0
for z in range(num_stories + 1):
    for y in range(bay_y + 1):
        for x in range(bay_x + 1):
            nodes.append({
                'id': node_id, 
                'x': x * L_x, 
                'y': y * L_y, 
                'z': z * h_story
            })
            node_id += 1

# Helper function to find node by coordinates
def get_node(x_idx, y_idx, z_idx):
    for n in nodes:
        if n['x'] == x_idx * L_x and n['y'] == y_idx * L_y and n['z'] == z_idx * h_story:
            return n['id']
    return None

# Generate Elements (Columns and Beams)
element_id = 0
for z in range(num_stories + 1):
    for y in range(bay_y + 1):
        for x in range(bay_x + 1):
            current_node = get_node(x, y, z)
            
            # Add Column (Z-direction)
            if z < num_stories:
                top_node = get_node(x, y, z + 1)
                if top_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': top_node, 'type': 'Column'})
                    element_id += 1
                    
            # Add Beam (X-direction)
            if z > 0 and x < bay_x:
                right_node = get_node(x + 1, y, z)
                if right_node is not None:
                    elements.append({'id': element_id, 'ni': current_node, 'nj': right_node, 'type': 'Beam'})
                    element_id += 1
                    
            # Add Beam (Y-direction)
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
        hoverinfo='text', text=f"{el['type']} ID: {el['id']}",
        showlegend=False
    ))

# Plot Nodes
x_coords = [n['x'] for n in nodes]
y_coords = [n['y'] for n in nodes]
z_coords = [n['z'] for n in nodes]

fig.add_trace(go.Scatter3d(
    x=x_coords, y=y_coords, z=z_coords,
    mode='markers', marker=dict(size=3, color='black'),
    hoverinfo='text', text=[f"Node: {n['id']}" for n in nodes],
    showlegend=False
))

fig.update_layout(
    scene=dict(xaxis_title='X (m)', yaxis_title='Y (m)', zaxis_title='Z (m)', aspectmode='data'),
    margin=dict(l=0, r=0, b=0, t=0), height=600
)

st.plotly_chart(fig, use_container_width=True)

# --- LOAD DEFINITION ---
st.divider()
st.header("3. Load Definition & Analysis")

colA, colB, colC = st.columns(3)
with colA:
    slab_thickness = st.number_input("Slab Thickness (mm)", value=150)
    dl_area = (slab_thickness / 1000.0) * 25.0 + 1.5 
    st.info(f"**Calculated Dead Load (DL):** {dl_area:.2f} kN/m²")
with colB:
    ll_area = st.number_input("Live Load (LL) (kN/m²)", value=3.0, step=0.5)
with colC:
    q_factored = 1.5 * (dl_area + ll_area)
    st.success(f"**Factored Area Load (q_u):** {q_factored:.2f} kN/m²")

# --- SOLVER EXECUTION ---
if st.button("Run Complete 3D Structural Analysis", type="primary", use_container_width=True):
    with st.spinner("Distributing loads, assembling matrices, and solving..."):
        
        # 1. Distribute Loads
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

        # 2. Helper Functions for Matrices
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

        # 3. Assemble Global Force Vector & Matrices
        num_nodes = len(nodes)
        F_global = np.zeros(num_nodes * 6)
        E_conc = 25e6
        G_conc = E_conc / (2 * (1 + 0.2)) 
        b, h = 0.3, 0.45
        A_sec, Iy_sec, Iz_sec = b * h, (b * h**3) / 12.0, (h * b**3) / 12.0
        J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))

        for el in elements:
            ni_data = next(n for n in nodes if n['id'] == el['ni'])
            nj_data = next(n for n in nodes if n['id'] == el['nj'])
            L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
            
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

        # 4. Global Assembly & Boundary Conditions
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

        # 5. Solve & Extract Internal Forces
        try:
            U_free = np.linalg.solve(K_free, F_free)
            U_global = np.zeros(num_nodes * 6)
            U_global[free_dofs] = U_free
            
            for el in elements:
                ni_data = next(n for n in nodes if n['id'] == el['ni'])
                nj_data = next(n for n in nodes if n['id'] == el['nj'])
                L = math.sqrt((nj_data['x']-ni_data['x'])**2 + (nj_data['y']-ni_data['y'])**2 + (nj_data['z']-ni_data['z'])**2)
                T_matrix = get_transformation_matrix(ni_data, nj_data)
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

            # Display Results
            st.success("🎉 Solver executed successfully! Nodal displacements & internal forces calculated.")
            
            col_res1, col_res2 = st.columns(2)
            with col_res1:
                st.metric("Max Nodal Displacement", f"{np.max(np.abs(U_global)) * 1000:.2f} mm")
            with col_res2:
                el_sample = elements[0]
                st.write(f"**Sample Internal Forces (Element 0 - {el_sample['type']}):**")
                st.code(f"Axial (N): {el_sample['F_internal'][0]:.2f} kN\nShear (Vz): {el_sample['F_internal'][2]:.2f} kN\nMoment (My): {el_sample['F_internal'][4]:.2f} kN-m")
                
        except np.linalg.LinAlgError:
            st.error("Solver Failed: Global Stiffness Matrix is singular. Check geometry/boundary conditions.")

        # =========================================================================
    # 7. IS 456:2000 Concrete Design Checks (Beams)
    # =========================================================================
    st.divider()
    st.header("4. IS 456:2000 Beam Design (Flexure)")
    
    # Material Properties
    col_mat1, col_mat2 = st.columns(2)
    with col_mat1:
        fck = st.number_input("Concrete Grade (fck in MPa)", value=25.0, step=5.0)
    with col_mat2:
        fy = st.number_input("Steel Grade (fy in MPa)", value=500.0, step=85.0)

    if st.button("Calculate Beam Reinforcement", type="primary"):
        beam_results = []
        
        # Beam Dimensions (Converting from mm to meters for moment capacity)
        # Using the default 230x400 mm section from your sidebar
        b_m = 0.230
        h_m = 0.400
        clear_cover = 0.030 # 30mm cover
        d_m = h_m - clear_cover
        
        # IS 456 Constant for Fe500 Limiting Moment
        # Mulim = 0.133 * fck * b * d^2
        Mu_lim_kNm = 0.133 * fck * b_m * (d_m**2) * 1000 
        
        for el in elements:
            if el['type'] == 'Beam':
                # Extract absolute maximum moment (converting from N-m to kN-m if needed, 
                # but our matrix was already in kN and m)
                M_y_i = abs(el['F_internal'][4])
                M_y_j = abs(el['F_internal'][10])
                Mu_max = max(M_y_i, M_y_j)
                
                status = ""
                Ast_req = 0.0
                
                # Minimum reinforcement criteria (IS 456 clause 26.5.1.1)
                Ast_min = (0.85 * b_m * d_m * 1e6) / fy
                
                if Mu_max == 0:
                    status = "No Load"
                    Ast_req = Ast_min
                elif Mu_max <= Mu_lim_kNm:
                    status = "Singly Reinforced"
                    # Solve IS 456 quadratic formula for Ast
                    # Mu = 0.87 * fy * Ast * d * (1 - (Ast * fy)/(b * d * fck))
                    # Rearranges to: a*(Ast^2) - b*(Ast) + c = 0
                    a = (0.87 * fy * fy) / (b_m * d_m * fck)
                    b_coef = 0.87 * fy * d_m
                    c = -Mu_max / 1000.0 # Convert Mu to MN-m for MPa consistency
                    
                    # Quadratic formula
                    discriminant = b_coef**2 - 4*a*c
                    if discriminant >= 0:
                        Ast_m2 = (b_coef - math.sqrt(discriminant)) / (2*a)
                        Ast_req = Ast_m2 * 1e6 # Convert to mm^2
                        Ast_req = max(Ast_req, Ast_min)
                    else:
                        status = "Math Error"
                else:
                    status = "Doubly Reinforced (or Resize)"
                    Ast_req = None # Requires top and bottom steel calculation
                    
                beam_results.append({
                    "Beam ID": el['id'],
                    "Max Moment (kN-m)": round(Mu_max, 2),
                    "Section Status": status,
                    "Req. Bottom Steel (mm²)": round(Ast_req, 2) if Ast_req else "N/A"
                })

        # Display results in a clean table
        st.dataframe(beam_results, use_container_width=True)
        st.info(f"**Note:** Limiting Moment Capacity ($M_{{u,lim}}$) for this section is **{Mu_lim_kNm:.2f} kN-m**.")
