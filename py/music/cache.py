"""
缓存模块

基于文件 MD5 的缓存机制, 避免重复计算 (如 ffmpeg 预扫描等重操作)
"""

import json
import hashlib
from pathlib import Path

from .config import CACHE_FILE, STATIC_MUSIC_DIR, PROJECT_ROOT

# 运行时缓存, 由 load_cache() 填充
_cache_data: dict = {}
# 标记缓存是否有更新, 用于决定是否写入文件
_cache_dirty = False


def load_cache() -> None:
    """从磁盘加载缓存文件"""
    global _cache_data
    if CACHE_FILE.exists():
        try:
            _cache_data = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            print(f"[缓存] 已加载缓存: {len(_cache_data)} 条记录")
        except (json.JSONDecodeError, Exception) as e:
            print(f"[缓存] 缓存文件损坏, 将重新生成: {e}")
            _cache_data = {}
    else:
        print("[缓存] 无缓存文件, 将全量计算")
        _cache_data = {}


def save_cache() -> None:
    """将缓存写入磁盘"""
    if not _cache_dirty:
        return
    try:
        CACHE_FILE.write_text(
            json.dumps(_cache_data, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        print(f"[缓存] 已保存缓存: {len(_cache_data)} 条记录")
    except Exception as e:
        print(f"[缓存] 保存缓存失败: {e}")


def file_md5(filepath: Path) -> str:
    """计算文件内容的 MD5 哈希 (用于缓存判断)"""
    h = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def get_cache(namespace: str, key: str, file_hash: str) -> dict | None:
    """从缓存中获取数据

    Args:
        namespace: 缓存命名空间 (如 'metadata', 'ass_fonts', 'ass_bounds')
        key: 缓存键 (通常是文件相对路径)
        file_hash: 当前文件的 MD5 哈希

    Returns:
        缓存的数据 dict, 如果缓存未命中或哈希不匹配则返回 None
    """
    cache_key = f"{namespace}:{key}"
    entry = _cache_data.get(cache_key)
    if entry and entry.get('hash') == file_hash:
        return entry.get('data')
    return None


def set_cache(namespace: str, key: str, file_hash: str, data: dict) -> None:
    """写入缓存数据"""
    global _cache_dirty
    cache_key = f"{namespace}:{key}"
    _cache_data[cache_key] = {
        'hash': file_hash,
        'data': data,
    }
    _cache_dirty = True


def get_file_id(filepath: Path) -> str:
    """生成文件唯一 ID (基于相对路径的 hash)"""
    rel = filepath.relative_to(STATIC_MUSIC_DIR)
    return hashlib.md5(str(rel).encode()).hexdigest()[:12]


def path_to_url(filepath: Path) -> str:
    """将文件路径转换为 URL (相对于仓库根目录)"""
    rel = filepath.relative_to(PROJECT_ROOT)
    return f"/{rel.as_posix()}"
