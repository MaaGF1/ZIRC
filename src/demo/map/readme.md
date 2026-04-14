# 地图 Demo使用说明

## 一、工程结构

```
map/
├── map.py               # 启动主程序
├── gflzirc/             # src/core/gflzirc
├── gflmaps/             # 前端网页文件夹 (包含 index.html, main.js, style.css, images 等)
└── GFLData/             # 离线数据文件夹 (包含 ch, en, jp 等目录)
```

其中：

1. `gflzirc`可以通过PYPI: `pip install gflzirc`安装；
2. `gflmaps`对应**MaaGF1/maps**仓库的内容，其中`main.js`需要替换为`src/demo/map/gflmaps/main.js`；
3. `GFLData`对应**MaaGF1/GFLData**中的数据。

## 二、依赖

### 2.1 基础部分

1. PYPI: `pywebview`、`pythonnet`
2. Webview2: `WebView2 Runtime`

### 2.2 Webview2

1. 前往微软官方 WebView2 下载页：
	`https://developer.microsoft.com/zh-cn/microsoft-edge/webview2/`
2. 在页面中下方的 **常青版独立安装程序 (Evergreen Standalone Installer)** 中，选择 **x64(或对应版本)** 进行下载。