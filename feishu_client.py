"""飞书文档客户端

通过飞书开放平台 API，在指定文件夹下创建文档并写入内容。
用于将视频转写文字稿存入飞书知识库。

需要配置：
- FEISHU_APP_ID: 飞书应用 App ID
- FEISHU_APP_SECRET: 飞书应用 App Secret
- FEISHU_FOLDER_TOKEN: 目标文件夹 token
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE = "https://open.feishu.cn/open-apis"


@dataclass
class FeishuDocResult:
    """创建文档的结果"""
    success: bool
    doc_url: str = ""
    doc_title: str = ""
    error: Optional[str] = None


class FeishuClient:
    """飞书文档客户端"""

    def __init__(self, app_id: str, app_secret: str, folder_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.folder_token = folder_token
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _get_token(self) -> str:
        """获取 tenant_access_token（带缓存）"""
        if self._token and time.time() < self._token_expires:
            return self._token

        resp = requests.post(f"{_BASE}/auth/v3/tenant_access_token/internal", json={
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }, timeout=10)

        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"获取飞书 token 失败: {data.get('msg')}")

        self._token = data["tenant_access_token"]
        self._token_expires = time.time() + data.get("expire", 7200) - 300
        return self._token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    def _set_doc_permission(self, doc_token: str):
        """设置文档权限：组织内任何人可编辑

        通过设置 link_share_entity 让组织内成员可以通过链接直接编辑文档。
        """
        try:
            resp = requests.patch(
                f"{_BASE}/drive/v1/permissions/{doc_token}/public",
                headers=self._headers(),
                params={"type": "docx"},
                json={
                    "external_access_entity": "open",
                    "security_entity": "anyone_can_view",
                    "comment_entity": "anyone_can_view",
                    "share_entity": "anyone",
                    "link_share_entity": "tenant_editable",
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning(f"设置文档权限失败: {data.get('msg')} (不影响文档创建)")
            else:
                logger.info(f"文档权限已设置为组织内可编辑")
        except Exception as e:
            logger.warning(f"设置文档权限异常: {e} (不影响文档创建)")

    def save_transcript(
        self,
        title: str,
        author: str,
        source_url: str,
        duration: float,
        text: str,
        summary: str = "",
    ) -> FeishuDocResult:
        """将转写文字稿保存为飞书文档

        Args:
            title: 视频标题
            author: 作者/博主名
            source_url: 视频来源链接
            duration: 视频时长（秒）
            text: 转写文字内容（纠错后的）
            summary: AI 生成的摘要（可选）
        """
        now = time.strftime("%Y-%m-%d %H:%M")
        doc_title = f"[{now[:10]}] {title} - {author}" if author else f"[{now[:10]}] {title}"

        try:
            # 1. 创建文档
            doc_resp = requests.post(
                f"{_BASE}/docx/v1/documents",
                headers=self._headers(),
                json={"folder_token": self.folder_token, "title": doc_title},
                timeout=15,
            )
            doc_data = doc_resp.json()
            if doc_data.get("code") != 0:
                msg = doc_data.get("msg", "未知错误")
                logger.error(f"创建文档失败: {msg}")
                return FeishuDocResult(success=False, error=f"创建文档失败: {msg}")

            document = doc_data["data"]["document"]
            doc_id = document["document_id"]
            doc_url = f"https://my.feishu.cn/docx/{doc_id}"

            # 2. 设置文档权限（组织内可编辑）
            self._set_doc_permission(doc_id)

            # 3. 写入元信息 + 摘要 + 正文
            blocks = self._build_blocks(title, author, now, source_url, duration, text, summary)

            create_resp = requests.post(
                f"{_BASE}/docx/v1/documents/{doc_id}/blocks/{doc_id}/children",
                headers=self._headers(),
                json={"children": blocks, "index": 0},
                timeout=30,
            )
            create_data = create_resp.json()
            if create_data.get("code") != 0:
                msg = create_data.get("msg", "未知错误")
                logger.error(f"写入文档内容失败: {msg}")
                return FeishuDocResult(success=False, doc_url=doc_url, error=f"写入内容失败: {msg}")

            logger.info(f"文档已保存: {doc_title} -> {doc_url}")
            return FeishuDocResult(success=True, doc_url=doc_url, doc_title=doc_title)

        except requests.RequestException as e:
            logger.error(f"飞书 API 请求失败: {e}")
            return FeishuDocResult(success=False, error=f"网络请求失败: {e}")

    @staticmethod
    def _build_blocks(title, author, time_str, source_url, duration, text, summary=""):
        """构建飞书文档 block 列表"""

        def text_block(content: str) -> dict:
            """创建文本段落 block"""
            return {
                "block_type": 2,
                "text": {
                    "elements": [{"text_run": {"content": content}}],
                    "style": {},
                },
            }

        def bold_text_block(label: str, content: str) -> dict:
            """创建带粗体标签的文本 block"""
            return {
                "block_type": 2,
                "text": {
                    "elements": [
                        {"text_run": {"content": label, "text_element_style": {"bold": True}}},
                        {"text_run": {"content": content}},
                    ],
                    "style": {},
                },
            }

        def divider_block() -> dict:
            return {"block_type": 22, "divider": {}}

        blocks = []

        # 元信息区域
        blocks.append(bold_text_block("作者：", author if author else "未知"))
        blocks.append(bold_text_block("时间：", time_str))
        blocks.append(bold_text_block("来源：", source_url))
        blocks.append(bold_text_block("时长：", f"{duration:.1f}s"))

        # 摘要区域
        if summary:
            blocks.append(divider_block())
            blocks.append(bold_text_block("📋 内容摘要", ""))
            for line in summary.split("\n"):
                if line.strip():
                    blocks.append(text_block(line.strip()))

        # 分割线
        blocks.append(divider_block())
        blocks.append(bold_text_block("📝 完整文字稿", ""))

        # 正文
        paragraphs = text.split("\n") if "\n" in text else [text]
        for p in paragraphs:
            if p.strip():
                blocks.append(text_block(p.strip()))

        return blocks
