#!/usr/bin/env python3
"""
Kitchmatic Fleet Coordinate Visualization
Generates a PNG image showing all positions and waypoints
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, Circle
import numpy as np

# Set up the figure
fig, ax = plt.subplots(figsize=(16, 10))
ax.set_xlim(-0.1, 2.1)
ax.set_ylim(-0.1, 1.1)
ax.set_aspect('equal')
ax.grid(True, alpha=0.3, linestyle='--')
ax.set_xlabel('X (meters)', fontsize=12, fontweight='bold')
ax.set_ylabel('Y (meters)', fontsize=12, fontweight='bold')
ax.set_title('Kitchmatic Fleet Management - Coordinate Map\n(2.0m × 1.0m workspace)',
             fontsize=14, fontweight='bold')

# Define positions
positions = {
    # Pickup zone
    'pickup_spot': (0.47, 0.63),

    # Robot spawn/parking/charging
    'pinky1_spot': (0.585, 0.085),
    'pinky2_spot': (0.585, 0.255),
    'pinky3_spot': (0.585, 0.915),

    # Tables
    'table1': (1.785, 0.35),
    'table2': (1.415, 0.35),
    'table3': (1.785, 0.65),
    'table4': (1.415, 0.65),
    'table5': (1.235, 0.35),
    'table6': (0.865, 0.35),
    'table7': (1.235, 0.65),
    'table8': (0.865, 0.65),

    # Waypoints
    'point1': (0.78, 0.15),
    'point2': (0.78, 0.35),
    'point3': (0.78, 0.65),
    'point4': (0.78, 0.85),
    'point5': (1.325, 0.15),
    'point6': (1.325, 0.35),
    'point7': (1.325, 0.65),
    'point8': (1.325, 0.85),
    'point9': (1.85, 0.15),
    'point10': (1.85, 0.35),
    'point11': (1.85, 0.65),
    'point12': (1.85, 0.85),
    'point13': (0.585, 0.63),
}

# Lane connections
lanes = [
    # Vertical lanes (x = 0.78)
    ('point1', 'point2'), ('point2', 'point3'), ('point3', 'point4'),
    # Vertical lanes (x = 1.325)
    ('point5', 'point6'), ('point6', 'point7'), ('point7', 'point8'),
    # Vertical lanes (x = 1.85)
    ('point9', 'point10'), ('point10', 'point11'), ('point11', 'point12'),
    # Horizontal lanes (y = 0.15)
    ('point1', 'point5'), ('point5', 'point9'),
    # Horizontal lanes (y = 0.35) with table connections
    ('point2', 'table6'), ('table5', 'point6'), ('point6', 'table2'), ('table1', 'point10'),
    # Horizontal lanes (y = 0.65) with table connections
    ('point3', 'table8'), ('table7', 'point7'), ('point7', 'table4'), ('table3', 'point11'),
    # Horizontal lanes (y = 0.85)
    ('point4', 'point8'), ('point8', 'point12'),
    # Pickup zone connections
    ('pickup_spot', 'point13'), ('point13', 'point3'), ('point13', 'point2'),
    # Spawn/Charger connections
    ('pinky1_spot', 'point1'), ('pinky2_spot', 'point2'),
    ('pinky3_spot', 'point3'), ('pinky3_spot', 'point4'),
]

# Draw lanes (paths)
for start, end in lanes:
    x1, y1 = positions[start]
    x2, y2 = positions[end]
    ax.plot([x1, x2], [y1, y2], 'b-', alpha=0.3, linewidth=1.5, zorder=1)

# Draw map boundary (2.0m x 1.0m workspace)
boundary = patches.Rectangle((0, 0), 2.0, 1.0, linewidth=3,
                            edgecolor='black', facecolor='none',
                            linestyle='-', zorder=2)
ax.add_patch(boundary)

# Plot different position types with different colors/shapes

# 1. Pickup spot (green star)
x, y = positions['pickup_spot']
ax.plot(x, y, marker='*', markersize=20, color='green',
        markeredgecolor='darkgreen', markeredgewidth=2, zorder=5)
ax.text(x-0.08, y+0.05, 'Pickup\nSpot', fontsize=9, ha='center',
        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7))

# 2. Robot spawn/parking spots (blue squares)
for name in ['pinky1_spot', 'pinky2_spot', 'pinky3_spot']:
    x, y = positions[name]
    ax.plot(x, y, marker='s', markersize=15, color='blue',
            markeredgecolor='darkblue', markeredgewidth=2, zorder=5)
    label = name.replace('_spot', '').upper()
    offset_x = -0.12 if name == 'pinky3_spot' else -0.12
    ax.text(x+offset_x, y, label, fontsize=8, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7))

# 3. Tables (red circles)
for i in range(1, 9):
    name = f'table{i}'
    x, y = positions[name]
    circle = Circle((x, y), 0.04, color='red', alpha=0.6, zorder=4)
    ax.add_patch(circle)
    ax.plot(x, y, marker='o', markersize=12, color='red',
            markeredgecolor='darkred', markeredgewidth=2, zorder=5)
    ax.text(x, y-0.07, f'T{i}', fontsize=8, ha='center', fontweight='bold',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='lightsalmon', alpha=0.8))

# 4. Waypoints (orange triangles)
for i in range(1, 14):
    name = f'point{i}'
    x, y = positions[name]
    ax.plot(x, y, marker='^', markersize=10, color='orange',
            markeredgecolor='darkorange', markeredgewidth=1.5, zorder=4)
    ax.text(x, y+0.05, f'P{i}', fontsize=7, ha='center',
            bbox=dict(boxstyle='round,pad=0.2', facecolor='wheat', alpha=0.6))

# Add coordinate annotations for key positions
annotations = [
    ('pickup_spot', (0.47, 0.63), (-0.15, 0.1)),
    ('pinky1_spot', (0.585, 0.085), (-0.15, -0.08)),
    ('pinky2_spot', (0.585, 0.255), (0.1, 0.05)),
    ('pinky3_spot', (0.585, 0.915), (-0.15, 0.08)),
    ('table1', (1.785, 0.35), (0.08, -0.05)),
    ('point13', (0.585, 0.63), (0.1, 0.05)),
]

for name, (x, y), (dx, dy) in annotations:
    ax.annotate(f'({x:.3f}, {y:.3f})',
                xy=(x, y), xytext=(x+dx, y+dy),
                fontsize=7, color='black',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.5),
                arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0',
                               color='black', linewidth=0.5))

# Add legend
legend_elements = [
    plt.Line2D([0], [0], marker='*', color='w', markerfacecolor='green',
               markersize=15, label='Pickup Spot', markeredgecolor='darkgreen', markeredgewidth=2),
    plt.Line2D([0], [0], marker='s', color='w', markerfacecolor='blue',
               markersize=12, label='Robot Spawn/Charger', markeredgecolor='darkblue', markeredgewidth=2),
    plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='red',
               markersize=12, label='Table (Serving)', markeredgecolor='darkred', markeredgewidth=2),
    plt.Line2D([0], [0], marker='^', color='w', markerfacecolor='orange',
               markersize=10, label='Waypoint', markeredgecolor='darkorange', markeredgewidth=1.5),
    plt.Line2D([0], [0], color='blue', linewidth=2, alpha=0.5, label='Navigation Lane'),
]
ax.legend(handles=legend_elements, loc='upper left', fontsize=10, framealpha=0.9)

# Add robot radius indicator
robot_radius_demo = Circle((0.15, 0.92), 0.055, color='cyan', alpha=0.4, zorder=3)
ax.add_patch(robot_radius_demo)
ax.text(0.15, 0.92, 'Robot\nRadius\n5.5cm', fontsize=7, ha='center', va='center', fontweight='bold')

# Add scale bar
scale_start_x, scale_start_y = 0.05, 0.05
scale_length = 0.5  # 50cm
ax.plot([scale_start_x, scale_start_x + scale_length], [scale_start_y, scale_start_y],
        'k-', linewidth=3, zorder=10)
ax.plot([scale_start_x, scale_start_x], [scale_start_y-0.02, scale_start_y+0.02],
        'k-', linewidth=2, zorder=10)
ax.plot([scale_start_x + scale_length, scale_start_x + scale_length],
        [scale_start_y-0.02, scale_start_y+0.02], 'k-', linewidth=2, zorder=10)
ax.text(scale_start_x + scale_length/2, scale_start_y - 0.05, '50 cm',
        fontsize=9, ha='center', fontweight='bold')

# Add info box
info_text = """Map: real.png (410×210px)
Resolution: 0.005 m/pixel (5mm)
Origin: [-0.025, -0.025, 0.0]
Workspace: 2.0m × 1.0m"""
ax.text(1.7, 0.05, info_text, fontsize=8,
        bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgray', alpha=0.8),
        verticalalignment='bottom', family='monospace')

# Tight layout
plt.tight_layout()

# Save the figure
output_path = '/home/gw/kitchmatics/roscamp-repo-1/fms/config/coordinate_map.png'
plt.savefig(output_path, dpi=300, bbox_inches='tight')
print(f"Coordinate map saved to: {output_path}")

# Also save a high-res version
output_path_hires = '/home/gw/Documents/coordinate_map_hires.png'
plt.savefig(output_path_hires, dpi=600, bbox_inches='tight')
print(f"High-resolution map saved to: {output_path_hires}")

plt.close()
