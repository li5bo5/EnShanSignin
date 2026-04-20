#!/usr/bin/env python3
"""
Right.com.cn 论坛每日自动签到脚本
Discuz 论坛 + 签到功能
"""

import re
import os
import sys
import time
import random
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from push import push_success, push_failure

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_URL = os.environ.get("RIGHT_FORUM_URL", "https://www.right.com.cn/forum").rstrip('/')
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)

# 签到消息
MESSAGES = [
    "签到打卡，天天向上！",
    "每日签到，习惯养成！",
    "今天也要加油鸭！",
    "签到签到，金币到手！",
    "坚持签到，贵在坚持！",
    "每日一签，好运连连！",
    "签到成功，继续努力！",
]


def build_session(cookie_str: str) -> requests.Session:
    """
    从 COOKIE_RIGHT_FORUM 环境变量构建带 cookie 的 requests.Session。
    兼容两种 cookie 格式：
      1. "key=val; key2=val2"  （浏览器直接复制）
      2. Netscape cookie 格式（多行，tab 分隔）
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })

    # 设置重试
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))

    parsed = urlparse(BASE_URL)
    base_domain = parsed.hostname  # e.g. "www.right.com.cn"

    # 解析 cookie 字符串
    cookies_dict = {}
    lines = cookie_str.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Netscape 格式: domain  TRUE  /  FALSE  0  name  value
        if "\t" in line:
            parts = line.split("\t")
            if len(parts) >= 7:
                name = parts[5].strip()
                value = parts[6].strip()
                cookies_dict[name] = value
            continue

        # 标准 "key=val; key2=val2" 格式
        for pair in line.split("; "):
            pair = pair.strip()
            if "=" in pair:
                name, _, value = pair.partition("=")
                name = name.strip()
                value = value.strip()
                if name:
                    cookies_dict[name] = value

    if not cookies_dict:
        logger.error("No cookies parsed from COOKIE_RIGHT_FORUM")
        sys.exit(1)

    logger.info(f"Parsed {len(cookies_dict)} cookies: {list(cookies_dict.keys())}")

    # 设置 cookie，兼容 www 和非 www 域名
    for name, value in cookies_dict.items():
        s.cookies.set(name, value, domain=base_domain, path="/")
        # 同时设置另一个域名变体（www <-> 非 www）
        if base_domain.startswith("www."):
            alt_domain = base_domain[4:]  # right.com.cn
        else:
            alt_domain = "www." + base_domain
        s.cookies.set(name, value, domain=alt_domain, path="/")
        # 也设置无域名限制
        s.cookies.set(name, value, path="/")

    return s


def check_login(session: requests.Session) -> str | None:
    """检查登录状态，返回用户名"""
    logger.info("Checking login...")
    try:
        r = session.get(f"{BASE_URL}/forum.php", timeout=15, allow_redirects=True)
        body = decode_response(r)
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None

    # 调试：输出响应状态和关键信息
    logger.info(f"Response status: {r.status_code}, final URL: {r.url}")
    logger.info(f"Response length: {len(body)} chars")

    # 检测 Cloudflare 保护
    if r.status_code == 521 or 'window.onload=setTimeout' in body or 'Cloudflare' in body:
        logger.warning("Cloudflare protection detected. Trying to bypass...")
        # 尝试使用更真实的浏览器模拟
        session.headers.update({
            "Referer": BASE_URL,
            "Origin": BASE_URL,
        })
        # 尝试再次请求
        try:
            r = session.get(f"{BASE_URL}/forum.php", timeout=15, allow_redirects=True)
            body = decode_response(r)
            logger.info(f"Second response status: {r.status_code}")
        except Exception as e:
            logger.error(f"Second request failed: {e}")
            return None

    # 检查登录标记
    if "退出" in body or "注销" in body or "logging" in body:
        # 多种方式提取用户名
        patterns = [
            r'<a[^>]*href="[^" ]*space-uid-\d+[^" ]*"[^>]*>([^<]+)</a>',
            r'title="([^"]+)"[^>]*class="[^" ]*vwmy[^" ]*"',
            r'<a[^>]*id="umenu"[^>]*>([^<]+)</a>',
            r'welcomemessage[^>]*>([^<]+)<',
            r'<em[^>]*>([^<]{2,20})</em>',
            r'title="[^"]*"[^>]*>([^<]+)<',
        ]
        for pat in patterns:
            m = re.search(pat, body)
            if m and m.group(1).strip():
                username = m.group(1).strip()
                logger.info(f"Logged in as: {username}")
                return username

        logger.info("Logged in (username not extracted)")
        return "unknown"

    # 输出调试信息帮助排查
    if len(body) < 500:
        logger.warning(f"Short response body: {body[:300]}")
    elif len(body) > 500:
        logger.warning(f"Response body sample: {body[:500]}")

    logger.warning("Cookie expired or invalid — no login markers found")
    return None


def get_formhash(session: requests.Session) -> str | None:
    """获取 Discuz formhash"""
    try:
        r = session.get(f"{BASE_URL}/forum.php", timeout=15)
        body = decode_response(r)
        m = re.search(r'name="formhash"\s+value="(\w+)"', body)
        if m:
            fh = m.group(1)
            logger.info(f"formhash: {fh}")
            return fh
    except Exception as e:
        logger.error(f"Failed to get formhash: {e}")
    logger.warning("formhash not found")
    return None


def decode_response(r: requests.Response) -> str:
    """智能解码响应：优先从 XML/HTML 声明检测编码"""
    raw = r.content

    # 尝试从 XML 声明提取编码
    m = re.search(rb'<\?xml[^>]+encoding=["\']([^"\']+)', raw[:200])
    if m:
        enc = m.group(1).decode("ascii", errors="ignore").lower()
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            pass

    # 尝试从 Content-Type 提取
    ct = r.headers.get("Content-Type", "")
    m = re.search(r'charset=([^\s;]+)', ct, re.I)
    if m:
        enc = m.group(1).lower()
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            pass

    # Discuz 论坛默认 GBK，优先尝试
    for enc in ("gbk", "gb2312", "gb18030", "utf-8"):
        try:
            text = raw.decode(enc)
            # 简单验证：如果包含常见中文且不包含 replacement char
            if "\ufffd" not in text[:500] or enc == "utf-8":
                return text
        except (UnicodeDecodeError, LookupError):
            continue

    return raw.decode("utf-8", errors="replace")


def extract_sign_stats(body: str) -> dict:
    """从签到页/签到响应中提取签到统计信息"""
    stats = {}

    # 连续签到天数
    patterns = [
        r'连续签到[：:]\s*(\d+)\s*天',
        r'连续[：:]\s*(\d+)',
        r'连续(\d+)天',
        r'lianday[^>]*>(\d+)',
        r'连续.*?(\d+)',
    ]
    for p in patterns:
        m = re.search(p, body)
        if m:
            stats["continuous"] = int(m.group(1))
            break

    # 累计签到天数
    patterns = [
        r'累计签到[：:]\s*(\d+)\s*天',
        r'累计[：:]\s*(\d+)',
        r'累计(\d+)天',
        r'totaldays[^>]*>(\d+)',
        r'总签[：:]\s*(\d+)',
        r'累计.*?(\d+)',
    ]
    for p in patterns:
        m = re.search(p, body)
        if m:
            stats["total"] = int(m.group(1))
            break

    # 等级
    patterns = [
        r'等级[：:]\s*([^\s<,，]+)',
        r'level[：:]\s*([^\s<,，]+)',
        r'级别[：:]\s*([^\s<,，]+)',
    ]
    for p in patterns:
        m = re.search(p, body)
        if m:
            stats["level"] = m.group(1).strip()
            break

    # 奖励（金币/铜币/威望）
    patterns = [
        r'获得[^<]*?(\d+)\s*(?:个?)?(?:金币|铜币|威望|积分)',
        r'奖励[^<]*?(\d+)\s*(?:个?)?(?:金币|铜币|威望|积分)',
    ]
    for p in patterns:
        m = re.search(p, body)
        if m:
            stats["reward"] = m.group(0).strip()
            stats["coins"] = int(m.group(1))
            break

    return stats


def do_sign(session: requests.Session, formhash: str) -> tuple[bool, str, dict]:
    """Discuz 签到 POST 签到，返回 (成功, 消息, 统计信息)"""
    logger.info("Signing in...")
    
    # 尝试不同的签到页面路径
    sign_paths = [
        "/erling_qd-sign_in.html",
        "/plugin.php?id=dsu_paulsign:sign",
        "/plugin.php?id=签到插件ID:sign",
        "/forum.php?mod=sign",
        "/sign.php",
    ]
    
    sign_url = None
    for path in sign_paths:
        try:
            test_url = f"{BASE_URL}{path}"
            r = session.get(test_url, timeout=15, headers={
                "Referer": f"{BASE_URL}/forum.php",
            })
            body = decode_response(r)
            if "签到" in body or "qiandao" in r.url:
                sign_url = test_url
                logger.info(f"Found sign page: {sign_url}")
                break
        except Exception as e:
            logger.warning(f"Test path {path} failed: {e}")
            continue
    
    if not sign_url:
        return False, "Cannot find sign page", {}
    
    try:
        r = session.get(sign_url, timeout=15, headers={
            "Referer": f"{BASE_URL}/forum.php",
        })
        page_body = decode_response(r)
    except Exception as e:
        return False, f"Cannot access sign page: {e}", {}

    # 更准确地检测用户个人的签到状态
    # 避免误判页面上的统计信息（如"今日已签到：3406人"）
    logger.info("Checking sign status...")
    
    # 检查是否存在"立即签到"按钮
    if "立即签到" in page_body:
        logger.info("Found '立即签到' button - user not signed yet")
    else:
        logger.info("No '立即签到' button found - user may already signed")
    
    # 检查是否已经签到
    is_signed = False
    
    # 检查个人签到状态
    personal_sign_patterns = [
        r'您已签到',
        r'个人已签到',
        r'今日已签',
        r'已经签到',
        r'签到成功',
        r'已完成签到',
    ]
    
    for pattern in personal_sign_patterns:
        if pattern in page_body:
            # 检查是否是统计信息，避免误判
            if (pattern == "今日已签" or pattern == "今日已签到") and "今日已签到：" in page_body:
                # 这是统计信息，不是个人签到状态
                logger.info(f"Found statistical info: {pattern}")
                continue
            is_signed = True
            logger.info(f"Found personal sign status: {pattern}")
            break
    
    if is_signed:
        stats = extract_sign_stats(page_body)
        logger.info(f"Already signed, stats: {stats}")
        return True, "今日已签到", stats
    
    # 如果存在"立即签到"按钮，说明用户还没有签到
    if "立即签到" in page_body:
        logger.info("User not signed yet, proceeding to sign")

    # 从签到页提取可用的心情值（如果有）
    mood_options = re.findall(r'name="qdxq"\s+value="(\w+)"', page_body)
    if not mood_options:
        mood_options = re.findall(r'qdxq.*?value="(\w+)"', page_body)
    
    # 尝试不同的签到参数
    sign_params = [
        # 二零CMS 签到系统 - 直接提交
        {
            "url": sign_url,
            "data": {
                "formhash": formhash,
                "submit": "立即签到",
                "mod": "plugin",
                "id": "erling_qd:sign_in",
            }
        },
        # 二零CMS 签到系统 - 带操作参数
        {
            "url": sign_url,
            "data": {
                "formhash": formhash,
                "operation": "qiandao",
                "submit": "立即签到",
            }
        },
        # 通用签到
        {
            "url": sign_url,
            "data": {
                "formhash": formhash,
                "submit": "签到",
            }
        },
        # 标准 dsu_paulsign
        {
            "url": f"{BASE_URL}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1",
            "data": {
                "formhash": formhash,
                "qdxq": random.choice(mood_options) if mood_options else "kx",
                "qdmode": 1,
                "faession": "1",
                "todaysay": random.choice(MESSAGES),
                "fastreply": "0",
            }
        },
    ]

    for params in sign_params:
        try:
            r = session.post(params["url"], data=params["data"], headers={
                "Referer": sign_url,
                "X-Requested-With": "XMLHttpRequest",
            }, timeout=15)
            body = decode_response(r)
        except Exception as e:
            logger.error(f"Sign request failed: {e}")
            continue

        logger.info(f"Response ({len(body)} chars): {body[:500]}")

        # 检查是否是统计信息，避免误判
        if "今日已签" in body and "今日已签到：" in body:
            logger.info("Response contains statistical info, not personal sign status")
        elif "今日已签" in body or "已经签到" in body:
            stats = extract_sign_stats(body)
            logger.info(f"Sign status detected: 今日已签, stats: {stats}")
            return True, "今日已签到", stats

        # 签到成功
        if "签到成功" in body or "恭喜" in body or "获得" in body:
            stats = extract_sign_stats(body)
            logger.info(f"Sign success detected: {stats}")
            return True, "签到成功", stats

        # Discuz 签到弹窗：有"签到提示"标题 + hideWindow = 成功
        if "签到提示" in body and "hideWindow" in body:
            stats = extract_sign_stats(body)
            logger.info(f"Sign popup success: {stats}")
            return True, "签到成功", stats

        # 二零CMS 签到成功
        if "签到成功" in body or "获得" in body or "积分" in body:
            stats = extract_sign_stats(body)
            logger.info(f"二零CMS sign success: {stats}")
            return True, "签到成功", stats

        if "不正确" in body or "请重新选择" in body:
            logger.info("Mood rejected, trying next...")
            continue

        if "未登录" in body or "请先登录" in body:
            return False, "Cookie expired", {}

        # 输出详细的响应内容，帮助调试
        logger.info(f"Full response sample: {body[:1000]}")

    return False, "All sign attempts failed", {}


def notify(result: bool, message: str, username: str = "", stats: dict = None):
    """发送通知 — Right.com.cn 签到模板"""
    if stats is None:
        stats = {}
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    now_str = now.strftime("%Y-%m-%d %H:%M")

    print("")
    print("=" * 50)
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} (CST)  Result: {'✅' if result else '❌'} {message}")
    print(f"URL:  {BASE_URL}")
    if result:
        print(f"OK:   {message}")
    else:
        print(f"FAIL: {message}")
    print("=" * 50)

    gh_output = os.environ.get("GITHUB_OUTPUT")
    if gh_output:
        with open(gh_output, "a") as f:
            f.write(f"sign_result={'success' if result else 'failed'}\n")
            f.write(f"sign_message={message}\n")
            f.write(f"sign_time={now_str}\n")

    # --- 推送模板 ---
    if result:
        user_line = username if username and username != "unknown" else "未知用户"

        # 构建奖励行
        if stats.get("coins"):
            reward_line = f"获得 {stats['coins']} 积分"
        elif stats.get("reward"):
            reward_line = stats["reward"]
        else:
            reward_line = "签到成功"

        # 构建统计行
        parts = []
        if stats.get("continuous"):
            parts.append(f"连续{stats['continuous']}天")
        if stats.get("total"):
            parts.append(f"累计{stats['total']}天")
        if stats.get("level"):
            parts.append(f"等级: {stats['level']}")
        stats_line = " | ".join(parts) if parts else ""

        summary = f"✅ Right.com.cn 签到成功\n\n签到时间: {now_str}\n\n{user_line}\n✅ {reward_line} ({now_str})"
        if stats_line:
            summary += f"\n📊 {stats_line}"
        push_success(summary)
    else:
        summary = (
            f"❌ Right.com.cn 签到失败\n\n"
            f"签到时间: {now_str}\n\n"
            f"原因: {message}\n"
            f"URL: {BASE_URL}"
        )
        push_failure(summary)


def random_delay():
    """
    随机延迟后签到
    SIGN_MAX_DELAY 环境变量设定最大延迟秒数：
      未设置/空 → 默认0秒(立即签到)
      0         → 立即签到
      60        → 最多等60秒
      1800      → 最多等30分钟
    每天基于日期做种子，同一天延迟固定
    """
    max_delay_env = os.environ.get("SIGN_MAX_DELAY", "").strip()
    try:
        max_delay = int(max_delay_env) if max_delay_env else 0
    except ValueError:
        logger.warning(f"SIGN_MAX_DELAY 值无效: {max_delay_env!r}，使用默认 0 秒")
        max_delay = 0
    if max_delay < 0:
        max_delay = 0

    cst = timezone(timedelta(hours=8))
    today = datetime.now(cst).strftime("%Y-%m-%d")
    rng = random.Random(today)
    delay = rng.randint(0, max_delay)

    if delay == 0:
        print("⚡ 立即签到（延迟 0 秒）")
    else:
        minutes = delay // 60
        seconds = delay % 60
        print(f"⏳ 随机延迟 {minutes}分{seconds}秒（上限 {max_delay} 秒）")
    time.sleep(delay)


def main():
    sign_max = os.environ.get("SIGN_MAX_DELAY", "").strip()
    print("=" * 50)
    print("right-forum auto sign-in")
    print(f"URL: {BASE_URL}")
    print(f"SIGN_MAX_DELAY: {sign_max or '0'}s")
    print("=" * 50)

    # 随机延迟
    random_delay()

    cookie_str = os.environ.get("COOKIE_RIGHT_FORUM", "").strip()
    if not cookie_str:
        logger.error("COOKIE_RIGHT_FORUM not set")
        notify(False, "COOKIE_RIGHT_FORUM 环境变量未设置")
        sys.exit(1)

    session = build_session(cookie_str)

    username = check_login(session)
    if not username:
        notify(False, "Cookie invalid or expired")
        sys.exit(1)

    formhash = get_formhash(session)
    if not formhash:
        notify(False, "Cannot get formhash", username)
        sys.exit(1)

    success, message, stats = do_sign(session, formhash)
    notify(success, message, username, stats)

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
