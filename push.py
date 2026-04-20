#!/usr/bin/env python3
"""
推送通知模块
支持：WxPusher, Telegram, 飞书
"""

import os
import json
import logging
from urllib import parse
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- WxPusher ---  https://wxpusher.zjiecode.com/admin/
# WxPusher_Token 格式: 多个 token 用逗号分隔
WXPUSHER_TOKEN = os.environ.get("WXPUSHER_TOKEN", "").strip()
WXPUSHER_UID = os.environ.get("WXPUSHER_UID", "").strip()

# --- Telegram ---  https://t.me/BotFather
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()

# --- 飞书 ---  https://open.feishu.cn/  (开发者后台 -> 机器人)
LARK_TOKEN = os.environ.get("LARK_TOKEN", "").strip()

# 全局开关
PUSH_ENABLED = os.environ.get("PUSH_ENABLED", "true").strip().lower() == "true"


def push_wx(text: str):
    """WxPusher 推送"""
    if not WXPUSHER_TOKEN or not WXPUSHER_UID:
        return
    url = "https://wxpusher.zjiecode.com/api/send/message"
    data = {
        "appToken": WXPUSHER_TOKEN,
        "content": text,
        "summary": text[:100],  # 消息摘要，显示在微信聊天列表
        "contentType": 1,  # 1:文本  2:html  3:markdown
        "uids": WXPUSHER_UID.split(","),
        "url": "",  # 点击消息跳转到的地址
    }
    try:
        r = requests.post(url, json=data, timeout=10)
        res = r.json()
        if res.get("code") == 1000:
            logger.info("WxPusher 推送成功")
        else:
            logger.warning(f"WxPusher 推送失败: {res}")
    except Exception as e:
        logger.error(f"WxPusher 推送异常: {e}")


def push_telegram(text: str):
    """Telegram 推送"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "MarkdownV2",
    }
    try:
        r = requests.post(url, json=data, timeout=10)
        res = r.json()
        if res.get("ok"):
            logger.info("Telegram 推送成功")
        else:
            logger.warning(f"Telegram 推送失败: {res}")
    except Exception as e:
        logger.error(f"Telegram 推送异常: {e}")


def push_lark(text: str):
    """飞书推送"""
    if not LARK_TOKEN:
        return
    url = "https://open.feishu.cn/open-apis/bot/v2/hook/" + LARK_TOKEN
    data = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }
    try:
        r = requests.post(url, json=data, timeout=10)
        res = r.json()
        if res.get("code") == 0:
            logger.info("飞书 推送成功")
        else:
            logger.warning(f"飞书 推送失败: {res}")
    except Exception as e:
        logger.error(f"飞书 推送异常: {e}")


def push_success(text: str):
    """成功通知"""
    if not PUSH_ENABLED:
        logger.info("推送已禁用")
        return
    push_wx(text)
    push_telegram(text)
    push_lark(text)


def push_failure(text: str):
    """失败通知"""
    if not PUSH_ENABLED:
        logger.info("推送已禁用")
        return
    push_wx(text)
    push_telegram(text)
    push_lark(text)
