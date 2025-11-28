from BaseDevice.DataSetLoader import DatasetLoader
import av
import cv2
"""
"0":'静坐',

==========================================

"mmwave": "milliwave",  ---毫米波
"mm": "milliwave",  ---毫米波
"rgb": "Logitech StreamCam",
"""
if __name__ == "__main__":
    loader = DatasetLoader(r"D:\work\multi_collector\release\mmwave-skeleton\data")
    print(loader.shape)                   #返回(最大被试数, 最大状态数, 最大设备数, 最大文件数)
    data = loader[0, "0", "rgb", 0]       #[被试id,状态,设备,文件]
    #data = loader[0, 0, 0, 0]            #支持索引，返回一个Dict[str, Any]
    #data = loader[0, "after", "mm", :]   #支持切片，返回一个List[Dict[str, Any]]
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
    print(loader.get_mapping(0, "0"))
    print(loader.get_mapping(0, 0, "mm"))
    print(loader.get_mapping(0, "0", "mm"))
    print(loader.get_mapping(0, "0", "mm"))

    # print(data["frames"][0][:,:,:3])

    # encode_type = "mjpeg"
    # codec = av.codec.CodecContext.create(encode_type, 'r')
    # for frame in data["frames"]:
    #     packet = av.packet.Packet(frame)
    #     frames = codec.decode(packet)
    #     frame = frames[0]
    #     img = frame.to_ndarray(format='bgr24')
    #     img = cv2.resize(img, (1280, 720))   
    #     cv2.imshow("frame", img)
    #     if cv2.waitKey(33) == ord('q'):
    #         break
    # cv2.destroyAllWindows()