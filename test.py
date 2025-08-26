import numpy as np

data = np.load(r"data\测试\平静\ppg\1756196871.944325f1000c57225.npz", allow_pickle=True)
frames = data['frames']
timestamps = data['timestamps']
meta_info = data['meta_info']
print(timestamps[:10])