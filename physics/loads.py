def apply_gravity_loads(elements, params, slab_thickness_mm, max_panel_x, max_panel_y):
    """Calculates tributary UDLs based on Yield Line Theory and applies them to beam elements."""
    # 1. Calculate Factored Area Load (q_u)
    dead_load = (slab_thickness_mm / 1000.0) * 25.0
    q_u = 1.5 * (params['live_load'] + params['floor_finish'] + dead_load)
    
    # 2. Yield Line Equivalent Load Distribution
    Lx = min(max_panel_x, max_panel_y)
    Ly = max(max_panel_x, max_panel_y)
    
    w_short = (q_u * Lx) / 3.0
    w_long = (q_u * Lx / 6.0) * (3.0 - (Lx / Ly)**2) if Ly > 0 else w_short

    # 3. Apply to Elements
    for el in elements:
        el.load_kN_m = 0.0
        if el.type == 'Beam':
            dx, dy = abs(el.nj.x - el.ni.x), abs(el.nj.y - el.ni.y)
            
            # Identify if beam spans the short or long direction of the slab panel
            if dx > dy: 
                slab_load = w_long if max_panel_x >= max_panel_y else w_short
            else: 
                slab_load = w_long if max_panel_y > max_panel_x else w_short
            
            # Wall Load (Assuming 3.0m story height for simplicity)
            is_secondary = not (el.ni.is_primary and el.nj.is_primary)
            h_story = 3.0 
            wall_udl = (params['wall_thickness'] / 1000.0) * 20.0 * max(0.1, (h_story - el.section.h)) if not is_secondary else 0.0
            
            # Element Self Weight
            self_wt = el.section.A * 25.0 * 1.5
            
            el.load_kN_m = slab_load + wall_udl + self_wt
