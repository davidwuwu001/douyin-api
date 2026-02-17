"""火山引擎语音转文字模块

使用火山引擎「豆包语音 - 音视频字幕生成」接口，将视频/音频转为文字。
接口文档: https://www.volcengine.com/docs/6561/80909

流程：
1. 提交音频 URL 到 submit 接口，获取任务 ID
2. 通过 query 接口查询转写结果（支持阻塞/轮询两种模式）
3. 拼接所有 utterances 的 text，返回完整文本

需要配置：
- VOLC_APP_ID: 火山引擎应用 ID
- VOLC_ACCESS_TOKEN: 火山引擎 Bearer Token
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://openspeech.bytedance.com/api/v1/vc"


@dataclass
class TranscriptResult:
    """转写结果"""
    text: str  # 完整文本
    duration: float = 0.0  # 音频时长（秒）
    utterances: list = None  # 原始分句数据
    error: Optional[str] = None  # 错误信息

    def __post_init__(self):
        if self.utterances is None:
            self.utterances = []


class Transcriber:
    """火山引擎语音转文字

    使用音视频字幕生成 API，支持直接传入音频/视频 URL。
    """

    def __init__(self, app_id: str, access_token: str, timeout: float = 120.0):
        """
        Args:
            app_id: 火山引擎应用 ID
            access_token: Bearer Token
            timeout: 查询超时时间（秒），默认 120s
        """
        self.app_id = app_id
        self.access_token = access_token
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer; {self.access_token}",
            "Content-Type": "application/json",
        }

    def _submit(self, audio_url: str) -> Optional[str]:
        """提交音频 URL，返回任务 ID"""
        resp = requests.post(
            f"{_BASE_URL}/submit",
            params={
                "appid": self.app_id,
                "language": "zh-CN",
                "use_itn": "True",       # 数字转换（中文数字→阿拉伯数字）
                "use_capitalize": "True",
                "use_punc": "True",       # 添加标点
                "caption_type": "speech",  # 只识别说话部分
                "max_lines": 1,
                "words_per_line": 40,
            },
            json={"url": audio_url},
            headers=self._headers(),
            timeout=30,
        )

        if resp.status_code != 200:
            logger.error(f"submit 请求失败 HTTP {resp.status_code}: {resp.text}")
            return None

        data = resp.json()
        if data.get("code") != 0 and str(data.get("code")) != "0":
            logger.error(f"submit 失败: {data.get('message')}")
            return None

        job_id = data.get("id")
        logger.info(f"任务已提交, job_id={job_id}")
        return job_id

    def _query(self, job_id: str, blocking: bool = True) -> dict:
        """查询转写结果

        Args:
            job_id: 任务 ID
            blocking: 是否使用阻塞模式（服务端等待完成后返回）
        """
        resp = requests.get(
            f"{_BASE_URL}/query",
            params={
                "appid": self.app_id,
                "id": job_id,
                "blocking": 1 if blocking else 0,
            },
            headers={"Authorization": f"Bearer; {self.access_token}"},
            timeout=self.timeout,
        )

        if resp.status_code != 200:
            logger.error(f"query 请求失败 HTTP {resp.status_code}")
            return {"code": -1, "message": f"HTTP {resp.status_code}"}

        return resp.json()

    def transcribe(self, audio_url: str) -> TranscriptResult:
        """转写音频 URL 为文字

        Args:
            audio_url: 音频/视频的可访问 URL

        Returns:
            TranscriptResult 包含完整文本和分句信息
        """
        # 1. 提交任务
        job_id = self._submit(audio_url)
        if not job_id:
            return TranscriptResult(text="", error="提交转写任务失败")

        # 2. 查询结果（阻塞模式，服务端会等处理完再返回）
        logger.info(f"等待转写完成... job_id={job_id}")
        result = self._query(job_id, blocking=True)

        code = result.get("code", -1)

        # 还在处理中（阻塞模式下一般不会出现，但做个兜底）
        if code == 2000:
            # 轮询等待
            start = time.time()
            while time.time() - start < self.timeout:
                time.sleep(3)
                result = self._query(job_id, blocking=False)
                code = result.get("code", -1)
                if code != 2000:
                    break
                logger.info("转写处理中，继续等待...")

        if code != 0:
            msg = result.get("message", "未知错误")
            logger.error(f"转写失败: code={code}, message={msg}")
            return TranscriptResult(text="", error=f"转写失败({code}): {msg}")

        # 3. 拼接文本
        utterances = result.get("utterances", [])
        duration = result.get("duration", 0.0)
        full_text = "".join(u.get("text", "") for u in utterances)

        logger.info(f"转写完成: {len(utterances)} 句, {duration:.1f}s, {len(full_text)} 字")

        return TranscriptResult(
            text=full_text,
            duration=duration,
            utterances=utterances,
        )
