import math

def evaluate_is456(elements, params, U_global, nodes, z_elevations):
    max_ur_system = 0.0
    fck = params['fck']
    fy = params['fy']
    num_stories = max([n.floor for n in nodes]) if nodes else 1
    
    # Calculate Storey Drifts
    floor_drifts = {}
    for z in range(1, num_stories + 1):
        nodes_z = [n for n in nodes if n.floor == z]
        nodes_prev = [n for n in nodes if n.floor == z - 1]
        
        max_x_z = max([abs(U_global[n.id*6]) for n in nodes_z]) if nodes_z else 0
        max_x_prev = max([abs(U_global[n.id*6]) for n in nodes_prev]) if nodes_prev else 0
        max_y_z = max([abs(U_global[n.id*6 + 1]) for n in nodes_z]) if nodes_z else 0
        max_y_prev = max([abs(U_global[n.id*6 + 1]) for n in nodes_prev]) if nodes_prev else 0
        
        drift = max(abs(max_x_z - max_x_prev), abs(max_y_z - max_y_prev))
        h_story = z_elevations.get(z, 3.0) - z_elevations.get(z-1, 0.0)
        floor_drifts[z] = drift / (0.004 * h_story) if h_story > 0 else 0
        
    for el in elements:
        b, h = el.section.b, el.section.h
        el.failure_mode = ""
        
        if el.type == 'Beam':
            Mu = max(abs(el.f_internal[5]), abs(el.f_internal[11]))
            Vu = max(abs(el.f_internal[1]), abs(el.f_internal[7]))
            
            Mu_lim = (0.138 if fy <= 415 else 0.133) * fck * (b*1000) * ((h*1000 - 40)**2) / 1e6
            tau_v = (Vu * 1000) / ((b*1000) * (h*1000 - 40)) if b > 0 else 0
            tau_c_max = 0.62 * math.sqrt(fck)
            
            L_mm = el.length * 1000
            # Absolute max midspan deflection (Classical formulation)
            delta_ss = (5 * el.load_kN_m * 1000 * (el.length**4)) / (384 * el.material.E * el.section.Iz) * 1000 if (el.material.E * el.section.Iz) != 0 else 0
            theta_1, theta_2 = el.u_local[5], el.u_local[11]
            defl = delta_ss + abs((L_mm / 8) * (theta_1 - theta_2))
            defl_limit = L_mm / 250.0
            
            ur_flex = Mu / Mu_lim if Mu_lim > 0 else 1.0
            ur_shear = tau_v / tau_c_max if tau_c_max > 0 else 1.0
            ur_def = defl / defl_limit if defl_limit > 0 else 1.0
            
            el.ur_max = max(ur_flex, ur_shear, ur_def)
            if ur_def > 1.0: el.failure_mode += "deflection "
            if ur_flex > 1.0: el.failure_mode += "flexure "
            if ur_shear > 1.0: el.failure_mode += "shear "
            
            el.design_details = {
                'ID': el.id, 'Floor': el.floor, 'Size (mm)': f"{int(b*1000)}x{int(h*1000)}",
                'Max UR': round(el.ur_max, 2), 'Mu(kN.m)': round(Mu, 1), 'Status': 'Safe' if el.ur_max <= 1.0 else el.failure_mode.strip()
            }
            
        elif el.type == 'Column':
            Pu = max(abs(el.f_internal[0]), abs(el.f_internal[6]))
            Mu = max(abs(el.f_internal[5]), abs(el.f_internal[11]))
            
            Ag = (b*1000) * (h*1000)
            Pu_lim = (0.4 * fck * Ag + 0.67 * fy * 0.04 * Ag) / 1000.0
            
            ur_axial = Pu / Pu_lim if Pu_lim > 0 else 1.0
            ur_drift = floor_drifts.get(el.floor, 0.0)
            
            el.ur_max = max(ur_axial, ur_drift)
            if ur_drift > 1.0: el.failure_mode += "drift "
            if ur_axial > 1.0: el.failure_mode += "axial_crushing "
            
            el.design_details = {
                'ID': el.id, 'Floor': el.floor, 'Size (mm)': f"{int(b*1000)}x{int(h*1000)}",
                'Max UR': round(el.ur_max, 2), 'Pu(kN)': round(Pu, 1), 'Status': 'Safe' if el.ur_max <= 1.0 else el.failure_mode.strip()
            }
            
        max_ur_system = max(max_ur_system, el.ur_max)
        
    return elements, max_ur_system <= 1.0, max_ur_system
