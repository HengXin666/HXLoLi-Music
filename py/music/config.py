"""
配置模块

包含项目路径、文件扩展名、字体配置、常量等全局配置项
"""

from pathlib import Path

# 项目根目录 (py/music/config.py -> py/music -> py -> 项目根)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATIC_MUSIC_DIR = PROJECT_ROOT / "static" / "music"
FONTS_DIR = STATIC_MUSIC_DIR / "fonts"
INFO_DIR = PROJECT_ROOT / "static" / "info"  # 歌曲详细配置 (按需加载)
OUTPUT_FILE = PROJECT_ROOT / "playlist.json"
CACHE_FILE = PROJECT_ROOT / ".playlist_cache.json"

# 支持的音频文件扩展名
AUDIO_EXTENSIONS = {'.mp3', '.flac', '.ogg', '.m4a', '.wav', '.opus'}
# ASS 字幕扩展名
ASS_EXTENSIONS = {'.ass', '.ssa'}
# 封面图片扩展名
COVER_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
# 字体扩展名
FONT_EXTENSIONS = {'.ttf', '.otf', '.woff', '.woff2'}

# baseUrl: 空字符串, 生成相对路径 (前端会拼接 CDN 前缀)
BASE_URL = ""

# CJK Fallback 字体下载 URL (Noto Sans SC - 支持简体中文、日文假名和常用汉字)
CJK_FONT_NAME = "NotoSansSC-Regular.ttf"
CJK_FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"
)

# ASS 字体自动下载配置表
# key: ASS Style 行中的字体名 (精确匹配)
# value: dict
#   - file: 下载后保存的文件名
#   - url:  下载 URL
#   - note: 说明 (可选)
FONT_DOWNLOAD_MAP: dict[str, dict] = {
    "Rounded-L Mgen+ 1c bold": {
        "file": "rounded-mgenplus-1c-bold.ttf",
        "url": "https://github.com/itouhiro/mixfont-mplus-ipa/releases/download/v2013.0501/mgenplus-20130501.7z",
        # 压缩包内的文件路径 (相对于压缩包根目录)
        "archive_path": "rounded-mgenplus-1c-bold.ttf",
    },
}

# 封面图片的 MIME -> 扩展名映射
MIME_TO_EXT = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}

# ASS 预扫描分辨率 (与 C++ 版 _assParse.setFrameSize(1920, 1080) 一致)
PRESCAN_WIDTH = 1920
PRESCAN_HEIGHT = 1080
PRESCAN_FPS = 2  # 每秒采样帧数
