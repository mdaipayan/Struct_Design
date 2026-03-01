import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import lsqr
from physics.stiffness import get_local_stiffness, get_transformation_matrix

class FEMSolver:
    def __init__(self, nodes, elements, params, z_elevations):
        self.nodes = nodes
        self.elements = elements
        self.params = params
        self.z_elevations = z_elevations
        self.num_nodes = len(nodes)
        self.ndof = self.num_nodes * 6
        
    def solve(self):
        if self.ndof == 0: return np.zeros(0)
            
        K = lil_matrix((self.ndof, self.ndof))
        F = np.zeros(self.ndof)
        
        # 1. Seismic Base Shear Injection
        seismic_wt = sum([(el.load_kN_m / 1.5) * el.length for el in self.elements if el.type == 'Beam'])
        v_base = self.params['lateral_coeff'] * seismic_wt
        num_stories = max([n.floor for n in self.nodes]) if self.nodes else 1
        
        floor_wts = {z: seismic_wt / num_stories for z in range(1, num_stories + 1)}
        sum_wh2 = sum([floor_wts[z] * (self.z_elevations.get(z, 0)**2) for z in floor_wts])
        floor_f = {z: v_base * (floor_wts[z] * (self.z_elevations.get(z, 0)**2)) / sum_wh2 if sum_wh2 > 0 else 0 for z in floor_wts}
        
        for n in self.nodes:
            if n.z > 0:
                floor_node_count = len([nd for nd in self.nodes if nd.floor == n.floor])
                F[n.id * 6] += (floor_f[n.floor] / floor_node_count) if floor_node_count > 0 else 0
        
        # 2. Matrix Assembly
        for el in self.elements:
            L = el.length
            k_loc = get_local_stiffness(el.material.E, el.material.G, el.section.A, el.section.Iy, el.section.Iz, el.section.J, L)
            T = get_transformation_matrix(el.ni, el.nj)
            k_glob = T.T @ k_loc @ T
            
            i_dof, j_dof = el.ni.id * 6, el.nj.id * 6
            dof_idx = [i_dof+i for i in range(6)] + [j_dof+i for i in range(6)]
            
            for row in range(12):
                for col in range(12):
                    K[dof_idx[row], dof_idx[col]] += k_glob[row, col]
            
            if el.type == 'Beam' and el.load_kN_m > 0:
                V, M = (el.load_kN_m * L) / 2.0, (el.load_kN_m * L**2) / 12.0
                F_loc = np.zeros(12); F_loc[1]=V; F_loc[5]=M; F_loc[7]=V; F_loc[11]=-M
                F_glob = T.T @ F_loc
                for i in range(12): F[dof_idx[i]] -= F_glob[i]
        
        # 3. Sparse Least-Squares Solve
        fixed_dofs = [n.id * 6 + dof for n in self.nodes if n.is_fixed() for dof in range(6)]
        free_dofs = sorted(list(set(range(self.ndof)) - set(fixed_dofs)))
        
        K_free = K[np.ix_(free_dofs, free_dofs)].tocsr()
        F_free = F[free_dofs]
        U_free = lsqr(K_free, F_free)[0]
        
        U_global = np.zeros(self.ndof)
        U_global[free_dofs] = U_free
        
        # 4. Recover Local Forces
        for el in self.elements:
            T = get_transformation_matrix(el.ni, el.nj)
            i_dof, j_dof = el.ni.id * 6, el.nj.id * 6
            u_glob = np.concatenate((U_global[i_dof:i_dof+6], U_global[j_dof:j_dof+6]))
            el.u_local = T @ u_glob
            
            k_loc = get_local_stiffness(el.material.E, el.material.G, el.section.A, el.section.Iy, el.section.Iz, el.section.J, el.length)
            F_loc_ENL = np.zeros(12)
            if el.type == 'Beam' and el.load_kN_m > 0:
                V, M = (el.load_kN_m * el.length) / 2.0, (el.load_kN_m * el.length**2) / 12.0
                F_loc_ENL[1]=V; F_loc_ENL[5]=M; F_loc_ENL[7]=V; F_loc_ENL[11]=-M
            el.f_internal = (k_loc @ el.u_local) + F_loc_ENL
            
        return U_global
