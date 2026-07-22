"""
models.py — 統一評論資料結構
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


@dataclass
class Review:
    platform: str       # "Google Play" | "App Store"
    date: datetime      # 台北時間 (UTC+8)
    username: str
    rating: int         # 1–5
    version: str        # App 版本號，例如 "4.17.0"
    title: Optional[str]   # App Store 才有標題；Google Play 為 None
    content: str        # 評論內文
    raw_id: str = ""    # 平台原生 ID（Google Play reviewId）
    reply_content: Optional[str] = None   # 官方/客服回覆內文（無回覆為 None）
    reply_date: Optional[datetime] = None # 回覆時間（台北時間）

    def dedup_key(self) -> str:
        """
        去重 Key：平台 + 日期時間（分鐘精度）+ 用戶名前 20 字元。
        與 md_writer 解析 MD 時的格式一致。
        """
        date_key = self.date.strftime("%Y%m%d%H%M")
        user_key = self.username[:20].strip()
        return f"{self.platform}|{date_key}|{user_key}"

    def content_dedup_key(self) -> str:
        """
        內容指紋：跨來源去重使用，避免 App Store HTML/RSS/AMP 因時間或版本欄位
        略有差異而把同一則評論寫入多次。
        """
        if self.raw_id and self.platform == "Google Play":
            return f"{self.platform}|id|{self.raw_id}"

        text = self.normalized_review_text()
        user_key = self.username.strip().casefold()
        return f"{self.platform}|content|{user_key}|{self.rating}|{text}"

    def normalized_review_text(self) -> str:
        """回傳去重用的標題 + 內文正規化文字。"""
        text = self.content or ""
        if self.title:
            text = f"【{self.title}】 {text}"
        text = text.replace("\n", " ").replace("|", "｜").strip()
        text = re.sub(r"\s+", " ", text)
        return text.casefold()

    def format_content_for_md(self) -> str:
        """格式化評論內容，加上標題（如有），並清理換行與豎線。"""
        text = self.content.replace("\n", " ").replace("|", "｜").strip()
        if self.title:
            title_clean = self.title.replace("|", "｜").strip()
            text = f"**【{title_clean}】** {text}"
        return text[:600]  # 限制欄位長度

    def format_reply_for_md(self) -> str:
        """格式化客服回覆為單一表格欄位文字；無回覆時回傳空字串。"""
        if not self.reply_content:
            return ""
        text = self.reply_content.replace("\n", " ").replace("|", "｜").strip()
        if not text:
            return ""
        if self.reply_date:
            date_str = self.reply_date.strftime("%Y-%m-%d")
            text = f"**[{date_str}]** {text}"
        return text[:600]  # 限制欄位長度
