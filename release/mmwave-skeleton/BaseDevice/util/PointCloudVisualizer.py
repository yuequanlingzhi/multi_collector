import numpy as np
import threading
import open3d as o3d
from .GridPlane import create_xz_grid_plane


class PointCloudVisualizer:
    """3D点云可视化器，封装所有3D绘制相关代码"""
    
    def __init__(self, width=640, height=480, 
                 point_size=5.0, background_color=None,
                 coord_size=2.0, grid_size=10.0, grid_resolution=0.5,
                 view_front=None, view_lookat=None, view_up=None, view_zoom=3.0):
        """
        初始化3D可视化器
        
        参数:
            width: 图像宽度
            height: 图像高度
            point_size: 点云点的大小
            background_color: 背景颜色，RGB格式[0-1]，默认白色
            coord_size: 坐标轴大小（米）
            grid_size: 网格大小（米）
            grid_resolution: 网格分辨率（米）
            view_front: 视角前方向量，默认[2, 1, -5]
            view_lookat: 观察目标点，默认[0, 2, 5]
            view_up: 上方向量，默认[0, 1, 0]
            view_zoom: 缩放值，默认3.0
        """
        self.width = width
        self.height = height
        self.point_size = point_size
        self.background_color = background_color if background_color is not None else np.array([1, 1, 1])
        
        # 可视化器对象
        self.vis = None
        self.pcd_combined = None  # 点云对象，用于更新
        self.released = False  # 标志位：是否已释放资源
        
        # 线程锁，保护Open3D可视化器的访问（Open3D不是线程安全的）
        self.lock = threading.Lock()
        
        # 视角参数
        self.view_front = view_front if view_front is not None else [2, 1, -5]
        self.view_lookat = view_lookat if view_lookat is not None else [0, 2, 5]
        self.view_up = view_up if view_up is not None else [0, 1, 0]
        self.view_zoom = view_zoom
        
        # 网格参数
        self.coord_size = coord_size
        self.grid_size = grid_size
        self.grid_resolution = grid_resolution
        
        # 初始化可视化器
        self._init_visualizer()
    
    def _init_visualizer(self):
        """初始化可视化器，添加坐标轴、原点和网格（只执行一次）"""
        # 创建可视化器（offscreen模式）
        self.vis = o3d.visualization.Visualizer()
        self.vis.create_window(visible=False, width=self.width, height=self.height)
        
        # 设置渲染选项
        render_option = self.vis.get_render_option()
        render_option.point_size = self.point_size
        render_option.background_color = self.background_color
        
        # 添加坐标轴（标注xyz坐标系）
        coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=self.coord_size)
        self.vis.add_geometry(coord_frame)
        
        # 在原点添加大红点（使用球体表示）
        origin_radius = self.coord_size * 0.15
        origin_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=origin_radius)
        origin_sphere.paint_uniform_color([1.0, 0.0, 0.0])  # 大红
        origin_sphere.translate([0, 0, 0])
        self.vis.add_geometry(origin_sphere)
        
        # 添加x-z平面的背景墙（地面网格）
        xz_grid = create_xz_grid_plane(
            position=0, 
            size=self.grid_size, 
            resolution=self.grid_resolution
        )
        if xz_grid:
            self.vis.add_geometry(xz_grid)
        
        # 创建空的点云对象（后续只更新这个对象）
        self.pcd_combined = o3d.geometry.PointCloud()
        self.vis.add_geometry(self.pcd_combined)
        
        # 设置视角
        view_ctl = self.vis.get_view_control()
        view_ctl.set_front(self.view_front)
        view_ctl.set_lookat(self.view_lookat)
        view_ctl.set_up(self.view_up)
        view_ctl.set_zoom(self.view_zoom)
        
        # 初始渲染
        self.vis.poll_events()
        self.vis.update_renderer()
    
    def update_points(self, points_dynamic=None, points_short=None, 
                     color_dynamic=None, color_short=None):
        """
        更新点云数据
        
        参数:
            points_dynamic: dynamic_high点云，numpy数组 shape (N, 3)，单位米
            points_short: short_micro_high点云，numpy数组 shape (M, 3)，单位米
            color_dynamic: dynamic_high点云颜色，RGB格式[0-1]，默认蓝色[0, 0, 1.0]
            color_short: short_micro_high点云颜色，RGB格式[0-1]，默认红色[1.0, 0, 0]
        """
        # 如果已释放，直接返回
        if self.released or self.vis is None or self.pcd_combined is None:
            return
        
        if color_dynamic is None:
            color_dynamic = [0.0, 0.0, 1.0]  # 蓝色
        if color_short is None:
            color_short = [1.0, 0.0, 0.0]  # 红色
        
        all_points = []
        all_colors = []
        
        # 添加dynamic_high点云
        if points_dynamic is not None and len(points_dynamic) > 0:
            all_points.append(points_dynamic)
            colors = np.tile(color_dynamic, (len(points_dynamic), 1))
            all_colors.append(colors)
        
        # 添加short_micro_high点云
        if points_short is not None and len(points_short) > 0:
            all_points.append(points_short)
            colors = np.tile(color_short, (len(points_short), 1))
            all_colors.append(colors)
        
        # 使用线程锁保护所有操作
        with self.lock:
            # 再次检查（可能在获取锁的过程中被释放）
            if self.released or self.vis is None or self.pcd_combined is None:
                return
            
            # 合并所有点云
            if len(all_points) > 0:
                combined_points = np.vstack(all_points)
                combined_colors = np.vstack(all_colors)
                
                # 更新点云对象（不重新创建，只更新数据）
                self.pcd_combined.points = o3d.utility.Vector3dVector(combined_points)
                self.pcd_combined.colors = o3d.utility.Vector3dVector(combined_colors)
            else:
                # 如果没有点，清空点云
                self.pcd_combined.points = o3d.utility.Vector3dVector(np.array([]).reshape(0, 3))
                self.pcd_combined.colors = o3d.utility.Vector3dVector(np.array([]).reshape(0, 3))
            
            # 更新可视化器中的点云（只更新，不重新添加）
            try:
                self.vis.update_geometry(self.pcd_combined)
            except RuntimeError:
                # Open3D窗口可能已被销毁
                pass
    
    def get_image(self):
        """
        获取当前渲染的RGB图像
        
        返回:
            numpy数组，shape (height, width, 3)，dtype uint8，RGB格式，如果已释放则返回None
        """
        # 如果已释放，返回None
        if self.released or self.vis is None:
            return None
        
        # 使用线程锁保护所有Open3D操作
        try:
            with self.lock:
                # 再次检查（可能在获取锁的过程中被释放）
                if self.released or self.vis is None:
                    return None
                
                # 更新渲染
                self.vis.poll_events()
                self.vis.update_renderer()
                
                # 捕获图像
                image = self.vis.capture_screen_float_buffer(do_render=True)
        except RuntimeError:
            # Open3D窗口可能已被销毁
            return None
        
        # 转换为numpy数组并转换为RGB格式 (0-255)
        image_np = np.asarray(image)
        # open3d返回的是RGB格式，但值在[0,1]范围，需要转换为[0,255]
        image_rgb = (image_np * 255).astype(np.uint8)
        
        return image_rgb
    
    def release(self):
        """释放可视化器资源"""
        self.released = True  # 先设置标志，防止后续调用
        with self.lock:
            if self.vis is not None:
                try:
                    self.vis.destroy_window()
                except:
                    pass
                self.vis = None
            self.pcd_combined = None

