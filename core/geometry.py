import pandas as pd
from core.entities import Node, Element, Section, Material

class MeshGenerator:
    def __init__(self, floors_df, x_grids_df, y_grids_df, cols_df, base_params):
        self.floors = floors_df
        self.x_grids = x_grids_df
        self.y_grids = y_grids_df
        self.cols = cols_df
        self.params = base_params
        
        self.nodes = []
        self.elements = []
        self.material = Material(fck=self.params['fck'], fy=self.params['fy'])
        
    def safe_float(self, val, default=0.0):
        try:
            if pd.isna(val) or val is None or str(val).strip() == "": return default
            return float(val)
        except (ValueError, TypeError): return default

    def build(self):
        # 1. Map Z-Elevations
        z_elevations = {0: 0.0}
        current_z = 0.0
        for _, row in self.floors.iterrows():
            current_z += float(row['Height (m)'])
            z_elevations[int(row['Floor'])] = current_z
        num_stories = len(self.floors)

        # 2. Map X and Y Grids
        x_map = {str(row['Grid_ID']).strip(): float(row['X_Coord (m)']) for _, row in self.x_grids.iterrows() if pd.notna(row['Grid_ID'])}
        y_map = {str(row['Grid_ID']).strip(): float(row['Y_Coord (m)']) for _, row in self.y_grids.iterrows() if pd.notna(row['Grid_ID'])}

        # 3. Extract Primary Column Coordinates
        primary_xy = []
        for _, row in self.cols.iterrows():
            xg, yg = str(row.get('X_Grid', '')).strip(), str(row.get('Y_Grid', '')).strip()
            if xg in x_map and yg in y_map:
                x_val = x_map[xg] + self.safe_float(row.get('X_Offset (m)'))
                y_val = y_map[yg] + self.safe_float(row.get('Y_Offset (m)'))
                primary_xy.append({'x': x_val, 'y': y_val, 'angle': self.safe_float(row.get('Angle (deg)'))})

        # 4. Generate Node Objects
        nid = 0
        for floor_idx in range(num_stories + 1):
            z_val = z_elevations.get(floor_idx, 0.0)
            for pt in primary_xy:
                self.nodes.append(Node(id=nid, x=pt['x'], y=pt['y'], z=z_val, floor=floor_idx, is_primary=True))
                nid += 1

        # Retrieve Section Dimensions
        cb, ch = map(float, self.params['col_dim'].split('x'))
        bb, bh = map(float, self.params['beam_dim'].split('x'))

        # 5. Generate Column Elements
        eid = 0
        for z in range(num_stories):
            bottom_nodes = [n for n in self.nodes if n.floor == z]
            top_nodes = [n for n in self.nodes if n.floor == z + 1]
            for bn in bottom_nodes:
                tn = next((n for n in top_nodes if abs(n.x - bn.x) < 0.01 and abs(n.y - bn.y) < 0.01), None)
                if tn:
                    # Handle column orientation
                    pt_angle = next((pt['angle'] for pt in primary_xy if abs(pt['x'] - bn.x) < 0.01 and abs(pt['y'] - bn.y) < 0.01), 0.0)
                    actual_cb, actual_ch = (ch, cb) if pt_angle == 90 else (cb, ch)
                    sec = Section(b_mm=actual_cb, h_mm=actual_ch)
                    self.elements.append(Element(id=eid, ni=bn, nj=tn, type='Column', section=sec, material=self.material, angle_deg=pt_angle))
                    eid += 1

        # 6. Generate Beam Elements (with strict 0.05m tolerance)
        tolerance = 0.05 
        for z in range(1, num_stories + 1):
            floor_nodes = [n for n in self.nodes if n.floor == z]
            
            # X-Direction Beams
            y_groups = {}
            for n in floor_nodes:
                matched = False
                for y_key in y_groups.keys():
                    if abs(n.y - y_key) <= tolerance:
                        y_groups[y_key].append(n); matched = True; break
                if not matched: y_groups[n.y] = [n]
                    
            for y_key, group in y_groups.items():
                group = sorted(group, key=lambda k: k.x)
                for i in range(len(group)-1):
                    sec = Section(b_mm=bb, h_mm=bh)
                    self.elements.append(Element(id=eid, ni=group[i], nj=group[i+1], type='Beam', section=sec, material=self.material))
                    eid += 1
                    
            # Y-Direction Beams
            x_groups = {}
            for n in floor_nodes:
                matched = False
                for x_key in x_groups.keys():
                    if abs(n.x - x_key) <= tolerance:
                        x_groups[x_key].append(n); matched = True; break
                if not matched: x_groups[n.x] = [n]
                    
            for x_key, group in x_groups.items():
                group = sorted(group, key=lambda k: k.y)
                for i in range(len(group)-1):
                    sec = Section(b_mm=bb, h_mm=bh)
                    self.elements.append(Element(id=eid, ni=group[i], nj=group[i+1], type='Beam', section=sec, material=self.material))
                    eid += 1
                    
        return self.nodes, self.elements
