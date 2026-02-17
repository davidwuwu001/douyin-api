"""AI 文字处理模块

调用火山方舟（豆包大模型）对转写文字进行：
1. 错别字纠正
2. 内容摘要生成

API 兼容 OpenAI 格式。
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


@dataclass
class AIProcessResult:
    """AI 处理结果"""
    success: bool
    corrected_text: str = ""
    summary: str = ""
    error: Optional[str] = None


class AIProcessor:
    """豆包大模型文字处理器"""

    def __init__(self, api_key: str, model: str = "doubao-seed-2-0-mini-260215"):
        self.api_key = api_key
        self.model = model

    def _call(self, system_prompt: str, user_content: str, max_tokens: int = 4096) -> str:
        """调用大模型"""
        resp = requests.post(
            _ARK_BASE,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        data = resp.json()
        if "choices" not in data:
            raise RuntimeError(f"API 返回异常: {data.get('error', data)}")
        return data["choices"][0]["message"]["content"].strip()

    def generate_title(self, text: str) -> str:
        """根据文字内容自动生成一个简短标题

        Args:
            text: 文字内容

        Returns:
            生成的标题，失败返回空字符串
        """
        try:
            title = self._call(
                system_prompt=(
                    "你是一个标题生成助手。"
                    "请根据以下文字内容，生成一个简洁、准确的中文标题。"
                    "标题要求：10-25个字，概括核心主题，不要加书名号或引号。"
                    "直接输出标题，不要添加任何说明。"
                ),
                user_content=text[:2000],  # 取前2000字足够判断主题
                max_tokens=100,
            )
            # 清理可能的引号
            title = title.strip().strip('"\'""''《》【】')
            logger.info(f"AI 生成标题: {title}")
            return title
        except Exception as e:
            logger.error(f"AI 生成标题失败: {e}")
            return ""

    def process(self, raw_text: str) -> AIProcessResult:
        """对转写文字做纠错 + 摘要

        Args:
            raw_text: 语音转写的原始文字

        Returns:
            AIProcessResult 包含纠正后的文字和摘要
        """
        try:
            # 1. 纠错
            corrected = self._call(
                system_prompt=(
                    "你是一个专业的中文文字校对助手。"
                    "请对以下语音转写文字进行纠错处理：修正错别字、同音字错误、语法不通顺的地方。"
                    "保持原文的意思和风格不变，只做必要的纠正。"
                    "直接输出纠正后的文字，不要添加任何说明或标注。"
                ),
                user_content=raw_text,
            )

            # 2. 摘要
            summary = self._call(
                system_prompt=(
                    "你是一个专业的内容摘要助手。"
                    "请对以下文字生成一段简洁的摘要，概括核心要点。"
                    "摘要控制在 200 字以内，用清晰的条理呈现。"
                    '直接输出摘要内容，不要添加"摘要："等前缀。'
                ),
                user_content=corrected,
                max_tokens=10000,
            )

            logger.info(f"AI 处理完成: 原文 {len(raw_text)} 字 -> 纠正 {len(corrected)} 字, 摘要 {len(summary)} 字")
            return AIProcessResult(success=True, corrected_text=corrected, summary=summary)

        except Exception as e:
            logger.error(f"AI 处理失败: {e}")
            return AIProcessResult(success=False, error=str(e))
