import numpy as np
import open3d as o3d


def create_xz_grid_plane(position=0, size=10.0, resolution=0.5, color=None):
    """
    创建x-z平面的网格（地面网格）
    
    参数:
        position: 平面的y坐标位置（默认0，即地面）
        size: 网格大小（米），默认10.0米
        resolution: 网格分辨率（米），默认0.5米
        color: 网格线颜色，RGB格式[0-1]，默认[0.5, 0.5, 0.5]（灰色）
    
    返回:
        o3d.geometry.LineSet: 网格线的LineSet对象
    """
    if color is None:
        color = [0.5, 0.5, 0.5]  # 默认灰色
    
    grid_lines = []
    grid_colors = []
    
    # x方向的网格线（沿z轴方向）
    num_lines_x = int(size / resolution) + 1
    for i in range(num_lines_x):
        x = -size / 2 + i * resolution
        grid_lines.append([[x, position, -size/2], [x, position, size/2]])
        grid_colors.append(color)
    
    # z方向的网格线（沿x轴方向）
    num_lines_z = int(size / resolution) + 1
    for i in range(num_lines_z):
        z = -size / 2 + i * resolution
        grid_lines.append([[-size/2, position, z], [size/2, position, z]])
        grid_colors.append(color)
    
    # 创建LineSet对象
    if len(grid_lines) > 0:
        grid_line_set = o3d.geometry.LineSet()
        points = []
        lines = []
        for line in grid_lines:
            start_idx = len(points)
            points.append(line[0])
            points.append(line[1])
            lines.append([start_idx, start_idx + 1])
        
        grid_line_set.points = o3d.utility.Vector3dVector(np.array(points))
        grid_line_set.lines = o3d.utility.Vector2iVector(np.array(lines))
        grid_line_set.colors = o3d.utility.Vector3dVector(np.array(grid_colors))
        return grid_line_set
    
    return None

