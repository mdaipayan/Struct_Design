import math

def step_optimizer(elements, learning_rate=0.5):
    """Applies a gradient-based step to resize element sections based on Utilization Ratios."""
    for el in elements:
        if el.ur_max > 1.0:
            b, h = el.section.b_mm, el.section.h_mm
            
            if el.type == 'Beam':
                # Deflection/Flexure: Depth is exponentially effective (I ~ h^3)
                scale = el.ur_max ** (0.33 * learning_rate)
                h_new = int(h * scale)
                h_new = math.ceil(h_new / 50.0) * 50 # Snap to nearest 50mm
                
                if h_new > h: 
                    h = h_new
                if h / b > 3.0: 
                    b += 50 
            else:
                # Columns: Area matters most
                scale = el.ur_max ** (0.5 * learning_rate)
                h_new = int(h * scale)
                h_new = math.ceil(h_new / 50.0) * 50
                if h_new > h: 
                    h = h_new
                    b += 50 
            
            # Master Architectural Safety Constraints
            b, h = min(b, 1000), min(h, 1200)
            
            el.section.b_mm = b
            el.section.h_mm = h
            
    return elements
