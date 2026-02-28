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
    # PASTE THE NEW CODE HERE:
    # 4. Construct Global Force Vector (F_global) using Equivalent Nodal Loads
    # =========================================================================
    import math

    # 1. Initialize Global Force Vector (6 DOFs per node)
    num_nodes = len(nodes)
    F_global = np.zeros(num_nodes * 6)

    # 2. Iterate through elements to apply Equivalent Nodal Loads
    for el in elements:
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
            
            # Initialize 12x1 local force vector for the element
            F_local_ENL = np.zeros(12)
            F_local_ENL[2] = -V        # Downward shear force Z (Node i)
            F_local_ENL[4] = -M        # Bending moment Y (Node i)
            F_local_ENL[8] = -V        # Downward shear force Z (Node j)
            F_local_ENL[10] = M        # Bending moment Y (Node j)
            
            # Placeholder for transformation: P_global = T^T * F_local_ENL
            P_global = F_local_ENL 
            
            # Assemble into Global Force Vector
            dof_i = el['ni'] * 6
            dof_j = el['nj'] * 6
            
            F_global[dof_i : dof_i + 6] += P_global[0:6]
            F_global[dof_j : dof_j + 6] += P_global[6:12]

    st.success(f"Successfully assembled Equivalent Nodal Loads into a {len(F_global)}x1 Global Force Vector.")

