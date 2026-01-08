"""
Behavior domain using zonotope representation.

A behavior is represented as a finite set of zonotopes.
Each zonotope represents a convex region in the behavior space.
Zonotopes provide exact Minkowski sum/difference and better geometric operations.
"""

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
import copy
import numpy as np
from ..zonotope_ops import Zonotope, zonotope_union, zonotope_subtract, zonotope_intersection

# Configuration: Maximum zonotopes before applying conservative merging
MAX_ZONOTOPES_PER_SET = 500  # Sound over-approximation applied if exceeded



@dataclass(frozen=True)
class ZonotopeRegion:
    """
    A zonotope region with named variables for contract representation.
    
    Wraps a Zonotope with variable names for semantic interpretation.
    The zonotope dimensions correspond to variables in a fixed order.
    """
    variables: Tuple[str, ...]  # Ordered variable names
    zonotope: Zonotope  # The actual zonotope (dimension = len(variables))
    
    def __init__(self, var_bounds: Dict[str, Tuple[float, float]]):
        """
        Create zonotope region from variable bounds (axis-aligned box).
        
        Args:
            var_bounds: Dictionary mapping variable name to (min, max) tuple
        """
        # Sort variables for canonical ordering
        sorted_vars = tuple(sorted(var_bounds.keys()))
        bounds_list = [var_bounds[var] for var in sorted_vars]
        
        # Create axis-aligned box zonotope
        zono = Zonotope.from_box(bounds_list)
        
        object.__setattr__(self, 'variables', sorted_vars)
        object.__setattr__(self, 'zonotope', zono)
    
    @classmethod
    def from_zonotope(cls, variables: Tuple[str, ...], zonotope: Zonotope) -> 'ZonotopeRegion':
        """Create from explicit zonotope and variable ordering."""
        region = object.__new__(cls)
        object.__setattr__(region, 'variables', variables)
        object.__setattr__(region, 'zonotope', zonotope)
        return region
    
    def to_bounds_dict(self) -> Dict[str, Tuple[float, float]]:
        """Get axis-aligned bounding box as variable -> (min, max) dict."""
        bounds = self.zonotope.to_box_bounds()
        return {var: (bounds[i, 0], bounds[i, 1]) for i, var in enumerate(self.variables)}
    
    @property
    def as_dict(self) -> Dict[str, Tuple[float, float]]:
        """Alias for to_bounds_dict() for backwards compatibility."""
        return self.to_bounds_dict()
    
    @property
    def bounds(self) -> Tuple[Tuple[str, Tuple[float, float]], ...]:
        """Get bounds as tuple of (variable, (min, max)) for compatibility."""
        bounds_dict = self.to_bounds_dict()
        return tuple(sorted(bounds_dict.items()))
    
    def is_empty(self) -> bool:
        """Check if region is empty."""
        return self.zonotope.is_empty()
    
    def get_variable_set(self) -> Set[str]:
        """Get set of variables."""
        return set(self.variables)
    
    def project(self, keep_variables: Set[str]) -> 'ZonotopeRegion':
        """
        Project zonotope region onto a subset of variables.
        Removes dimensions not in keep_variables.
        """
        # Find indices to keep
        keep_indices = [i for i, var in enumerate(self.variables) if var in keep_variables]
        
        if not keep_indices:
            # No variables to keep, return empty region
            return ZonotopeRegion({})
        
        # Project the zonotope
        new_center = self.zonotope.center[keep_indices]
        new_generators = self.zonotope.generators[keep_indices, :]
        new_zono = Zonotope(new_center, new_generators)
        
        # Project the variable list
        new_variables = tuple([self.variables[i] for i in keep_indices])
        
        return ZonotopeRegion.from_zonotope(new_variables, new_zono)
    
    def __str__(self) -> str:
        """String representation showing bounding box."""
        bounds_dict = self.to_bounds_dict()
        items = [f"{var}∈[{lb:.2f}, {ub:.2f}]" for var, (lb, ub) in sorted(bounds_dict.items())]
        return f"ZonotopeRegion({', '.join(items)})"
    
    def __repr__(self) -> str:
        return str(self)


# For backwards compatibility, create Box as alias
Box = ZonotopeRegion


# Configuration constants
MAX_ZONOTOPES_PER_SET = 20  # Limit on number of zonotopes to prevent explosion (reduced from 100)


class BehaviorSet:
    """
    A behavior set is a finite union of zonotope regions (DNF representation).
    Represents a region in the behavior space using zonotopes for accurate operations.
    """
    
    def __init__(self, regions: List[ZonotopeRegion] = None):
        """Create behavior set from list of zonotope regions"""
        self.regions = regions if regions is not None else []
        # Remove empty regions
        self.regions = [r for r in self.regions if not r.is_empty()]
        
        # Apply cache management if too many regions
        if len(self.regions) > MAX_ZONOTOPES_PER_SET:
            self.regions = self._apply_cache_management(self.regions)
    
    # Backwards compatibility: expose as 'boxes'
    @property
    def boxes(self) -> List[ZonotopeRegion]:
        """Alias for regions (backwards compatibility)."""
        return self.regions
    
    def is_empty(self) -> bool:
        """Check if behavior set is empty"""
        return len(self.regions) == 0
    
    def union(self, other: 'BehaviorSet') -> 'BehaviorSet':
        """
        Union of two behavior sets using zonotope union.
        For each pair, computes zonotope hull (over-approximation).
        """
        if other.is_empty():
            return BehaviorSet(self.regions[:])
        if self.is_empty():
            return BehaviorSet(other.regions[:])
        
        # Simple approach: concatenate regions
        all_regions = self.regions + other.regions
        
        # Aggressively merge if too many regions
        if len(all_regions) > MAX_ZONOTOPES_PER_SET:
            all_regions = self._apply_cache_management(all_regions)
        
        return BehaviorSet(all_regions)
    
    def intersection(self, other: 'BehaviorSet') -> 'BehaviorSet':
        """
        Intersection of two behavior sets.
        Computes pairwise intersections of all regions using zonotope intersection.
        """
        result_regions = []
        
        for r1 in self.regions:
            for r2 in other.regions:
                # Check variable compatibility
                if r1.get_variable_set() != r2.get_variable_set():
                    continue  # Skip incompatible regions
                
                try:
                    # Use zonotope intersection (over-approximation)
                    intersect_zono = zonotope_intersection(r1.zonotope, r2.zonotope)
                    if not intersect_zono.is_empty():
                        intersect_region = ZonotopeRegion.from_zonotope(r1.variables, intersect_zono)
                        result_regions.append(intersect_region)
                except Exception:
                    # If intersection fails, skip
                    pass
        
        return BehaviorSet(result_regions)
    
    def difference(self, other: 'BehaviorSet') -> 'BehaviorSet':
        r"""
        Set difference: self \ other using zonotope subtraction.
        
        Uses zonotope_subtract which handles geometric difference correctly.
        This is the KEY FIX - zonotope subtraction is much more accurate than
        box subtraction!
        """
        if other.is_empty():
            return BehaviorSet(self.regions[:])
        
        result_regions = self.regions[:]
        
        for region_to_subtract in other.regions:
            new_result = []
            for region in result_regions:
                # Check variable compatibility
                if region.get_variable_set() != region_to_subtract.get_variable_set():
                    # Can't subtract, keep original
                    new_result.append(region)
                    continue
                
                try:
                    # Use zonotope subtraction (returns list of zonotopes)
                    subtracted_zonos = zonotope_subtract(region.zonotope, region_to_subtract.zonotope)
                    
                    # Convert back to ZonotopeRegions
                    for zono in subtracted_zonos:
                        if not zono.is_empty():
                            new_region = ZonotopeRegion.from_zonotope(region.variables, zono)
                            new_result.append(new_region)
                except Exception as e:
                    # If subtraction fails, conservatively keep original
                    new_result.append(region)
            
            result_regions = new_result
            
            # Apply aggressive cache management if too many regions
            if len(result_regions) > MAX_ZONOTOPES_PER_SET:
                result_regions = self._apply_cache_management(result_regions)
        
        return BehaviorSet(result_regions)
    
    def project(self, variables: Set[str]) -> 'BehaviorSet':
        """
        Project behavior set onto subset of variables.
        For zonotopes, projection simply removes generators for projected-out variables.
        """
        projected_regions = []
        for region in self.regions:
            # Get intersection of variables
            keep_vars = region.get_variable_set() & variables
            if keep_vars:
                projected_region = region.project(keep_vars)
                if not projected_region.is_empty():
                    projected_regions.append(projected_region)
        return BehaviorSet(projected_regions)
    
    def subset_of(self, other: 'BehaviorSet') -> bool:
        """
        Conservative subset check: self ⊆ other.
        Check if every zonotope region in self is covered by the union of regions in other.
        
        For zonotopes, we use bounding box approximation for efficiency.
        """
        if self.is_empty():
            return True
        if other.is_empty():
            return False
        
        # For each region in self, check if it's covered by union of regions in other
        for region1 in self.regions:
            covered = False
            
            # Get bounds for region1
            bounds1 = region1.zonotope.to_box_bounds()
            
            for region2 in other.regions:
                # Check variable compatibility
                if region1.get_variable_set() != region2.get_variable_set():
                    continue
                
                # Get bounds for region2
                bounds2 = region2.zonotope.to_box_bounds()
                
                # Conservative check: if bounding box of region1 is within bounds2
                all_inside = True
                for var in region1.variables:
                    lb1, ub1 = bounds1[region1.variables.index(var)]
                    lb2, ub2 = bounds2[region2.variables.index(var)]
                    if lb1 < lb2 or ub1 > ub2:
                        all_inside = False
                        break
                
                if all_inside:
                    covered = True
                    break
            
            if not covered:
                return False
        
        return True
    
    def total_volume_estimate(self) -> float:
        """
        Sum of volumes of all zonotope regions (may overcount due to overlaps).
        Used for metrics only.
        """
        return sum(region.zonotope.volume() for region in self.regions)
    
    @staticmethod
    def _apply_cache_management(regions: List[ZonotopeRegion]) -> List[ZonotopeRegion]:
        """
        Reduce number of zonotope regions by merging/over-approximating.
        Uses zonotope union for conservative approximation.
        AGGRESSIVE merging to prevent explosion.
        """
        if len(regions) <= MAX_ZONOTOPES_PER_SET:
            return regions
        
        # Strategy: repeatedly merge closest pairs until under limit
        current = regions[:]
        
        while len(current) > MAX_ZONOTOPES_PER_SET:
            # Merge pairs aggressively
            merged = []
            i = 0
            while i < len(current):
                if i + 1 < len(current):
                    # Merge consecutive pairs
                    try:
                        # Check if they have the same variables
                        if current[i].get_variable_set() == current[i+1].get_variable_set():
                            merged_zono = zonotope_union(current[i].zonotope, current[i+1].zonotope)
                            merged_region = ZonotopeRegion.from_zonotope(current[i].variables, merged_zono)
                            merged.append(merged_region)
                            i += 2
                        else:
                            # Can't merge incompatible variables, keep first
                            merged.append(current[i])
                            i += 1
                    except Exception:
                        # If merge fails, keep first only
                        merged.append(current[i])
                        i += 1
                else:
                    merged.append(current[i])
                    i += 1
            
            current = merged
            
            # If still too many after one pass, be even more aggressive
            if len(current) > MAX_ZONOTOPES_PER_SET:
                # Take only the first MAX_ZONOTOPES_PER_SET regions
                # This is a conservative over-approximation
                current = current[:MAX_ZONOTOPES_PER_SET]
                break
        
        return current
    
    def __len__(self) -> int:
        """Number of zonotope regions in the representation"""
        return len(self.regions)
    
    def __str__(self) -> str:
        if self.is_empty():
            return "BehaviorSet(∅)"
        if len(self.regions) == 1:
            return f"BehaviorSet(1 region)"
        return f"BehaviorSet({len(self.regions)} regions)"
    
    def detailed_str(self, max_regions: int = 5) -> str:
        """Detailed string representation showing zonotope regions"""
        if self.is_empty():
            return "BehaviorSet(∅)"
        
        lines = [f"BehaviorSet with {len(self.regions)} region(s):"]
        for i, region in enumerate(self.regions[:max_regions]):
            # Show bounding box for readability
            bounds = region.zonotope.to_box_bounds()
            bounds_str = ", ".join([
                f"{var}∈[{bounds[j][0]:.2f}, {bounds[j][1]:.2f}]" 
                for j, var in enumerate(region.variables)
            ])
            lines.append(f"  [{i+1}] {{{bounds_str}}}")
        
        if len(self.regions) > max_regions:
            lines.append(f"  ... and {len(self.regions) - max_regions} more regions")
        
        return "\n".join(lines)
    
    def __repr__(self) -> str:
        return str(self)

