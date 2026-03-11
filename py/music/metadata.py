"""
音频元数据提取模块

从音频文件中提取标题、艺术家、时长, 以及嵌入的封面图片
"""

from pathlib import Path

from .config import COVER_EXTENSIONS, MIME_TO_EXT, STATIC_MUSIC_DIR
from .cache import get_cache, set_cache

try:
    from mutagen import File as MutagenFile
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    from mutagen.wave import WAVE
    from mutagen.oggopus import OggOpus
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("[警告] 未安装 mutagen, 将使用文件名作为元数据")
    print("  安装: cd py && uv sync")
    print()


def _extract_metadata_impl(filepath: Path) -> dict:
    """从音频文件中提取元数据 (标题、艺术家、时长) — 实际计算逻辑"""
    title = filepath.stem  # 默认使用文件名
    artist = "Unknown"
    duration = 0

    if not HAS_MUTAGEN:
        return {"title": title, "artist": artist, "duration": duration}

    try:
        audio = MutagenFile(str(filepath))
        if audio is None:
            return {"title": title, "artist": artist, "duration": duration}

        # 获取时长
        if hasattr(audio, 'info') and hasattr(audio.info, 'length'):
            duration = round(audio.info.length, 2)

        # 根据不同格式提取标签
        if isinstance(audio, MP3):
            # ID3 tags
            if audio.tags:
                title = str(audio.tags.get('TIT2', title))
                artist = str(audio.tags.get('TPE1', artist))
        elif isinstance(audio, FLAC):
            title = audio.get('title', [title])[0]
            artist = audio.get('artist', [artist])[0]
        elif isinstance(audio, (OggVorbis, OggOpus)):
            title = audio.get('title', [title])[0]
            artist = audio.get('artist', [artist])[0]
        elif isinstance(audio, MP4):
            # iTunes-style tags
            title = audio.tags.get('\xa9nam', [title])[0] if audio.tags else title
            artist = audio.tags.get('\xa9ART', [artist])[0] if audio.tags else artist
        elif isinstance(audio, WAVE):
            # WAV 文件一般没有标签
            pass
        else:
            # 尝试通用方式
            tags = getattr(audio, 'tags', None)
            if tags:
                if hasattr(tags, 'get'):
                    title = tags.get('title', [title])[0] if isinstance(tags.get('title', title), list) else tags.get('title', title)
                    artist = tags.get('artist', [artist])[0] if isinstance(tags.get('artist', artist), list) else tags.get('artist', artist)

    except Exception as e:
        print(f"  [警告] 无法读取 {filepath.name} 的元数据: {e}")

    return {"title": str(title), "artist": str(artist), "duration": duration}


def extract_metadata(filepath: Path, audio_hash: str) -> dict:
    """提取音频元数据, 优先使用缓存"""
    cache_key = str(filepath.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('metadata', cache_key, audio_hash)
    if cached is not None:
        print(f"    └─ 元数据: 使用缓存")
        return cached

    result = _extract_metadata_impl(filepath)
    set_cache('metadata', cache_key, audio_hash, result)
    return result


def extract_cover_from_audio(audio_path: Path, audio_hash: str) -> Path | None:
    """从音频文件中提取嵌入的封面图片，保存到同目录下

    如果同名封面已经存在则跳过。
    使用缓存: 如果音频文件未变更且封面文件仍存在, 则跳过提取。
    返回封面文件路径，无封面则返回 None。
    """
    if not HAS_MUTAGEN:
        return None

    stem = audio_path.stem
    parent = audio_path.parent

    # 如果同名封面已存在，跳过提取
    for ext in COVER_EXTENSIONS:
        if (parent / (stem + ext)).exists():
            return parent / (stem + ext)

    # 检查缓存: 上次提取过且音频没变, 说明确实没有嵌入封面
    cache_key = str(audio_path.relative_to(STATIC_MUSIC_DIR))
    cached = get_cache('cover_extract', cache_key, audio_hash)
    if cached is not None:
        cover_name = cached.get('cover_name')
        if cover_name:
            cover_path = parent / cover_name
            if cover_path.exists():
                return cover_path
        else:
            # 上次就没提取到封面, 且音频没变
            return None

    try:
        audio = MutagenFile(str(audio_path))
        if audio is None:
            return None

        img_data = None
        img_mime = None

        if isinstance(audio, MP3):
            # ID3 APIC frames
            if audio.tags:
                for key in audio.tags:
                    if key.startswith('APIC'):
                        apic = audio.tags[key]
                        img_data = apic.data
                        img_mime = apic.mime
                        break

        elif isinstance(audio, FLAC):
            # FLAC pictures
            if audio.pictures:
                pic = audio.pictures[0]
                img_data = pic.data
                img_mime = pic.mime

        elif isinstance(audio, MP4):
            # MP4/M4A covr atom
            if audio.tags and 'covr' in audio.tags:
                covers = audio.tags['covr']
                if covers:
                    cover = covers[0]
                    img_data = bytes(cover)
                    # MP4Cover.FORMAT_JPEG = 13, FORMAT_PNG = 14
                    if hasattr(cover, 'imageformat'):
                        img_mime = 'image/png' if cover.imageformat == 14 else 'image/jpeg'
                    else:
                        img_mime = 'image/jpeg'

        elif isinstance(audio, (OggVorbis, OggOpus)):
            # Ogg 格式嵌入封面 (metadata_block_picture)
            import base64
            from mutagen.flac import Picture
            pics = audio.get('metadata_block_picture', [])
            if pics:
                try:
                    pic = Picture(base64.b64decode(pics[0]))
                    img_data = pic.data
                    img_mime = pic.mime
                except Exception:
                    pass

        if img_data and img_mime:
            ext = MIME_TO_EXT.get(img_mime, '.jpg')
            cover_path = parent / (stem + ext)
            cover_path.write_bytes(img_data)
            print(f"    └─ 提取封面: {cover_path.name} ({len(img_data)} bytes)")
            set_cache('cover_extract', cache_key, audio_hash, {'cover_name': cover_path.name})
            return cover_path

    except Exception as e:
        print(f"  [警告] 提取封面失败 {audio_path.name}: {e}")

    # 没有嵌入封面, 也写入缓存避免下次重复尝试
    set_cache('cover_extract', cache_key, audio_hash, {'cover_name': None})
    return None


def find_matching_cover(audio_path: Path) -> Path | None:
    """查找与音频文件同名的封面图片"""
    stem = audio_path.stem
    parent = audio_path.parent
    for ext in COVER_EXTENSIONS:
        cover_path = parent / (stem + ext)
        if cover_path.exists():
            return cover_path
    # 也查找目录中的 cover.* / folder.*
    for name_prefix in ['cover', 'folder', 'albumart']:
        for ext in COVER_EXTENSIONS:
            cover_path = parent / (name_prefix + ext)
            if cover_path.exists():
                return cover_path
    return None
