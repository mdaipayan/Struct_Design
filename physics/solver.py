import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import lsqr
from physics.stiffness import get_local_stiffness, get_transformation_matrix

class FEMSolver:
    def __init__(self, nodes, elements):
        self.nodes = nodes
        self.elements = elements
        self.num_nodes = len(nodes)
        self.ndof = self.num_nodes * 6
        
    def solve(self):
        if self.ndof == 0: 
            return np.zeros(0), False
            
        # Initialize Sparse Matrix for O(1) performance and memory safety
        K = lil_matrix((self.ndof, self.ndof))
        F = np.zeros(self.ndof)
        
        # 1. Global Assembly
        for el in self.elements:
            L = el.length
            k_loc = get_local_stiffness(el.material.E, el.material.G, el.section.A, el.section.Iy, el.section.Iz, el.section.J, L)
            T = get_transformation_matrix(el.ni, el.nj)
            
            # Transform to global
            k_glob = T.T @ k_loc @ T
            
            # Map degrees of freedom
            i_dof, j_dof = el.ni.id * 6, el.nj.id * 6
            dof_indices = [i_dof+i for i in range(6)] + [j_dof+i for i in range(6)]
            
            # Inject into sparse K matrix
            for row in range(12):
                for col in range(12):
                    K[dof_indices[row], dof_indices[col]] += k_glob[row, col]
            
            # Fixed End Forces (FEF) due to UDL on beams
            if el.type == 'Beam' and el.load_kN_m > 0:
                V = (el.load_kN_m * L) / 2.0
                M = (el.load_kN_m * L**2) / 12.0
                
                # Vertical Load applied to local Y axis
                F_loc = np.zeros(12)
                F_loc[1] = V      # Shear i
                F_loc[5] = M      # Moment i
                F_loc[7] = V      # Shear j
                F_loc[11] = -M    # Moment j
                
                F_glob = T.T @ F_loc
                for i in range(12):
                    F[dof_indices[i]] -= F_glob[i]
        
        # 2. Apply Boundary Conditions (Base Nodes are Fixed)
        fixed_dofs = [n.id * 6 + dof for n in self.nodes if n.is_fixed() for dof in range(6)]
        free_dofs = sorted(list(set(range(self.ndof)) - set(fixed_dofs)))
        
        K_free = K[np.ix_(free_dofs, free_dofs)].tocsr()
        F_free = F[free_dofs]
        
        # 3. Least-Squares Pseudo-Inverse Solver
        # This prevents the application from crashing if the user draws an unstable mechanism
        U_free = lsqr(K_free, F_free)[0]
        
        # 4. Reconstruct Global Displacements
        U_global = np.zeros(self.ndof)
        U_global[free_dofs] = U_free
        
        # 5. Extract Internal Forces & Local Displacements
        for el in self.elements:
            T = get_transformation_matrix(el.ni, el.nj)
            i_dof, j_dof = el.ni.id * 6, el.nj.id * 6
            
            # Extract local displacements
            u_glob = np.concatenate((U_global[i_dof:i_dof+6], U_global[j_dof:j_dof+6]))
            el.u_local = T @ u_glob
            
            # Reconstruct internal forces
            k_loc = get_local_stiffness(el.material.E, el.material.G, el.section.A, el.section.Iy, el.section.Iz, el.section.J, el.length)
            
            F_loc_ENL = np.zeros(12)
            if el.type == 'Beam' and el.load_kN_m > 0:
                V, M = (el.load_kN_m * el.length) / 2.0, (el.load_kN_m * el.length**2) / 12.0
                F_loc_ENL[1], F_loc_ENL[5], F_loc_ENL[7], F_loc_ENL[11] = V, M, V, -M
            
            el.f_internal = (k_loc @ el.u_local) + F_loc_ENL
            
        return U_global
