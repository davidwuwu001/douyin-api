"""抖音视频解析器

通过 iesdouyin 移动端分享页面解析视频信息，获取无水印视频播放地址。
纯 HTTP 请求，不需要 cookie、登录或浏览器环境。
"""

import asyncio
import logging
import re
import json
from typing import List, Optional

import requests

from models import VideoRecord

logger = logging.getLogger(__name__)

# 移动端 UA + Referer，模拟手机浏览器访问
_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/116.0.0.0 Mobile Safari/537.36"
    ),
    "referer": "https://www.douyin.com/?is_from_mobile_home=1&recommend=1",
}

_SHARE_URL_TEMPLATE = "https://www.iesdouyin.com/share/video/{aweme_id}/"
_PLAY_URL_TEMPLATE = "https://www.douyin.com/aweme/v1/play/?video_id={video_id}"


def extract_url_from_text(text: str) -> Optional[str]:
    """从分享文本中提取抖音链接

    抖音一键分享的文本通常包含大量描述信息，需要从中提取出有效 URL。

    支持提取：
    - https://v.douyin.com/xxx （短链接）
    - https://www.douyin.com/video/xxx （长链接）
    - http(s)://www.iesdouyin.com/share/video/xxx

    示例输入：
        '3.05 复制打开抖音，看看【量子位的作品】... https://v.douyin.com/pblL5pmtw_4/ NwF:/'
    返回：
        'https://v.douyin.com/pblL5pmtw_4/'
    """
    # 优先匹配抖音域名的 URL
    match = re.search(
        r'https?://(?:v\.douyin\.com|www\.douyin\.com|www\.iesdouyin\.com)/\S+',
        text,
    )
    if match:
        # 去除尾部可能粘连的非 URL 字符
        url = match.group(0).rstrip('。，！？、）》」】')
        return url
    return None


def resolve_short_url(short_url: str, timeout: float = 10.0) -> Optional[str]:
    """解析抖音短链接，跟踪重定向获取最终长链接

    短链接（如 https://v.douyin.com/xxx）会 302 重定向到长链接。
    通过 HEAD 请求 + allow_redirects 跟踪重定向链，拿到最终 URL。

    Returns:
        最终重定向后的 URL，失败返回 None
    """
    try:
        resp = requests.head(
            short_url,
            headers=_HEADERS,
            allow_redirects=True,
            timeout=timeout,
        )
        final_url = resp.url
        logger.info(f"短链接重定向: {short_url} -> {final_url}")
        return final_url
    except requests.RequestException as e:
        logger.error(f"短链接解析失败: {short_url} - {e}")
        return None


def extract_aweme_id(video_url: str) -> Optional[str]:
    """从抖音视频 URL 中提取 aweme_id

    支持格式：
    - https://www.douyin.com/video/7606346524510997787
    - https://www.douyin.com/video/7606346524510997787?xxx=yyy
    """
    match = re.search(r"/video/(\d+)", video_url)
    return match.group(1) if match else None


class VideoResolver:
    """抖音视频解析器

    通过 iesdouyin 接口解析视频，获取无水印播放地址。
    支持单个解析和批量解析，内置请求间隔控制。
    """

    def __init__(self, delay: float = 2.0, timeout: float = 15.0):
        """
        Args:
            delay: 批量解析时每次请求的间隔秒数，防止触发反爬
            timeout: 单次请求超时时间
        """
        self.delay = delay
        self.timeout = timeout
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """获取 HTTP Session（懒加载，绕过系统代理）"""
        if self._session is None:
            self._session = requests.Session()
            self._session.trust_env = False  # 绕过环境变量中的代理
        return self._session

    def resolve(self, video: VideoRecord) -> VideoRecord:
        """解析单个视频，填充 aweme_id、video_play_url、duration_seconds

        支持三种输入：
        1. 标准长链接：https://www.douyin.com/video/xxx
        2. 短链接：https://v.douyin.com/xxx
        3. 分享文本：包含链接的混合文本（自动提取 URL）

        解析失败不抛异常，只记录日志，返回原始 VideoRecord（play_url 为空）。
        """
        url = video.url

        # 判断输入是否为纯 URL 还是包含其他文本的分享文本
        # 纯 URL 以 http 开头且不含空格；否则视为分享文本，需要提取
        is_plain_url = url.strip().startswith("http") and " " not in url.strip()
        if not is_plain_url:
            extracted = extract_url_from_text(url)
            if extracted:
                logger.info(f"从分享文本中提取到 URL: {extracted}")
                url = extracted
            else:
                logger.warning(f"无法从文本中提取抖音链接: {url}")
                return video

        # 提取 aweme_id（长链接直接提取）
        aweme_id = extract_aweme_id(url)

        # 如果提取失败，可能是短链接，尝试重定向解析
        if not aweme_id and "v.douyin.com" in url:
            logger.info(f"检测到短链接，尝试重定向解析: {url}")
            final_url = resolve_short_url(url, timeout=self.timeout)
            if final_url:
                aweme_id = extract_aweme_id(final_url)

        if not aweme_id:
            logger.warning(f"无法从 URL 提取 aweme_id: {url}")
            return video

        video.aweme_id = aweme_id

        try:
            share_url = _SHARE_URL_TEMPLATE.format(aweme_id=aweme_id)
            session = self._get_session()
            resp = session.get(share_url, headers=_HEADERS, timeout=self.timeout)

            if resp.status_code != 200:
                logger.warning(f"请求失败 HTTP {resp.status_code}: {video.title}")
                return video

            # 提取 _ROUTER_DATA
            match = re.findall(
                r"window\._ROUTER_DATA\s*=\s*(.*?)</script>", resp.text
            )
            if not match:
                logger.warning(f"未找到 _ROUTER_DATA: {video.title}")
                return video

            json_data = json.loads(match[0])
            video_page = json_data.get("loaderData", {}).get("video_(id)/page", {})
            video_info = video_page.get("videoInfoRes", {})
            item_list = video_info.get("item_list", [])

            if not item_list:
                # 检查是否被过滤（图文类型等）
                filter_list = video_info.get("filter_list", [])
                if filter_list:
                    reason = filter_list[0].get("filter_reason", "unknown")
                    logger.info(f"视频被过滤({reason}): {video.title}")
                else:
                    logger.warning(f"item_list 为空: {video.title}")
                return video

            item = item_list[0]
            video_uri = item.get("video", {}).get("play_addr", {}).get("uri", "")
            duration_ms = item.get("video", {}).get("duration", 0)

            # 提取视频标题（desc）和作者昵称
            desc = item.get("desc", "").strip()
            author_nickname = item.get("author", {}).get("nickname", "").strip()
            if desc and not video.title:
                video.title = desc
            if author_nickname and not video.author:
                video.author = author_nickname

            if video_uri:
                if "mp3" not in video_uri:
                    video.video_play_url = _PLAY_URL_TEMPLATE.format(video_id=video_uri)
                else:
                    video.video_play_url = video_uri
                video.duration_seconds = duration_ms / 1000.0
                logger.info(
                    f"解析成功: {video.title} | 作者: {video.author} | "
                    f"{video.duration_seconds:.1f}s | {video_uri}"
                )
            else:
                logger.warning(f"未找到 video_uri: {video.title}")

        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {video.title} - {e}")
        except requests.RequestException as e:
            logger.error(f"网络请求失败: {video.title} - {e}")
        except Exception as e:
            logger.error(f"解析异常: {video.title} - {e}")

        return video

    async def resolve_batch(self, videos: List[VideoRecord]) -> List[VideoRecord]:
        """批量解析视频列表

        在事件循环中用 run_in_executor 执行同步请求，
        每次请求之间加入延迟防止触发反爬。
        返回解析后的 VideoRecord 列表（原地修改）。
        """
        loop = asyncio.get_event_loop()
        resolved = []
        total = len(videos)

        for i, video in enumerate(videos):
            # 跳过已解析的
            if video.video_play_url:
                resolved.append(video)
                continue

            result = await loop.run_in_executor(None, self.resolve, video)
            resolved.append(result)

            # 除最后一个外，加延迟
            if i < total - 1:
                await asyncio.sleep(self.delay)

        success = sum(1 for v in resolved if v.video_play_url)
        logger.info(f"批量解析完成: {success}/{total} 个视频解析成功")
        return resolved

    def close(self):
        """关闭 HTTP Session"""
        if self._session:
            self._session.close()
            self._session = None
