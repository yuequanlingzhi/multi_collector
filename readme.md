# Multi_collerctor

Multi_collerctor是HCC用于采集数据集的多模态数据采集脚本，能控制多个设备的同时录制以及自动化保存。此版本依赖windows10系统。

# 部署

## 克隆仓库

```
https://github.com/yuequanlingzhi/multi_collector.git
cd multi_collector
```

## 创建并激活环境

```
conda create -n multi_collector python=3.6.13
```

```
conda activate multi_collector
```

## 安装依赖

1. pip 安装部分依赖

   ```
   pip install -r requirements.txt
   ```
2. 本地安装pyav

   ```
   pip install av-9.0.1-cp36-cp36m-win_amd64.whl
   ```
3. 安装pymoduleconnector(UWB 设备需求)

   ```
   cd uwb
   python setup.py install
   cd ../
   ```
4. 配置ffmpeg
   将下列路径添加至环境变量

   ```
   ./ffmpeg-4.3.2-2021-02-27-full_build-shared/bin
   ./ffmpeg-4.3.2-2021-02-27-full_build-shared/lib
   ./ffmpeg-4.3.2-2021-02-27-full_build-shared/include
   ```
