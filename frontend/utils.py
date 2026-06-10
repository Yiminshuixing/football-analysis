"""前端工具函数"""
import httpx
import streamlit as st
from typing import Optional, List, Dict, Any
from datetime import datetime


# API 基础地址
def get_api_base() -> str:
    """获取 API 基础地址"""
    try:
        if "api_base" in st.secrets:
            return st.secrets["api_base"]
    except Exception:
        pass  # 没有 secrets 文件时使用默认地址
    return "http://localhost:8000"


def api_get(endpoint: str, params: dict = None) -> Optional[Any]:
    """调用后端 API (GET)"""
    url = f"{get_api_base()}/api{endpoint}"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params)
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception as e:
        st.error(f"API 请求失败: {e}")
        return None


def api_post(endpoint: str, params: dict = None, json_body: dict = None) -> Optional[Any]:
    """调用后端 API (POST)

    Args:
        endpoint: API 路径
        params: URL 查询参数（可选）
        json_body: JSON 请求体（可选）

    注意：
    - 如果后端使用 Query(...) 接收参数，用 params= 传
    - 如果后端使用 Pydantic BaseModel 接收，用 json_body= 传
    """
    url = f"{get_api_base()}/api{endpoint}"
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, params=params, json=json_body)
            if resp.status_code == 200:
                return resp.json()
            st.error(f"API 错误 ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        st.error(f"API 请求失败: {e}")
        return None


def format_match_time(utc_date_str: str) -> str:
    """格式化比赛时间"""
    try:
        dt = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00"))
        return dt.strftime("%m/%d %H:%M")
    except:
        return utc_date_str


def get_outcome_label(outcome: str) -> str:
    """获取结果中文标签"""
    labels = {"HOME": "主胜", "DRAW": "平局", "AWAY": "客胜"}
    return labels.get(outcome, outcome)


def get_outcome_emoji(outcome: str) -> str:
    """获取结果 emoji"""
    emojis = {"HOME": "🏠", "DRAW": "🤝", "AWAY": "✈️"}
    return emojis.get(outcome, "❓")


def probability_bar(prob: float, width: int = 200) -> str:
    """生成概率进度条（纯文本）"""
    filled = int(prob * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"{bar} {prob:.1%}"
