"""数据模型定义

定义系统中所有核心数据结构，每个 dataclass 都支持 to_dict() / from_dict() 的 JSON 序列化。
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class VideoRecord:
    """视频记录"""
    title: str
    url: str
    like_count: str = ""
    cover_url: str = ""
    is_pinned: bool = False
    aweme_id: str = ""
    video_play_url: str = ""
    duration_seconds: float = 0.0
    author: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "like_count": self.like_count,
            "cover_url": self.cover_url,
            "is_pinned": self.is_pinned,
            "aweme_id": self.aweme_id,
            "video_play_url": self.video_play_url,
            "duration_seconds": self.duration_seconds,
            "author": self.author,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "VideoRecord":
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            like_count=data.get("like_count", ""),
            cover_url=data.get("cover_url", ""),
            is_pinned=data.get("is_pinned", False),
            aweme_id=data.get("aweme_id", ""),
            video_play_url=data.get("video_play_url", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            author=data.get("author", ""),
        )


@dataclass
class BloggerProfile:
    """博主资料"""
    name: str
    following: str = ""
    followers: str = ""
    total_likes: str = ""
    works_count: str = ""
    douyin_id: str = ""
    ip_location: str = ""
    gender: str = ""
    location: str = ""
    bio: str = ""
    age: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "following": self.following,
            "followers": self.followers,
            "total_likes": self.total_likes,
            "works_count": self.works_count,
            "douyin_id": self.douyin_id,
            "ip_location": self.ip_location,
            "gender": self.gender,
            "location": self.location,
            "bio": self.bio,
            "age": self.age,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BloggerProfile":
        return cls(
            name=data.get("name", ""),
            following=data.get("following", ""),
            followers=data.get("followers", ""),
            total_likes=data.get("total_likes", ""),
            works_count=data.get("works_count", ""),
            douyin_id=data.get("douyin_id", ""),
            ip_location=data.get("ip_location", ""),
            gender=data.get("gender", ""),
            location=data.get("location", ""),
            bio=data.get("bio", ""),
            age=data.get("age", ""),
        )


@dataclass
class BloggerData:
    """博主抓取数据"""
    name: str
    url: str
    profile: BloggerProfile
    videos: List[VideoRecord] = field(default_factory=list)
    fetched_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "profile": self.profile.to_dict(),
            "videos": [v.to_dict() for v in self.videos],
            "fetched_at": self.fetched_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BloggerData":
        return cls(
            name=data.get("name", ""),
            url=data.get("url", ""),
            profile=BloggerProfile.from_dict(data.get("profile", {"name": ""})),
            videos=[VideoRecord.from_dict(v) for v in data.get("videos", [])],
            fetched_at=data.get("fetched_at", ""),
            error=data.get("error"),
        )


@dataclass
class TranscriptResult:
    """视频转录结果"""
    video_url: str
    video_title: str
    text: str
    duration_seconds: float = 0.0
    transcribed_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "video_url": self.video_url,
            "video_title": self.video_title,
            "text": self.text,
            "duration_seconds": self.duration_seconds,
            "transcribed_at": self.transcribed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptResult":
        return cls(
            video_url=data.get("video_url", ""),
            video_title=data.get("video_title", ""),
            text=data.get("text", ""),
            duration_seconds=data.get("duration_seconds", 0.0),
            transcribed_at=data.get("transcribed_at", ""),
            error=data.get("error"),
        )


@dataclass
class SummaryResult:
    """AI 摘要结果"""
    video_url: str
    video_title: str
    blogger_name: str
    summary: str
    key_points: List[str] = field(default_factory=list)
    summarized_at: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "video_url": self.video_url,
            "video_title": self.video_title,
            "blogger_name": self.blogger_name,
            "summary": self.summary,
            "key_points": list(self.key_points),
            "summarized_at": self.summarized_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SummaryResult":
        return cls(
            video_url=data.get("video_url", ""),
            video_title=data.get("video_title", ""),
            blogger_name=data.get("blogger_name", ""),
            summary=data.get("summary", ""),
            key_points=list(data.get("key_points", [])),
            summarized_at=data.get("summarized_at", ""),
            error=data.get("error"),
        )


@dataclass
class ReportEntry:
    """报告中的单个博主条目"""
    blogger_name: str
    blogger_url: str
    profile: BloggerProfile
    videos: List[dict] = field(default_factory=list)  # 每个 dict 包含 video, transcript, summary

    def to_dict(self) -> dict:
        return {
            "blogger_name": self.blogger_name,
            "blogger_url": self.blogger_url,
            "profile": self.profile.to_dict(),
            "videos": list(self.videos),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReportEntry":
        return cls(
            blogger_name=data.get("blogger_name", ""),
            blogger_url=data.get("blogger_url", ""),
            profile=BloggerProfile.from_dict(data.get("profile", {"name": ""})),
            videos=list(data.get("videos", [])),
        )


@dataclass
class Report:
    """日报/周报"""
    report_type: str  # "daily" | "weekly"
    date: str
    entries: List[ReportEntry] = field(default_factory=list)
    total_bloggers: int = 0
    total_new_videos: int = 0
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "report_type": self.report_type,
            "date": self.date,
            "entries": [e.to_dict() for e in self.entries],
            "total_bloggers": self.total_bloggers,
            "total_new_videos": self.total_new_videos,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Report":
        return cls(
            report_type=data.get("report_type", ""),
            date=data.get("date", ""),
            entries=[ReportEntry.from_dict(e) for e in data.get("entries", [])],
            total_bloggers=data.get("total_bloggers", 0),
            total_new_videos=data.get("total_new_videos", 0),
            generated_at=data.get("generated_at", ""),
        )
