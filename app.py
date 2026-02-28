import streamlit as st
import math

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="IS Code Structural Sizer", page_icon="🏗️", layout="wide")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏗️ Structural App")
st.sidebar.markdown("Preliminary sizing and load calculations per Indian Standards.")
app_mode = st.sidebar.radio(
    "Select Module:",
    ["Home", "RCC Slab & Beam (IS 456)", "RCC Column (IS 456)", "Steel Slenderness (IS 800)", "Wind Load (IS 875 Pt 3)"]
)

st.sidebar.divider()
st.sidebar.caption("Designed for preliminary architectural planning and structural conceptualization.")

# --- MODULE: HOME ---
if app_mode == "Home":
    st.title("Structural Conceptualization & Sizing Tool")
    st.markdown("""
    Welcome to the preliminary sizing and loading application. 
    
    Use the sidebar to navigate through the different modules:
    * **RCC Slab & Beam:** Calculate effective and overall depth based on span-to-depth ratios.
    * **RCC Column:** Estimate column dimensions using the tributary area and axial load method.
    * **Steel Slenderness:** Determine minimum radius of gyration ($r_{min}$) for truss and frame members to prevent buckling.
    * **Wind Load:** Calculate design wind pressure ($P_z$) for building facades and roofs.
    """)

# --- MODULE: RCC SLAB & BEAM ---
elif app_mode == "RCC Slab & Beam (IS 456)":
    st.header("RCC Slab & Beam Sizing (IS 456:2000)")
    st.caption("Based on deflection control criteria ($L/d$ ratios).")
    
    col1, col2 = st.columns(2)
    with col1:
        span_m = st.number_input("Clear Span (meters)", min_value=1.0, max_value=15.0, value=4.0, step=0.5)
    with col2:
        support = st.selectbox("Support Condition", ["Cantilever", "Simply Supported", "Continuous"])

    # Calculation
    span_mm = span_m * 1000
    ratios = {"Cantilever": 7, "Simply Supported": 20, "Continuous": 26}
    base_ratio = ratios.get(support, 20)
    
    # Assuming standard modification factor for preliminary sizing
    mod_factor = 1.2 
    allowable_ratio = base_ratio * mod_factor
    req_d = span_mm / allowable_ratio
    
    overall_D = req_d + 30 # Assuming 25mm clear cover + half bar dia
    practical_D = ((overall_D // 25) + 1) * 25 # Rounding up to nearest 25mm

    st.divider()
    st.subheader("Results:")
    st.info(f"**Required Effective Depth ($d$):** {req_d:.2f} mm")
    st.success(f"**Recommended Overall Depth ($D$):** {practical_D:.0f} mm")

# --- MODULE: RCC COLUMN ---
elif app_mode == "RCC Column (IS 456)":
    st.header("RCC Column Sizing")
    st.caption("Axial load estimation using the Tributary Area Method.")
    
    col1, col2 = st.columns(2)
    with col1:
        trib_area = st.number_input("Tributary Area ($m^2$)", min_value=1.0, value=16.0, step=1.0)
        floors = st.number_input("Number of Floors Supported", min_value=1, value=3, step=1)
        load_sqm = st.number_input("Avg. Load per Floor ($kN/m^2$)", value=12.0, step=1.0)
    with col2:
        fck = st.selectbox("Concrete Grade ($f_{ck}$)", [20, 25, 30, 35, 40], index=1)
        fy = st.selectbox("Steel Grade ($f_y$)", [415, 500, 550], index=1)
        steel_percent = st.slider("Assumed Steel % ($p_t$)", 0.8, 4.0, 1.0, 0.1)
    
    # Calculations
    total_load = trib_area * floors * load_sqm
    Pu_kN = 1.5 * total_load
    Pu_N = Pu_kN * 1000
    
    pt = steel_percent / 100
    stress_capacity = (0.4 * fck * (1 - pt)) + (0.67 * fy * pt)
    
    Ag_req = Pu_N / stress_capacity
    side_mm = math.sqrt(Ag_req)
    practical_side = math.ceil(side_mm / 25) * 25
    
    st.divider()
    st.subheader("Results:")
    st.info(f"**Factored Axial Load ($P_u$):** {Pu_kN:.2f} kN")
    st.success(f"**Preliminary Square Column Size:** {practical_side} mm $\\times$ {practical_side} mm")

# --- MODULE: STEEL SLENDERNESS ---
elif app_mode == "Steel Slenderness (IS 800)":
    st.header("Steel Member Sizer (IS 800:2007)")
    st.caption("Determines required radius of gyration based on slenderness limits.")
    
    length_mm = st.number_input("Effective Length, $KL$ (mm)", min_value=100, value=3000, step=100)
    member_type = st.radio(
        "Member Loading Condition", 
        [
            "Compression (Dead + Imposed Loads)", 
            "Tension (Standard tie member)", 
            "Tension (Subjected to wind/earthquake reversal)"
        ]
    )
    
    if "Compression" in member_type:
        max_lambda = 180
    elif "reversal" in member_type:
        max_lambda = 350
    else:
        max_lambda = 400
        
    r_min = length_mm / max_lambda
    
    st.divider()
    st.subheader("Results:")
    st.info(f"**Maximum Allowable Slenderness ($\\lambda$):** {max_lambda}")
    st.success(f"**Required Min. Radius of Gyration ($r_{{min}}$):** {r_min:.2f} mm")

# --- MODULE: WIND LOAD ---
elif app_mode == "Wind Load (IS 875 Pt 3)":
    st.header("Wind Load Calculation (IS 875 Part 3: 2015)")
    st.caption("Calculate Design Wind Pressure ($P_z$) for a given height.")
    
    col1, col2 = st.columns(2)
    with col1:
        Vb = st.number_input("Basic Wind Speed, $V_b$ (m/s)", min_value=33, max_value=55, value=44, step=1)
        k1 = st.number_input("Risk Coefficient ($k_1$)", value=1.0, step=0.01)
        k3 = st.number_input("Topography Factor ($k_3$)", value=1.0, step=0.01)
        k4 = st.number_input("Importance Factor ($k_4$)", value=1.0, step=0.01)
    with col2:
        terrain = st.selectbox("Terrain Category", [1, 2, 3, 4], index=1)
        height_z = st.number_input("Height of Structure, $z$ (m)", min_value=1.0, value=10.0, step=1.0)
    
    # Simplified k2 logic for demonstration (assuming Class A structure size)
    # In a full app, this would query a table or interpolation function
    k2_values = {
        1: {10: 1.05, 15: 1.09, 20: 1.12},
        2: {10: 1.00, 15: 1.05, 20: 1.07},
        3: {10: 0.91, 15: 0.97, 20: 1.01},
        4: {10: 0.80, 15: 0.80, 20: 0.80}
    }
    
    # Grabbing closest k2 value for simplicity in this baseline app
    closest_h = min([10, 15, 20], key=lambda x: abs(x - height_z))
    k2 = k2_values[terrain][closest_h]
    st.write(f"*Interpolated $k_2$ factor used for height ~{closest_h}m:* **{k2}**")

    # Calculations
    Vz = Vb * k1 * k2 * k3 * k4
    Pz_N = 0.6 * (Vz ** 2)
    Pz_kN = Pz_N / 1000

    st.divider()
    st.subheader("Results:")
    st.info(f"**Design Wind Speed ($V_z$):** {Vz:.2f} m/s")
    st.success(f"**Design Wind Pressure ($P_z$):** {Pz_kN:.3f} $kN/m^2$")
