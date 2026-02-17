"""邮件发送模块

通过 SMTP 发送转写文字稿到指定邮箱。
支持 QQ 邮箱等 SSL SMTP 服务。
"""

import logging
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    success: bool
    error: Optional[str] = None


class EmailSender:
    """SMTP 邮件发送器"""

    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password

    def send_transcript(
        self,
        to_addr: str,
        title: str,
        author: str,
        source_url: str,
        duration: float,
        text: str,
        summary: str = "",
    ) -> EmailResult:
        """发送转写文字稿邮件

        Args:
            to_addr: 收件人邮箱
            title: 视频标题
            author: 作者
            source_url: 视频来源链接
            duration: 视频时长(秒)
            text: 正文(AI润色后)
            summary: 摘要
        """
        subject = f"[视频文字稿] {title}"
        html = self._build_html(title, author, source_url, duration, text, summary)

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.user
            msg["To"] = to_addr
            msg.attach(MIMEText(html, "html", "utf-8"))

            with smtplib.SMTP_SSL(self.host, self.port, timeout=15) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, [to_addr], msg.as_string())

            logger.info(f"邮件已发送: {subject} -> {to_addr}")
            return EmailResult(success=True)
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return EmailResult(success=False, error=str(e))

    @staticmethod
    def _build_html(title, author, source_url, duration, text, summary):
        """构建 HTML 邮件正文"""
        import time
        now = time.strftime("%Y-%m-%d %H:%M")

        summary_section = ""
        if summary:
            summary_html = "".join(f"<p>{line}</p>" for line in summary.split("\n") if line.strip())
            summary_section = f"""
            <div style="background:#f0f7ff;border-left:4px solid #1890ff;padding:12px 16px;margin:16px 0;border-radius:4px;">
                <h3 style="margin:0 0 8px;color:#1890ff;font-size:15px;">📋 内容摘要</h3>
                <div style="color:#333;font-size:14px;line-height:1.8;">{summary_html}</div>
            </div>"""

        text_html = "".join(f"<p style='margin:8px 0;'>{line}</p>" for line in text.split("\n") if line.strip())

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#333;">
<h2 style="color:#1a1a1a;border-bottom:2px solid #fe2c55;padding-bottom:8px;">🎬 {title}</h2>
<table style="font-size:13px;color:#666;margin:12px 0;">
<tr><td style="padding:2px 12px 2px 0;"><b>作者</b></td><td>{author or '未知'}</td></tr>
<tr><td style="padding:2px 12px 2px 0;"><b>时间</b></td><td>{now}</td></tr>
<tr><td style="padding:2px 12px 2px 0;"><b>来源</b></td><td><a href="{source_url}" style="color:#fe2c55;">{source_url}</a></td></tr>
<tr><td style="padding:2px 12px 2px 0;"><b>时长</b></td><td>{duration:.1f}s</td></tr>
</table>
{summary_section}
<div style="margin-top:16px;">
<h3 style="color:#1a1a1a;font-size:15px;">📝 完整文字稿</h3>
<div style="font-size:14px;line-height:1.8;color:#444;">{text_html}</div>
</div>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<p style="font-size:12px;color:#999;">此邮件由抖音视频解析工具自动发送</p>
</body></html>"""
