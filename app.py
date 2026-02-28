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

# Plot Elements as lines
for el in elements:
    ni = next(n for n in nodes if n['id'] == el['ni'])
    nj = next(n for n in nodes if n['id'] == el['nj'])
    
    color = 'blue' if el['type'] == 'Column' else 'red'
    
    fig.add_trace(go.Scatter3d(
        x=[ni['x'], nj['x']],
        y=[ni['y'], nj['y']],
        z=[ni['z'], nj['z']],
        mode='lines',
        line=dict(color=color, width=4),
        hoverinfo='text',
        text=f"{el['type']} ID: {el['id']}",
        showlegend=False
    ))

# Plot Nodes as markers
x_coords = [n['x'] for n in nodes]
y_coords = [n['y'] for n in nodes]
z_coords = [n['z'] for n in nodes]

fig.add_trace(go.Scatter3d(
    x=x_coords, y=y_coords, z=z_coords,
    mode='markers',
    marker=dict(size=3, color='black'),
    hoverinfo='text',
    text=[f"Node: {n['id']}" for n in nodes],
    showlegend=False
))

# Configure Viewport
fig.update_layout(
    scene=dict(
        xaxis_title='X (m)',
        yaxis_title='Y (m)',
        zaxis_title='Z (m)',
        aspectmode='data' 
    ),
    margin=dict(l=0, r=0, b=0, t=0),
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# --- ACTION BUTTONS ---
st.divider()
colA, colB, colC = st.columns(3)
with colA:
    if st.button("1. Generate Load Combinations (IS 875/1893)", use_container_width=True):
        st.info("Load generator module to be connected.")
with colB:
    if st.button("2. Run 3D Direct Stiffness Solver", use_container_width=True, type="primary"):
        st.info(f"Solver will process {len(nodes)} nodes and {len(elements)} elements.")
with colC:
    if st.button("3. Execute IS Code Design Checks", use_container_width=True):
        st.info("Optimization and penalty evaluation to be connected.")


# --- SLAB LOAD DISTRIBUTION & MATRIX GENERATION ---
st.divider()
st.header("3. Slab Load Distribution & Matrix Assembly")
st.caption("Distributes floor loads, calculates 3D transformations, and builds element stiffness matrices.")

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

if st.button("Distribute Loads & Assemble Matrices", type="primary"):
    # 1. Determine panel dimensions
    Lx = min(L_x, L_y)
    Ly = max(L_x, L_y)
    aspect_ratio = Ly / Lx
    
    # 2. Calculate Equivalent UDLs
    if aspect_ratio > 2.0:
        w_long = q_factored * (Lx / 2.0)
        w_short = 0.0
        slab_type = "One-Way Slab"
    else:
        w_short = (q_factored * Lx) / 3.0
        w_long = (q_factored * Lx / 6.0) * (3.0 - (Lx / Ly)**2)
        slab_type = "Two-Way Slab"
        
    if L_x == Lx:
        w_x_beam = w_short
        w_y_beam = w_long
    else:
        w_x_beam = w_long
        w_y_beam = w_short
        
    # 3. Apply loads to the elements dictionary
    beams_loaded = 0
    for el in elements:
        el['load_kN_m'] = 0.0 # initialize
        if el['type'] == 'Beam':
            ni = next(n for n in nodes if n['id'] == el['ni'])
            nj = next(n for n in nodes if n['id'] == el['nj'])
            
            if abs(ni['y'] - nj['y']) < 0.01: # Parallel to X-axis
                is_perimeter_y = ni['y'] == 0 or ni['y'] == bay_y * L_y
                multiplier = 1.0 if is_perimeter_y else 2.0
                el['load_kN_m'] = w_x_beam * multiplier
                beams_loaded += 1
                
            elif abs(ni['x'] - nj['x']) < 0.01: # Parallel to Y-axis
                is_perimeter_x = ni['x'] == 0 or ni['x'] == bay_x * L_x
                multiplier = 1.0 if is_perimeter_x else 2.0
                el['load_kN_m'] = w_y_beam * multiplier
                beams_loaded += 1

    st.success(f"Successfully distributed {slab_type} loads to {beams_loaded} beams.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Internal X-Beam Load", f"{w_x_beam * 2:.2f} kN/m")
        st.caption("Perimeter: " + f"{w_x_beam:.2f} kN/m")
    with col2:
        st.metric("Internal Y-Beam Load", f"{w_y_beam * 2:.2f} kN/m")
        st.caption("Perimeter: " + f"{w_y_beam:.2f} kN/m")

    # =========================================================================
    # 4. Construct Global Matrices and Force Vectors
    # =========================================================================
    
    # --- HELPER FUNCTION: 3D TRANSFORMATION ---
    def get_transformation_matrix(ni, nj):
        dx = nj['x'] - ni['x']
        dy = nj['y'] - ni['y']
        dz = nj['z'] - ni['z']
        L = math.sqrt(dx**2 + dy**2 + dz**2)
        
        cx = dx / L
        cy = dy / L
        cz = dz / L
        
        lam = np.zeros((3, 3))
        
        if abs(cx) < 1e-6 and abs(cy) < 1e-6:
            if cz > 0: 
                lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
            else:      
                lam = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
        else: 
            D = math.sqrt(cx**2 + cy**2)
            lam = np.array([
                [cx, cy, cz],
                [-cx*cz/D, -cy*cz/D, D],
                [-cy/D, cx/D, 0]
            ])
            
        T = np.zeros((12, 12))
        T[0:3, 0:3] = lam
        T[3:6, 3:6] = lam
        T[6:9, 6:9] = lam
        T[9:12, 9:12] = lam
        return T

    # --- HELPER FUNCTION: LOCAL STIFFNESS MATRIX ---
    def get_local_stiffness_matrix(E, G, A, Iy, Iz, J, L):
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

    # 1. Initialize Global Force Vector (6 DOFs per node)
    num_nodes = len(nodes)
    F_global = np.zeros(num_nodes * 6)

    # 2. Iterate through elements to apply Stiffness and Nodal Loads
    for el in elements:
        
        # A. GEOMETRY & TRANSFORMATION
        ni_data = next(n for n in nodes if n['id'] == el['ni'])
        nj_data = next(n for n in nodes if n['id'] == el['nj'])
        
        dx = nj_data['x'] - ni_data['x']
        dy = nj_data['y'] - ni_data['y']
        dz = nj_data['z'] - ni_data['z']
        L = math.sqrt(dx**2 + dy**2 + dz**2)
        
        T_matrix = get_transformation_matrix(ni_data, nj_data)

        # B. STIFFNESS MATRIX
        E_conc = 25e6  # kN/m^2
        G_conc = E_conc / (2 * (1 + 0.2)) 
        
        # Generic 300x450 section for now
        b, h = 0.3, 0.45
        A_sec = b * h
        Iy_sec = (b * h**3) / 12.0
        Iz_sec = (h * b**3) / 12.0
        J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))
        
        k_local = get_local_stiffness_matrix(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        k_global = np.dot(np.dot(T_matrix.T, k_local), T_matrix)
        el['k_global'] = k_global

        # C. LOAD ASSEMBLY (ONLY LOADED BEAMS)
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            
            V = (w * L) / 2.0
            M = (w * L**2) / 12.0
            
            F_local_ENL = np.zeros(12)
            F_local_ENL[2] = -V        # Downward shear force Z (Node i)
            F_local_ENL[4] = -M        # Bending moment Y (Node i)
            F_local_ENL[8] = -V        # Downward shear force Z (Node j)
            F_local_ENL[10] = M        # Bending moment Y (Node j)
            
            P_global = np.dot(T_matrix.T, F_local_ENL)
            
            dof_i = el['ni'] * 6
            dof_j = el['nj'] * 6
            
            F_global[dof_i : dof_i + 6] += P_global[0:6]
            F_global[dof_j : dof_j + 6] += P_global[6:12]

    st.success(f"Successfully assigned stiffness matrices and assembled a {len(F_global)}x1 Global Force Vector.")
    
    
    # =========================================================================
    # 5. Global Assembly, Boundary Conditions, and Solver
    # =========================================================================
    
    # 1. Initialize empty Structure Global Stiffness Matrix (K_global)
    K_global = np.zeros((num_nodes * 6, num_nodes * 6))
    
    # 2. Assemble element matrices into the global matrix
    for el in elements:
        k_g = el['k_global']
        
        # Calculate the starting index for the DOFs of node i and node j
        i_dof = el['ni'] * 6
        j_dof = el['nj'] * 6
        
        # Extract the four 6x6 submatrices from the 12x12 element matrix
        k_ii = k_g[0:6, 0:6]
        k_ij = k_g[0:6, 6:12]
        k_ji = k_g[6:12, 0:6]
        k_jj = k_g[6:12, 6:12]
        
        # Add them to the corresponding locations in K_global
        K_global[i_dof:i_dof+6, i_dof:i_dof+6] += k_ii
        K_global[i_dof:i_dof+6, j_dof:j_dof+6] += k_ij
        K_global[j_dof:j_dof+6, i_dof:i_dof+6] += k_ji
        K_global[j_dof:j_dof+6, j_dof:j_dof+6] += k_jj

    st.success(f"Successfully assembled the {len(K_global)}x{len(K_global)} Structure Global Stiffness Matrix (K).")

    # 3. Apply Boundary Conditions (Fix all base nodes where z == 0)
    fixed_dofs = []
    for n in nodes:
        if n['z'] == 0:
            base_dof = n['id'] * 6
            fixed_dofs.extend(range(base_dof, base_dof + 6))
            
    # Determine which DOFs are free to move
    all_dofs = list(range(num_nodes * 6))
    free_dofs = list(set(all_dofs) - set(fixed_dofs))
    free_dofs.sort()
    
    # 4. Partition the matrices to isolate the free DOFs
    K_free = K_global[np.ix_(free_dofs, free_dofs)]
    F_free = F_global[free_dofs]
    
    # 5. SOLVE: U = K^-1 * F
    try:
        U_free = np.linalg.solve(K_free, F_free)
        
        # Reconstruct the full displacement vector U_global
        U_global = np.zeros(num_nodes * 6)
        U_global[free_dofs] = U_free
        
        st.success("🎉 Solver executed successfully! Nodal displacements calculated.")
        
        # Optional: Display maximum displacement for a quick sanity check
        max_disp_m = np.max(np.abs(U_global))
        max_disp_mm = max_disp_m * 1000
        st.info(f"**Maximum Nodal Displacement:** {max_disp_mm:.2f} mm")
        
    except np.linalg.LinAlgError:
        st.error("Solver Failed: The Global Stiffness Matrix is singular. Check geometry and boundary conditions.")


    
    # =========================================================================
    # 6. Calculate Element Internal Forces (Axial, Shear, Moment)
    # =========================================================================
    
    # We only want to run this if the solver succeeded and U_global exists
    if 'U_global' in locals():
        
        for el in elements:
            # A. Re-fetch Geometry & Section Properties
            ni_data = next(n for n in nodes if n['id'] == el['ni'])
            nj_data = next(n for n in nodes if n['id'] == el['nj'])
            
            dx = nj_data['x'] - ni_data['x']
            dy = nj_data['y'] - ni_data['y']
            dz = nj_data['z'] - ni_data['z']
            L = math.sqrt(dx**2 + dy**2 + dz**2)
            
            T_matrix = get_transformation_matrix(ni_data, nj_data)
            
            # Using the same concrete and section properties as before
            E_conc = 25e6
            G_conc = E_conc / (2 * (1 + 0.2))
            b, h = 0.3, 0.45
            A_sec = b * h; Iy_sec = (b * h**3) / 12.0; Iz_sec = (h * b**3) / 12.0
            J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))
            
            k_local = get_local_stiffness_matrix(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
            
            # B. Extract Global Displacements for this Element
            i_dof = el['ni'] * 6
            j_dof = el['nj'] * 6
            
            u_global = np.zeros(12)
            u_global[0:6] = U_global[i_dof : i_dof + 6]
            u_global[6:12] = U_global[j_dof : j_dof + 6]
            
            # C. Transform Global Displacements to Local Displacements
            u_local = np.dot(T_matrix, u_global)
            
            # D. Reconstruct Equivalent Nodal Loads to get Fixed End Moments (FEM = -ENL)
            F_local_ENL = np.zeros(12)
            w = el.get('load_kN_m', 0.0)
            if el['type'] == 'Beam' and w > 0:
                V = (w * L) / 2.0
                M = (w * L**2) / 12.0
                F_local_ENL[2] = -V        # Downward shear force Z (Node i)
                F_local_ENL[4] = -M        # Bending moment Y (Node i)
                F_local_ENL[8] = -V        # Downward shear force Z (Node j)
                F_local_ENL[10] = M        # Bending moment Y (Node j)
                
            # E. Final Internal Force Calculation: F = (k * u) - ENL
            F_internal = np.dot(k_local, u_local) - F_local_ENL
            
            # Store the 12x1 internal force vector in the element dictionary
            el['F_internal'] = F_internal

        st.success("Successfully extracted internal forces (Axial, Shear, Bending, Torsion) for all elements.")
        
        # Optional: Print out the forces for Element 0 as a quick sanity check
        el_0 = elements[0]
        st.write(f"**Sample Output for {el_0['type']} 0 (Node {el_0['ni']} to {el_0['nj']}):**")
        st.code(
            f"Axial Force (N):  {el_0['F_internal'][0]:.2f} kN\n"
            f"Shear Z (Vz):     {el_0['F_internal'][2]:.2f} kN\n"
            f"Moment Y (My):    {el_0['F_internal'][4]:.2f} kN-m"
        )
