from dataclasses import dataclass, field
import math
import numpy as np

@dataclass
class Node:
    id: int
    x: float
    y: float
    z: float
    floor: int
    is_primary: bool = True
    
    # 6 Degrees of Freedom (Translations: UX, UY, UZ | Rotations: RX, RY, RZ)
    u_global: np.ndarray = field(default_factory=lambda: np.zeros(6))
    
    def is_fixed(self) -> bool:
        """Nodes at Z=0 are considered fully fixed to the foundation."""
        return self.z == 0.0

@dataclass
class Material:
    fck: float  # Concrete compressive strength (MPa)
    fy: float   # Steel yield strength (MPa)
    
    @property
    def E(self) -> float:
        """Young's Modulus of Concrete per IS 456 (kN/m^2)"""
        return 5000 * math.sqrt(self.fck) * 1000
    
    @property
    def G(self) -> float:
        """Shear Modulus of Concrete (kN/m^2) assuming Poisson's ratio = 0.2"""
        return self.E / (2 * (1 + 0.2))

@dataclass
class Section:
    b_mm: float
    h_mm: float
    
    @property
    def b(self) -> float: return self.b_mm / 1000.0
    
    @property
    def h(self) -> float: return self.h_mm / 1000.0

    @property
    def A(self) -> float: return self.b * self.h
    
    @property
    def Iy(self) -> float:
        """Minor axis moment of inertia"""
        return (self.h * self.b**3) / 12.0
        
    @property
    def Iz(self) -> float:
        """Major axis moment of inertia"""
        return (self.b * self.h**3) / 12.0
        
    @property
    def J(self) -> float:
        """Torsional constant for rectangular section (Roark's formula)"""
        dim_min, dim_max = min(self.b, self.h), max(self.b, self.h)
        return (dim_min**3 * dim_max) * (1/3 - 0.21 * (dim_min/dim_max) * (1 - (dim_min**4) / (12 * dim_max**4)))

@dataclass
class Element:
    id: int
    ni: Node
    nj: Node
    type: str  # 'Beam' or 'Column'
    section: Section
    material: Material
    angle_deg: float = 0.0
    
    # Analysis Results
    load_kN_m: float = 0.0
    f_internal: np.ndarray = field(default_factory=lambda: np.zeros(12))
    u_local: np.ndarray = field(default_factory=lambda: np.zeros(12))
    ur_max: float = 0.0
    failure_mode: str = ""
    
    @property
    def length(self) -> float:
        return math.sqrt((self.nj.x - self.ni.x)**2 + (self.nj.y - self.ni.y)**2 + (self.nj.z - self.ni.z)**2)
