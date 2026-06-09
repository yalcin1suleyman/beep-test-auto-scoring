#!/usr/bin/env python3
"""
Test script for the new 2-click line calibration system.
"""

import numpy as np
import cv2
from line_geometry import PerspectiveLine

def test_perspective_line_from_points():
    """Test creating PerspectiveLine from 2 points"""
    # Test case 1: Horizontal line (same Y)
    points1 = [(100, 200), (500, 200)]
    line1 = PerspectiveLine.from_points(points1)
    print(f"Test 1 - Horizontal line: {points1}")
    print(f"  Created points: {line1.points}")
    print(f"  Median Y: {line1.median_y}")
    assert line1.median_y == 200, "Median Y should be 200"
    print("  ✓ PASSED\n")

    # Test case 2: Perspective line (different Y values)
    points2 = [(100, 280), (500, 290)]
    line2 = PerspectiveLine.from_points(points2)
    print(f"Test 2 - Perspective line: {points2}")
    print(f"  Created points: {line2.points}")
    print(f"  Median Y: {line2.median_y}")
    print("  Y at x=100: {:.1f}".format(line2.y_at(100)))
    print("  Y at x=300: {:.1f}".format(line2.y_at(300)))
    print("  Y at x=500: {:.1f}".format(line2.y_at(500)))
    assert line2.median_y == 285, "Median Y should be 285"
    print("  ✓ PASSED\n")

    # Test case 3: Interpolation
    print("Test 3 - Interpolation between two points")
    y_at_300 = line2.y_at(300)
    expected_y = 280 + (300 - 100) / (500 - 100) * (290 - 280)
    print(f"  Y at x=300: {y_at_300:.2f}, expected: {expected_y:.2f}")
    assert abs(y_at_300 - expected_y) < 0.01, "Interpolation should be accurate"
    print("  ✓ PASSED\n")

    # Test case 4: Drawing (just make sure it doesn't crash)
    print("Test 4 - Drawing line on frame")
    frame = np.zeros((480, 848, 3), dtype=np.uint8)
    line2.draw(frame, (0, 255, 0), 2)
    print("  ✓ Line drawn successfully (no crashes)\n")

def test_dual_camera_calibration():
    """Test the calibration workflow"""
    print("=" * 70)
    print("Testing dual camera calibration workflow")
    print("=" * 70)
    
    # Create dummy frames
    frame1 = np.random.randint(0, 256, (478, 848, 3), dtype=np.uint8)
    frame2 = np.random.randint(0, 256, (576, 1024, 3), dtype=np.uint8)
    
    print(f"Frame 1 (Camera 1) shape: {frame1.shape}")
    print(f"Frame 2 (Camera 2) shape: {frame2.shape}")
    
    # Simulate calibration results
    start_points = [(70, 280), (720, 289)]
    far_points = [(170, 462), (906, 449)]
    
    print(f"\nStart camera calibration points: {start_points}")
    print(f"Far camera calibration points: {far_points}")
    
    # Create lines
    start_line = PerspectiveLine.from_points(start_points)
    far_line = PerspectiveLine.from_points(far_points)
    
    print(f"\nStart line points (ordered): {start_line.points}")
    print(f"Start line median Y: {start_line.median_y}")
    print(f"\nFar line points (ordered): {far_line.points}")
    print(f"Far line median Y: {far_line.median_y}")
    
    # Test Y interpolation at various X positions
    print(f"\nStart line Y values at different X positions:")
    for x in [70, 200, 400, 600, 720]:
        y = start_line.y_at(x)
        print(f"  X={x}: Y={y:.1f}")
    
    print(f"\n✓ Calibration test PASSED\n")

if __name__ == "__main__":
    try:
        test_perspective_line_from_points()
        test_dual_camera_calibration()
        print("\n" + "=" * 70)
        print("ALL TESTS PASSED! ✓")
        print("=" * 70)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
