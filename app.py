import streamlit as st
import numpy as np
import plotly.graph_objects as go

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
# Placeholder for applying IS code sections to columns and beams
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


# It calculates the equivalent UDLs for every beam in your generated grid and assigns the loads directly to the element data. #
st.divider()
st.header("3. Slab Load Distribution (Yield Line Theory)")
st.caption("Distributes floor area loads onto the 3D frame beams as equivalent UDLs.")

colA, colB, colC = st.columns(3)
with colA:
    slab_thickness = st.number_input("Slab Thickness (mm)", value=150)
    # Dead load: thickness * density of concrete (25 kN/m^3) + 1.5 kN/m^2 floor finish
    dl_area = (slab_thickness / 1000.0) * 25.0 + 1.5 
    st.info(f"**Calculated Dead Load (DL):** {dl_area:.2f} $kN/m^2$")
with colB:
    ll_area = st.number_input("Live Load (LL) ($kN/m^2$)", value=3.0, step=0.5)
with colC:
    # Limit state factored load: 1.5(DL + LL)
    q_factored = 1.5 * (dl_area + ll_area)
    st.success(f"**Factored Area Load ($q_u$):** {q_factored:.2f} $kN/m^2$")

if st.button("Distribute Loads to Beams", type="primary"):
    # 1. Determine panel dimensions
    Lx = min(L_x, L_y)
    Ly = max(L_x, L_y)
    aspect_ratio = Ly / Lx
    
    # 2. Calculate Equivalent UDLs
    if aspect_ratio > 2.0:
        # One-way slab logic
        w_long = q_factored * (Lx / 2.0)
        w_short = 0.0
        slab_type = "One-Way Slab"
    else:
        # Two-way slab logic
        w_short = (q_factored * Lx) / 3.0
        w_long = (q_factored * Lx / 6.0) * (3.0 - (Lx / Ly)**2)
        slab_type = "Two-Way Slab"
        
    # Map calculated loads based on which axis is longer
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
            
            # Identify if beam is parallel to X or Y axis
            if abs(ni['y'] - nj['y']) < 0.01: # Parallel to X-axis
                # Internal beams take load from two adjacent slabs, perimeter beams take from one.
                # For simplicity in this base script, we assume a typical internal beam multiplier of 2.
                # A full script checks neighbor existence.
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
    # 4. Construct Global Force Vector (F_global) using Equivalent Nodal Loads
    # =========================================================================
    import math

    # --- NEW HELPER FUNCTION FOR 3D TRANSFORMATION ---
    def get_transformation_matrix(ni, nj):
        dx = nj['x'] - ni['x']
        dy = nj['y'] - ni['y']
        dz = nj['z'] - ni['z']
        L = math.sqrt(dx**2 + dy**2 + dz**2)
        
        cx = dx / L
        cy = dy / L
        cz = dz / L
        
        # 3x3 Direction Cosine Matrix (Lambda)
        lam = np.zeros((3, 3))
        
        # Special case for perfectly vertical columns to avoid division by zero
        if abs(cx) < 1e-6 and abs(cy) < 1e-6:
            if cz > 0: # Pointing UP
                lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
            else:      # Pointing DOWN
                lam = np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
        else: # Standard non-vertical members
            D = math.sqrt(cx**2 + cy**2)
            lam = np.array([
                [cx, cy, cz],
                [-cx*cz/D, -cy*cz/D, D],
                [-cy/D, cx/D, 0]
            ])
            
        # Build 12x12 Transformation Matrix (T)
        T = np.zeros((12, 12))
        T[0:3, 0:3] = lam
        T[3:6, 3:6] = lam
        T[6:9, 6:9] = lam
        T[9:12, 9:12] = lam
        
        return T
    # -------------------------------------------------
    # --- NEW HELPER FUNCTION FOR LOCAL STIFFNESS MATRIX ---
    def get_local_stiffness_matrix(E, G, A, Iy, Iz, J, L):
        k = np.zeros((12, 12))
        
        # 1. Axial terms (local X)
        k[0, 0] = k[6, 6] = E * A / L
        k[0, 6] = k[6, 0] = -E * A / L
        
        # 2. Torsion terms (local X rotation)
        k[3, 3] = k[9, 9] = G * J / L
        k[3, 9] = k[9, 3] = -G * J / L
        
        # 3. Bending about local Y (causes shear in local Z)
        k[2, 2] = k[8, 8] = 12 * E * Iy / L**3
        k[2, 8] = k[8, 2] = -12 * E * Iy / L**3
        k[4, 4] = k[10, 10] = 4 * E * Iy / L
        k[4, 10] = k[10, 4] = 2 * E * Iy / L
        k[2, 4] = k[2, 10] = k[4, 2] = k[10, 2] = -6 * E * Iy / L**2
        k[8, 4] = k[8, 10] = k[4, 8] = k[10, 8] = 6 * E * Iy / L**2
        
        # 4. Bending about local Z (causes shear in local Y)
        k[1, 1] = k[7, 7] = 12 * E * Iz / L**3
        k[1, 7] = k[7, 1] = -12 * E * Iz / L**3
        k[5, 5] = k[11, 11] = 4 * E * Iz / L
        k[5, 11] = k[11, 5] = 2 * E * Iz / L
        k[1, 5] = k[1, 11] = k[5, 1] = k[11, 1] = 6 * E * Iz / L**2
        k[7, 5] = k[7, 11] = k[5, 7] = k[11, 7] = -6 * E * Iz / L**2
        
        return k
    # ------------------------------------------------------
    # 1. Initialize Global Force Vector (6 DOFs per node)
    num_nodes = len(nodes)
    F_global = np.zeros(num_nodes * 6)

    # 2. Iterate through elements to apply Equivalent Nodal Loads
    for el in elements:
        # ... (Inside your existing: for el in elements:) ...
        
        # [PLACEHOLDER SECTION PROPERTIES]
        # Assuming M25 Concrete: E = 25000 MPa (kN/mm2 -> converted to kN/m2)
        E_conc = 25e6  # kN/m^2
        G_conc = E_conc / (2 * (1 + 0.2)) # Assuming Poisson's ratio = 0.2
        
        # Generic 300x450 section for everything right now (0.3m x 0.45m)
        b, h = 0.3, 0.45
        A_sec = b * h
        Iy_sec = (b * h**3) / 12.0
        Iz_sec = (h * b**3) / 12.0
        # Torsional constant (approximate for rectangle)
        J_sec = (b**3 * h) * (1/3 - 0.21*(b/h)*(1 - (b**4)/(12*h**4)))
        
        # 1. Get 12x12 Local Stiffness Matrix
        k_local = get_local_stiffness_matrix(E_conc, G_conc, A_sec, Iy_sec, Iz_sec, J_sec, L)
        
        # 2. Transform to Global Element Stiffness Matrix
        # k_global = T^T * k_local * T
        k_global = np.dot(np.dot(T_matrix.T, k_local), T_matrix)
        
        # Store it in the element dictionary for the global assembly step
        el['k_global'] = k_global
        
        w = el.get('load_kN_m', 0.0)
        if el['type'] == 'Beam' and w > 0:
            
            # Get node coordinates
            ni_data = next(n for n in nodes if n['id'] == el['ni'])
            nj_data = next(n for n in nodes if n['id'] == el['nj'])
            
            # Calculate element length (L)
            dx = nj_data['x'] - ni_data['x']
            dy = nj_data['y'] - ni_data['y']
            dz = nj_data['z'] - ni_data['z']
            L = math.sqrt(dx**2 + dy**2 + dz**2)
            
            # Calculate Local Equivalent Nodal Loads (ENL = -FEM)
            V = (w * L) / 2.0
            M = (w * L**2) / 12.0
            
            F_local_ENL = np.zeros(12)
            F_local_ENL[2] = -V        # Downward shear force Z (Node i)
            F_local_ENL[4] = -M        # Bending moment Y (Node i)
            F_local_ENL[8] = -V        # Downward shear force Z (Node j)
            F_local_ENL[10] = M        # Bending moment Y (Node j)
            
            # --- NEW TRANSFORMATION APPLICATION ---
            # Get the transformation matrix for this specific beam
            T_matrix = get_transformation_matrix(ni_data, nj_data)
            
            # Transform Local forces to Global forces (P_global = T^T * F_local)
            P_global = np.dot(T_matrix.T, F_local_ENL)
            # --------------------------------------
            
            # Assemble into Global Force Vector
            dof_i = el['ni'] * 6
            dof_j = el['nj'] * 6
            
            F_global[dof_i : dof_i + 6] += P_global[0:6]
            F_global[dof_j : dof_j + 6] += P_global[6:12]

    st.success(f"Successfully assembled Equivalent Nodal Loads into a {len(F_global)}x1 Global Force Vector.")

