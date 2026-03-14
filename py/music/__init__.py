"""
HXLoLi-Music 播放列表生成工具包

子模块:
    config      - 路径常量、文件扩展名、字体配置
    cache       - 基于 MD5 的缓存机制
    metadata    - 音频元数据 & 封面提取
    ass_parser  - ASS 字幕解析 (字体、图片, 供渲染引擎虚拟 FS 加载)
    ass_prescan - ASS 预扫描 (ffmpeg bounds 计算)
    fonts       - 字体管理 (下载、查找)
    scanner     - 目录扫描、track 组装
"""
