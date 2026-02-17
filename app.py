"""抖音视频解析 API 服务

纯 JSON API，专为飞书多维表格等外部系统调用设计。
无 Web GUI，所有接口返回 JSON。

接口列表：
- POST /api/resolve      解析视频，返回下载地址、标题、作者
- POST /api/transcript   解析视频 + 语音转文字 + AI润色，返回完整文案
- POST /api/save_feishu  解析视频 + 转写 + AI润色 + 保存到飞书
- POST /api/email        解析视频 + 转写 + AI润色 + 发送邮件
- GET  /api/download     代理下载视频（绕过防盗链）

启动: gunicorn -w 2 -b 0.0.0.0:3102 --timeout 180 app:app
"""

import logging
import os
import time

import requests as http_requests
from flask import Flask, jsonify, request, Response

from config import Config
from video_resolver import VideoResolver, extract_url_from_text, resolve_short_url, extract_aweme_id
from models import VideoRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
resolver = VideoResolver(timeout=15.0)

# --- 懒加载组件 ---

_transcriber = None
def get_transcriber():
    global _transcriber
    if _transcriber is None and Config.is_transcribe_enabled():
        from transcriber import Transcriber
        _transcriber = Transcriber(app_id=Config.VOLC_APP_ID, access_token=Config.VOLC_ACCESS_TOKEN)
    return _transcriber

_ai = None
def get_ai():
    global _ai
    if _ai is None and Config.is_ai_enabled():
        from ai_processor import AIProcessor
        _ai = AIProcessor(api_key=Config.ARK_API_KEY, model=Config.ARK_MODEL)
    return _ai

_feishu = None
def get_feishu():
    global _feishu
    if _feishu is None and Config.is_feishu_enabled():
        from feishu_client import FeishuClient
        _feishu = FeishuClient(app_id=Config.FEISHU_APP_ID, app_secret=Config.FEISHU_APP_SECRET, folder_token=Config.FEISHU_FOLDER_TOKEN)
    return _feishu

_email = None
def get_email():
    global _email
    if _email is None and Config.is_email_enabled():
        from email_sender import EmailSender
        _email = EmailSender(host=Config.SMTP_HOST, port=Config.SMTP_PORT, user=Config.SMTP_USER, password=Config.SMTP_PASS)
    return _email


# --- 工具函数 ---

def _resolve_video(url: str) -> dict:
    """解析视频，返回结果字典"""
    video = VideoRecord(title="", url=url)
    result = resolver.resolve(video)
    if not result.video_play_url:
        return {"success": False, "error": "解析失败，请检查链接是否有效"}
    return {
        "success": True,
        "title": result.title or "",
        "author": result.author or "",
        "aweme_id": result.aweme_id,
        "play_url": result.video_play_url,
        "duration": round(result.duration_seconds, 1),
    }


def _transcribe_video(play_url: str) -> dict:
    """转写视频语音
    
    将播放地址转换为本地代理地址，让火山引擎通过我们的服务器下载视频
    """
    transcriber = get_transcriber()
    if not transcriber:
        return {"success": False, "error": "转写功能未配置"}
    
    # 使用本地代理地址，绕过抖音防盗链
    # 火山引擎会通过我们的服务器下载视频
    proxy_url = f"http://127.0.0.1:3102/api/download?url={play_url}"
    logger.info(f"使用代理地址进行转写: {proxy_url}")
    
    result = transcriber.transcribe(proxy_url)
    if result.error:
        return {"success": False, "error": result.error}
    return {"success": True, "text": result.text, "duration": round(result.duration, 1)}


def _ai_process(text: str, title: str = "") -> dict:
    """AI 纠错 + 摘要 + 自动生成标题"""
    ai = get_ai()
    if not ai:
        return {"corrected": text, "summary": "", "title": title or "未知视频"}
    ai_result = ai.process(text)
    corrected = ai_result.corrected_text if ai_result.success else text
    summary = ai_result.summary if ai_result.success else ""
    if not title or title == "未知":
        generated = ai.generate_title(corrected)
        if generated:
            title = generated
    return {"corrected": corrected, "summary": summary, "title": title or "未知视频"}


# --- API 接口 ---

@app.route("/api/resolve", methods=["POST"])
def api_resolve():
    """接口1: 解析视频下载地址

    请求: {"url": "抖音链接或分享文本"}
    响应: {"success": true, "title": "...", "author": "...", "play_url": "...", "duration": 12.3}
    """
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "请提供 url 参数"}), 400
    result = _resolve_video(url)
    return jsonify(result)


@app.route("/api/transcript", methods=["POST"])
def api_transcript():
    """接口2: 解析视频 + 语音转文字 + AI润色

    请求: {"url": "抖音链接或分享文本"}
    响应: {
        "success": true,
        "title": "视频标题(AI生成或原始)",
        "author": "作者",
        "duration": 12.3,
        "text": "AI纠错后的文字",
        "summary": "AI摘要",
        "play_url": "下载地址"
    }
    """
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "请提供 url 参数"}), 400

    # 1. 解析视频
    resolve_result = _resolve_video(url)
    if not resolve_result.get("success"):
        return jsonify(resolve_result)

    # 2. 语音转文字
    transcript = _transcribe_video(resolve_result["play_url"])
    if not transcript.get("success"):
        return jsonify({"success": False, "error": f"转写失败: {transcript.get('error')}"})

    # 3. AI 处理
    ai_result = _ai_process(transcript["text"], resolve_result.get("title", ""))

    return jsonify({
        "success": True,
        "title": ai_result["title"],
        "author": resolve_result.get("author", ""),
        "duration": resolve_result.get("duration", 0),
        "text": ai_result["corrected"],
        "summary": ai_result["summary"],
        "play_url": resolve_result["play_url"],
    })


@app.route("/api/save_feishu", methods=["POST"])
def api_save_feishu():
    """接口3: 解析视频 + 转写 + AI润色 + 保存到飞书

    请求: {"url": "抖音链接或分享文本"}
    响应: {"success": true, "doc_url": "飞书文档链接", "doc_title": "文档标题"}
    """
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"success": False, "error": "请提供 url 参数"}), 400

    client = get_feishu()
    if not client:
        return jsonify({"success": False, "error": "飞书功能未配置"})

    # 1. 解析视频
    resolve_result = _resolve_video(url)
    if not resolve_result.get("success"):
        return jsonify(resolve_result)

    # 2. 语音转文字
    transcript = _transcribe_video(resolve_result["play_url"])
    if not transcript.get("success"):
        return jsonify({"success": False, "error": f"转写失败: {transcript.get('error')}"})

    # 3. AI 处理
    ai_result = _ai_process(transcript["text"], resolve_result.get("title", ""))

    # 4. 保存到飞书
    result = client.save_transcript(
        title=ai_result["title"],
        author=resolve_result.get("author", ""),
        source_url=url,
        duration=resolve_result.get("duration", 0),
        text=ai_result["corrected"],
        summary=ai_result["summary"],
    )
    if result.success:
        return jsonify({"success": True, "doc_url": result.doc_url, "doc_title": result.doc_title})
    else:
        return jsonify({"success": False, "error": result.error})


@app.route("/api/email", methods=["POST"])
def api_email():
    """接口4: 解析视频 + 转写 + AI润色 + 发送邮件

    请求: {"url": "抖音链接或分享文本", "to": "收件人邮箱(可选，默认用配置)"}
    响应: {"success": true}
    """
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    to_addr = data.get("to", "").strip() or Config.EMAIL_TO
    if not url:
        return jsonify({"success": False, "error": "请提供 url 参数"}), 400
    if not to_addr:
        return jsonify({"success": False, "error": "请提供收件人邮箱"}), 400

    sender = get_email()
    if not sender:
        return jsonify({"success": False, "error": "邮件功能未配置"})

    # 1. 解析视频
    resolve_result = _resolve_video(url)
    if not resolve_result.get("success"):
        return jsonify(resolve_result)

    # 2. 语音转文字
    transcript = _transcribe_video(resolve_result["play_url"])
    if not transcript.get("success"):
        return jsonify({"success": False, "error": f"转写失败: {transcript.get('error')}"})

    # 3. AI 处理
    ai_result = _ai_process(transcript["text"], resolve_result.get("title", ""))

    # 4. 发送邮件
    result = sender.send_transcript(
        to_addr=to_addr,
        title=ai_result["title"],
        author=resolve_result.get("author", ""),
        source_url=url,
        duration=resolve_result.get("duration", 0),
        text=ai_result["corrected"],
        summary=ai_result["summary"],
    )
    if result.success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "error": result.error})


@app.route("/api/download")
def api_download():
    """接口5: 代理下载视频（绕过抖音 Referer 防盗链）
    
    请求: GET /api/download?url=播放地址&title=视频标题(可选)
    响应: 视频文件流
    """
    video_url = request.args.get("url", "").strip()
    title = request.args.get("title", "video").strip() or "video"
    if not video_url:
        return jsonify({"success": False, "error": "缺少 url 参数"}), 400

    import re
    from urllib.parse import quote
    # 清理文件名，只保留中文、英文、数字、下划线和连字符
    safe_title = re.sub(r'[^\w\u4e00-\u9fff\-]', '_', title)[:60]
    # URL 编码文件名，支持中文
    encoded_title = quote(safe_title)

    try:
        # 使用移动端 UA 和 Referer，模拟手机浏览器访问
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/116.0.0.0 Mobile Safari/537.36"
            ),
            "referer": "https://www.douyin.com/",
        }
        
        # 请求视频，allow_redirects=True 会自动跟踪 302 重定向到 CDN
        upstream = http_requests.get(
            video_url, 
            headers=headers, 
            stream=True, 
            timeout=30, 
            allow_redirects=True
        )
        
        if upstream.status_code != 200:
            logger.error(f"上游返回 {upstream.status_code}: {video_url}")
            return jsonify({"success": False, "error": f"上游返回 {upstream.status_code}"}), 502

        content_type = upstream.headers.get("Content-Type", "video/mp4")
        content_length = upstream.headers.get("Content-Length", "")

        resp_headers = {
            "Content-Type": content_type,
            "Content-Disposition": f'attachment; filename="{encoded_title}.mp4"; filename*=UTF-8\'\'{encoded_title}.mp4',
        }
        if content_length:
            resp_headers["Content-Length"] = content_length

        # 流式返回视频内容
        return Response(upstream.iter_content(chunk_size=65536), headers=resp_headers)
        
    except http_requests.RequestException as e:
        logger.error(f"下载失败: {video_url} - {e}")
        return jsonify({"success": False, "error": str(e)}), 502


@app.route("/health")
def health():
    """健康检查"""
    return jsonify({
        "status": "ok",
        "transcribe": Config.is_transcribe_enabled(),
        "ai": Config.is_ai_enabled(),
        "feishu": Config.is_feishu_enabled(),
        "email": Config.is_email_enabled(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3102))
    print(f"\n🔌 抖音视频解析 API 服务已启动")
    print(f"   端口: {port}")
    print(f"   接口:")
    print(f"   POST /api/resolve      - 解析下载地址")
    print(f"   POST /api/transcript   - 获取文案(转写+AI)")
    print(f"   POST /api/save_feishu  - 保存到飞书")
    print(f"   POST /api/email        - 发送邮件")
    print(f"   GET  /api/download     - 代理下载视频")
    print(f"   GET  /health           - 健康检查")
    print()
    app.run(host="0.0.0.0", port=port, debug=False)
