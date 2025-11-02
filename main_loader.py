from BaseDevice.DataSetLoader import DatasetLoader
"""
"start": "平静",
"begin": "平静",
"static": "平静",
"before": "平静",
"sport": "运动",
"middle": "运动",
"after": "运动后",
"rest": "休息",
"0": "平静",
"1": "运动",
"2": "运动后",
"3": "休息",

==========================================

"side1": 'HD Pro Webcam C920-1', ---C920摄像头1
"side2": 'HD Pro Webcam C920-2', ---C920摄像头2
"frame120": "HD USB Camera", ---120帧摄像头
"120": "HD USB Camera", ---120帧摄像头
"ir": "LRCP  USB2.0",   ---红外摄像头
"front": "USB Camera",  ---深度摄像头RGB通道
"ppg": "ppg",  ---PPG
"uwb": "uwb",  ---超宽带
"mmwave": "milliwave",  ---毫米波
"mm": "milliwave",  ---毫米波
"depth": "orbbec_depth_camera",  ---深度摄像头
"""
if __name__ == "__main__":
    loader = DatasetLoader(r"E:\多模态data")
    print(loader.shape)                   #返回(最大被试数, 最大状态数, 最大设备数, 最大文件数)
    data = loader[0, "after", "mm", 0]    #[被试id,状态,设备,文件]
    #data = loader[0, 0, 0, 0]            #支持索引，返回一个Dict[str, Any]
    #data = loader[0, "after", "mm", :]   #支持切片，返回一个list[Dict[str, Any]]
    print(data["device_name"])            #设备名称
    print(data["frame_rate"])             #帧率
    print(data["frames"].shape)           #帧数
    print(data["timestamps"].shape)       #时间戳
    print(data["meta_info"])              #元数据

    """
    通过索引访问状态、设备、文件时，提供了get_mapping方法，返回一个字典，键为索引，值为名称
    >>> loader.get_mapping()  # 返回所有被试名称
    >>> loader.get_mapping(0)  # 返回被试0的所有状态名称
    >>> loader.get_mapping(0, "start")  # 返回被试0,状态"start"的所有设备名称
    >>> loader.get_mapping(0, 1, "uwb")  # 返回被试0,状态1,设备"uwb"的所有文件名称
    """
    print("="*100)
    print(loader.get_mapping())
    print(loader.get_mapping(0))
    print(loader.get_mapping(0, "start"))
    print(loader.get_mapping(0, 1, "uwb"))
    print(loader.get_mapping(0, "0", "uwb"))
    print(loader.get_mapping(0, "start", "side1"))