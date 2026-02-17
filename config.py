"""配置管理

从环境变量或 .env 文件加载配置。
"""

import os


class Config:
    """应用配置，从环境变量读取"""

    # 火山引擎 - 音视频字幕生成
    VOLC_APP_ID: str = os.environ.get("VOLC_APP_ID", "")
    VOLC_ACCESS_TOKEN: str = os.environ.get("VOLC_ACCESS_TOKEN", "")

    # 飞书开放平台
    FEISHU_APP_ID: str = os.environ.get("FEISHU_APP_ID", "")
    FEISHU_APP_SECRET: str = os.environ.get("FEISHU_APP_SECRET", "")
    FEISHU_FOLDER_TOKEN: str = os.environ.get("FEISHU_FOLDER_TOKEN", "")

    # 火山方舟（豆包大模型）
    ARK_API_KEY: str = os.environ.get("ARK_API_KEY", "")
    ARK_MODEL: str = os.environ.get("ARK_MODEL", "doubao-seed-2-0-mini-260215")

    # 邮件发送 (SMTP)
    SMTP_HOST: str = os.environ.get("ALERT_SMTP_HOST", "").strip('"')
    SMTP_PORT: int = int(os.environ.get("ALERT_SMTP_PORT", "465").strip('"'))
    SMTP_USER: str = os.environ.get("ALERT_SMTP_USER", "").strip('"')
    SMTP_PASS: str = os.environ.get("ALERT_SMTP_PASS", "").strip('"')
    EMAIL_TO: str = os.environ.get("ALERT_EMAIL_TO", "").strip('"')

    @classmethod
    def is_transcribe_enabled(cls) -> bool:
        """转写功能是否已配置"""
        return bool(cls.VOLC_APP_ID and cls.VOLC_ACCESS_TOKEN)

    @classmethod
    def is_feishu_enabled(cls) -> bool:
        """飞书存储功能是否已配置"""
        return bool(cls.FEISHU_APP_ID and cls.FEISHU_APP_SECRET and cls.FEISHU_FOLDER_TOKEN)

    @classmethod
    def is_ai_enabled(cls) -> bool:
        """AI 处理功能是否已配置"""
        return bool(cls.ARK_API_KEY)

    @classmethod
    def is_email_enabled(cls) -> bool:
        """邮件发送功能是否已配置"""
        return bool(cls.SMTP_HOST and cls.SMTP_USER and cls.SMTP_PASS)
