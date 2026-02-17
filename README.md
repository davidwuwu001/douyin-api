# 抖音视频解析 API

纯 JSON API 服务，专为飞书多维表格等外部系统调用设计。

## 接口列表

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/resolve` | POST | 解析视频下载地址、标题、作者 |
| `/api/transcript` | POST | 解析 + 转写 + AI润色，返回完整文案 |
| `/api/save_feishu` | POST | 解析 + 转写 + AI润色 + 保存飞书文档 |
| `/api/email` | POST | 解析 + 转写 + AI润色 + 发送邮件 |
| `/health` | GET | 健康检查 |

## 请求格式

所有 POST 接口统一请求格式：

```json
{
  "url": "抖音链接或分享文本",
  "to": "收件人邮箱（仅 /api/email 需要，可选）"
}
```

## 响应示例

### /api/resolve
```json
{
  "success": true,
  "title": "视频标题",
  "author": "作者昵称",
  "aweme_id": "7606346524510997787",
  "play_url": "https://www.douyin.com/aweme/v1/play/?video_id=xxx",
  "duration": 125.3
}
```

### /api/transcript
```json
{
  "success": true,
  "title": "视频标题",
  "author": "作者昵称",
  "duration": 125.3,
  "text": "AI纠错后的完整文字稿",
  "summary": "AI生成的内容摘要",
  "play_url": "下载地址"
}
```

## 部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动
gunicorn -w 2 -b 0.0.0.0:3102 --timeout 180 app:app
```

## 飞书多维表格集成

在多维表格中使用「自动化」功能：
1. 触发条件：当某行的「链接」字段被填写时
2. 动作：发送 HTTP 请求到 `http://你的服务器:3102/api/transcript`
3. 请求体：`{"url": "{{链接字段}}"}`
4. 将响应中的 title、author、text、summary 回填到对应列
