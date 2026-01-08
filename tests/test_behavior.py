"""
Tests for BehaviorSet operations.

Validates union, intersection, difference, projection, and subset operations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.contracts import Box, BehaviorSet


def test_box_creation():
    """Test basic box creation and properties"""
    box = Box({'x': (0.0, 10.0), 'y': (5.0, 15.0)})
    assert box.variables == {'x', 'y'}
    assert not box.is_empty()
    assert box.as_dict == {'x': (0.0, 10.0), 'y': (5.0, 15.0)}


def test_box_empty():
    """Test empty box detection"""
    empty_box = Box({'x': (10.0, 5.0)})  # lb > ub
    assert empty_box.is_empty()


def test_box_intersection():
    """Test box intersection"""
    box1 = Box({'x': (0.0, 10.0), 'y': (0.0, 10.0)})
    box2 = Box({'x': (5.0, 15.0), 'y': (5.0, 15.0)})
    
    intersect = box1.intersection_with(box2)
    assert intersect is not None
    assert intersect.as_dict == {'x': (5.0, 10.0), 'y': (5.0, 10.0)}


def test_box_no_intersection():
    """Test non-intersecting boxes"""
    box1 = Box({'x': (0.0, 5.0)})
    box2 = Box({'x': (10.0, 15.0)})
    
    intersect = box1.intersection_with(box2)
    assert intersect is None


def test_box_subset():
    """Test box subset relation"""
    box1 = Box({'x': (2.0, 8.0), 'y': (3.0, 7.0)})
    box2 = Box({'x': (0.0, 10.0), 'y': (0.0, 10.0)})
    
    assert box1.subset_of(box2)
    assert not box2.subset_of(box1)


def test_box_projection():
    """Test box projection"""
    box = Box({'x': (0.0, 10.0), 'y': (5.0, 15.0), 'z': (2.0, 8.0)})
    projected = box.project({'x', 'y'})
    
    assert projected.variables == {'x', 'y'}
    assert projected.as_dict == {'x': (0.0, 10.0), 'y': (5.0, 15.0)}


def test_behavior_set_union():
    """Test BehaviorSet union removes duplicates"""
    box1 = Box({'x': (0.0, 10.0)})
    box2 = Box({'x': (5.0, 15.0)})
    box3 = Box({'x': (0.0, 10.0)})  # Duplicate of box1
    
    bs1 = BehaviorSet([box1, box2])
    bs2 = BehaviorSet([box2, box3])
    
    union = bs1.union(bs2)
    # Should have 2 unique boxes (box1/box3 are same, box2)
    assert len(union.boxes) == 2


def test_behavior_set_intersection():
    """Test BehaviorSet intersection"""
    box1 = Box({'x': (0.0, 10.0)})
    box2 = Box({'x': (5.0, 15.0)})
    
    bs1 = BehaviorSet([box1])
    bs2 = BehaviorSet([box2])
    
    intersect = bs1.intersection(bs2)
    assert len(intersect.boxes) == 1
    assert intersect.boxes[0].as_dict == {'x': (5.0, 10.0)}


def test_behavior_set_difference():
    """Test BehaviorSet difference"""
    box1 = Box({'x': (0.0, 20.0)})
    box2 = Box({'x': (5.0, 10.0)})  # Subset to subtract
    
    bs1 = BehaviorSet([box1])
    bs2 = BehaviorSet([box2])
    
    diff = bs1.difference(bs2)
    # Should have 2 boxes: [0,5] and [10,20]
    assert len(diff.boxes) >= 2


def test_behavior_set_subset():
    """Test BehaviorSet subset relation"""
    box1 = Box({'x': (2.0, 8.0)})
    box2 = Box({'x': (0.0, 10.0)})
    
    bs1 = BehaviorSet([box1])
    bs2 = BehaviorSet([box2])
    
    assert bs1.subset_of(bs2)
    assert not bs2.subset_of(bs1)


def test_behavior_set_projection():
    """Test BehaviorSet projection"""
    box1 = Box({'x': (0.0, 10.0), 'y': (5.0, 15.0)})
    box2 = Box({'x': (5.0, 15.0), 'y': (0.0, 10.0)})
    
    bs = BehaviorSet([box1, box2])
    projected = bs.project({'x'})
    
    assert len(projected.boxes) == 2
    for box in projected.boxes:
        assert box.variables == {'x'}


if __name__ == '__main__':
    # Run tests
    test_box_creation()
    test_box_empty()
    test_box_intersection()
    test_box_no_intersection()
    test_box_subset()
    test_box_projection()
    test_behavior_set_union()
    test_behavior_set_intersection()
    test_behavior_set_difference()
    test_behavior_set_subset()
    test_behavior_set_projection()
    print("✓ All BehaviorSet tests passed")
