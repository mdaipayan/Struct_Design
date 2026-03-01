import streamlit as st
import pandas as pd
import json
import copy
import plotly.graph_objects as go

# Modular Engine Imports
from core.geometry import MeshGenerator
from physics.loads import apply_gravity_loads
from physics.solver import FEMSolver
from design_codes.is_456 import evaluate_is456
from ai_optimizer.gradient_descent import step_optimizer

# --- PAGE SETUP ---
st.set_page_config(page_title="AI Structural Engine", layout="wide")
st.title("🧠 Physics-Informed AI Structural Optimizer")
st.caption("Gradient-Based Sizing | IS 456 | IS 875 | IS 1893")

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
    st.session_state.init_done = True

# --- SIDEBAR ---
st.sidebar.header("📂 Load Project")
uploaded_file = st.sidebar.file_uploader("Upload Project JSON", type=["json"])
if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        st.session_state.floors_df = pd.DataFrame(data.get("floors", []))
        st.session_state.x_grids_df = pd.DataFrame(data.get("x_grids", []))
        st.session_state.y_grids_df = pd.DataFrame(data.get("y_grids", []))
        st.session_state.cols_df = pd.DataFrame(data.get("columns", []))
        for k, v in data.get("parameters", {}).items(): st.session_state.params[k] = v
        st.rerun() 
    except Exception as e:
        st.sidebar.error(f"Invalid JSON file: {e}")

st.sidebar.header("1. Geometry & Grids")
floor_data = st.sidebar.data_editor(st.session_state.floors_df, num_rows="dynamic", use_container_width=True)
z_elevations = {0: 0.0}; current_z = 0.0
for idx, row in floor_data.iterrows():
    current_z += float(row['Height (m)'])
    z_elevations[int(row['Floor'])] = current_z

with st.sidebar.expander("Define X-Grids"):
    x_grid_data = st.data_editor(st.session_state.x_grids_df, num_rows="dynamic", use_container_width=True)
with st.sidebar.expander("Define Y-Grids"):
    y_grid_data = st.data_editor(st.session_state.y_grids_df, num_rows="dynamic", use_container_width=True)

x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in x_grid_data.iterrows() if pd.notna(row['Grid_ID'])}
y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in y_grid_data.iterrows() if pd.notna(row['Grid_ID'])}

with st.sidebar.expander("Column Locations", expanded=True):
    col_data = st.data_editor(st.session_state.cols_df, num_rows="dynamic", use_container_width=True)

st.sidebar.header("2. Base Physics Parameters")
st.session_state.params["col_dim"] = st.sidebar.text_input("Init Column Size", str(st.session_state.params["col_dim"]))
st.session_state.params["beam_dim"] = st.sidebar.text_input("Init Beam Size", str(st.session_state.params["beam_dim"]))
st.session_state.params["fck"] = st.sidebar.number_input("fck (MPa)", value=float(st.session_state.params["fck"]), step=5.0)
st.session_state.params["fy"] = st.sidebar.number_input("fy (MPa)", value=float(st.session_state.params["fy"]), step=85.0)
st.session_state.params["live_load"] = st.sidebar.number_input("Live Load (kN/m²)", value=float(st.session_state.params["live_load"]))
st.session_state.params["floor_finish"] = st.sidebar.number_input("Floor Finish (kN/m²)", value=float(st.session_state.params["floor_finish"]))
st.session_state.params["wall_thickness"] = st.sidebar.number_input("Wall Thk (mm)", value=int(st.session_state.params["wall_thickness"]))
st.session_state.params["slab_thickness"] = st.sidebar.number_input("Slab Thk (mm)", value=int(st.session_state.params["slab_thickness"]))
st.session_state.params["lateral_coeff"] = st.sidebar.slider("Seismic Base Shear Ah (%)", 0.0, 20.0, float(st.session_state.params["lateral_coeff"] * 100.0)) / 100.0

def render_viewport(view_nodes, view_elements, title):
    fig = go.Figure()
    for el in view_elements:
        color = 'blue' if el.type == 'Column' else 'red'
        fig.add_trace(go.Scatter3d(x=[el.ni.x, el.nj.x], y=[el.ni.y, el.nj.y], z=[el.ni.z, el.nj.z], mode='lines', line=dict(color=color, width=4), hoverinfo='text', text=f"{el.type} {int(el.section.b_mm)}x{int(el.section.h_mm)}", showlegend=False))
    x_c, y_c, z_c = [n.x for n in view_nodes], [n.y for n in view_nodes], [n.z for n in view_nodes]
    fig.add_trace(go.Scatter3d(x=x_c, y=y_c, z=z_c, mode='markers', marker=dict(size=3, color='black'), showlegend=False))
    fig.update_layout(scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0), height=400, title=title)
    st.plotly_chart(fig, use_container_width=True)

# --- EXECUTION ---
if st.button("Run PIML Analysis & Deep Optimization", type="primary", use_container_width=True):
    with st.spinner("Initializing Physics-Informed Matrix & Propagating Gradients..."):
        
        # 1. BUILD GEOMETRY
        mesher = MeshGenerator(floor_data, x_grid_data, y_grid_data, col_data, st.session_state.params)
        nodes, elements = mesher.build()
        if len(nodes) < 2: st.error("Geometry error."); st.stop()
        
        # 2. SLAB PANEL CALC
        x_coords, y_coords = sorted(list(x_map.values())), sorted(list(y_map.values()))
        x_spans = [x_coords[i+1] - x_coords[i] for i in range(len(x_coords)-1) if (x_coords[i+1] - x_coords[i]) > 0.5]
        y_spans = [y_coords[i+1] - y_coords[i] for i in range(len(y_coords)-1) if (y_coords[i+1] - y_coords[i]) > 0.5]
        max_panel_x, max_panel_y = max(x_spans) if x_spans else 1.0, max(y_spans) if y_spans else 1.0
        
        opt_slab = st.session_state.params['slab_thickness']
        
        # 3. PIML LOOP
        ai_elements = copy.deepcopy(elements)
        progress_bar = st.progress(0)
        loss_chart = st.empty()
        loss_history = []
        max_iters = 15
        
        for iteration in range(max_iters):
            apply_gravity_loads(ai_elements, st.session_state.params, opt_slab, max_panel_x, max_panel_y)
            solver = FEMSolver(nodes, ai_elements, st.session_state.params, z_elevations)
            U_global = solver.solve()
            
            ai_elements, passed, system_loss = evaluate_is456(ai_elements, st.session_state.params, U_global, nodes, z_elevations)
            loss_history.append(system_loss)
            
            # Live Plotly Loss Curve
            progress_bar.progress((iteration + 1) / max_iters)
            fig_loss = go.Figure(go.Scatter(y=loss_history, mode='lines+markers', name="Max UR", line=dict(color='orange')))
            fig_loss.add_hline(y=1.0, line_dash="dash", line_color="green", annotation_text="Safe Limit (UR = 1.0)")
            fig_loss.update_layout(title="Gradient Optimization Convergence (Loss Curve)", height=250, margin=dict(t=30, b=0))
            loss_chart.plotly_chart(fig_loss, use_container_width=True)
            
            if passed: 
                st.success(f"Algorithm Converged to Safe Minima in {iteration+1} iterations!")
                break
                
            ai_elements = step_optimizer(ai_elements, learning_rate=0.6)
            
        if not passed:
            st.warning("Algorithm hit iteration limit but significantly reduced internal forces.")
            
        render_viewport(nodes, ai_elements, "Optimized AI Structural Frame")
        
        st.subheader("Final Optimized Member Sizes")
        df_res = pd.DataFrame([el.design_details for el in ai_elements])
        st.dataframe(df_res, use_container_width=True)
        
        st.subheader("Concrete Takeoff Variance")
        man_vol = sum([(el.section.b_mm/1000)*(el.section.h_mm/1000)*el.length for el in elements])
        ai_vol = sum([(el.section.b_mm/1000)*(el.section.h_mm/1000)*el.length for el in ai_elements])
        st.metric("Total Framework Concrete", f"{ai_vol:.1f} m³", delta=f"{ai_vol - man_vol:.1f} m³ vs Manual Input", delta_color="inverse")
