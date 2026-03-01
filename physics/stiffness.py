import numpy as np
import math
from core.entities import Node

def get_local_stiffness(E: float, G: float, A: float, Iy: float, Iz: float, J: float, L: float) -> np.ndarray:
    """Generates the 12x12 local stiffness matrix for a 3D frame element."""
    k = np.zeros((12, 12))
    
    # Axial Stiffness (X-axis)
    k[0, 0] = k[6, 6] = E * A / L
    k[0, 6] = k[6, 0] = -E * A / L
    
    # Torsional Stiffness (About X-axis)
    k[3, 3] = k[9, 9] = G * J / L
    k[3, 9] = k[9, 3] = -G * J / L
    
    # Bending about Minor Axis (Iy) -> Affects local Z translations & Y rotations
    k[2, 2] = k[8, 8] = 12 * E * Iy / L**3
    k[2, 8] = k[8, 2] = -12 * E * Iy / L**3
    k[4, 4] = k[10, 10] = 4 * E * Iy / L
    k[4, 10] = k[10, 4] = 2 * E * Iy / L
    k[2, 4] = k[2, 10] = k[4, 2] = k[10, 2] = -6 * E * Iy / L**2
    k[8, 4] = k[8, 10] = k[4, 8] = k[10, 8] = 6 * E * Iy / L**2
    
    # Bending about Major Axis (Iz) -> Affects local Y translations & Z rotations
    k[1, 1] = k[7, 7] = 12 * E * Iz / L**3
    k[1, 7] = k[7, 1] = -12 * E * Iz / L**3
    k[5, 5] = k[11, 11] = 4 * E * Iz / L
    k[5, 11] = k[11, 5] = 2 * E * Iz / L
    k[1, 5] = k[1, 11] = k[5, 1] = k[11, 1] = 6 * E * Iz / L**2
    k[7, 5] = k[7, 11] = k[5, 7] = k[11, 7] = -6 * E * Iz / L**2
    
    # Mechanism Stabilizer: Add microscopic stiffness to prevent absolute zero singularity
    k += np.eye(12) * 1e-9 
    return k

def get_transformation_matrix(ni: Node, nj: Node) -> np.ndarray:
    """Generates the 12x12 transformation matrix from local to global coordinates."""
    dx, dy, dz = nj.x - ni.x, nj.y - ni.y, nj.z - ni.z
    L = math.sqrt(dx**2 + dy**2 + dz**2)
    if L == 0: return np.eye(12)
    
    cx, cy, cz = dx/L, dy/L, dz/L
    
    if abs(cx) < 1e-6 and abs(cy) < 1e-6: 
        # Vertical Member (Column)
        lam = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]) if cz > 0 else np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]])
    else: 
        # Horizontal / Diagonal Member
        D = math.sqrt(cx**2 + cy**2)
        lam = np.array([
            [cx, cy, cz], 
            [-cx*cz/D, -cy*cz/D, D], 
            [-cy/D, cx/D, 0]
        ])
        
    T = np.zeros((12, 12))
    for i in range(4): T[i*3:(i+1)*3, i*3:(i+1)*3] = lam
    return T
