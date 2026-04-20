# Right.com.cn 论坛每日自动签到脚本

自动签到 `https://www.right.com.cn/forum/forum.php` 论坛，支持推送通知。

## 功能特点

- ✅ 自动签到，支持 Discuz 论坛
- ✅ 智能检测登录状态
- ✅ 自动提取 formhash
- ✅ 支持多种签到页面路径
- ✅ 支持多种签到参数组合
- ✅ 智能解码响应（支持 GBK、UTF-8）
- ✅ 随机延迟签到（防 ban）
- ✅ 多平台推送通知（微信、Telegram、飞书）
- ✅ 详细的签到统计信息
- ✅ 支持自定义签到消息

## 环境变量

| 环境变量 | 说明 | 默认值 | 必须 |
|---------|------|-------|------|
| `COOKIE_RIGHT_FORUM` | 登录后的 Cookie（浏览器复制或 Netscape 格式） | - | ✅ |
| `SIGN_MAX_DELAY` | 最大随机延迟秒数（防 ban） | 0 | ❌ |
| `PUSH_ENABLED` | 是否启用推送通知 | true | ❌ |
| `WXPUSHER_TOKEN` | WxPusher 推送 token | - | ❌ |
| `WXPUSHER_UID` | WxPusher 用户 UID | - | ❌ |
| `TG_BOT_TOKEN` | Telegram 机器人 token | - | ❌ |
| `TG_CHAT_ID` | Telegram 聊天 ID | - | ❌ |
| `LARK_TOKEN` | 飞书机器人 token | - | ❌ |
| `RIGHT_FORUM_URL` | 论坛地址（默认 https://www.right.com.cn/forum） | - | ❌ |

## 获取 Cookie

1. 打开浏览器，登录 `https://www.right.com.cn/forum/forum.php`
2. 按 F12 打开开发者工具
3. 进入 Network 标签页
4. 刷新页面，找到 `forum.php` 请求
5. 复制 `Cookie` 字段的值
6. 将值粘贴到 `COOKIE_RIGHT_FORUM` 环境变量

## 部署方式

### 方法 1：GitHub Actions（推荐）

1. **Fork 此仓库**
2. **设置 Secrets**：
   - 进入仓库 → Settings → Secrets and variables → Actions
   - New repository secret
   - 名称：`COOKIE_RIGHT_FORUM`，值：你的 Cookie
   - 其他推送相关的 Secrets 按需设置
3. **启用 Actions**：
   - 进入 Actions 标签页
   - 点击 "I understand my workflows, go ahead and run them"
   - 工作流会在每天 00:30 自动运行

### 方法 2：本地运行

```bash
# 安装依赖
pip install requests

# 设置环境变量
export COOKIE_RIGHT_FORUM="你的 Cookie"

# 运行签到
python sign.py
```

## 签到时间

默认每天 **00:30**（北京时间）自动签到。

可在 `.github/workflows/sign.yml` 中修改 cron 表达式。

## 推送通知

### WxPusher（微信通知）
1. 访问 https://wxpusher.zjiecode.com/admin/
2. 创建应用，获取 `appToken`
3. 关注 "WxPusher" 公众号
4. 在应用的 "用户管理" 中获取用户 UID
5. 设置 `WXPUSHER_TOKEN` 和 `WXPUSHER_UID` 环境变量

### Telegram（电报通知）
1. 搜索 @BotFather，创建机器人获取 token
2. 搜索 @userinfobot，获取你的 chat_id
3. 设置 `TG_BOT_TOKEN` 和 `TG_CHAT_ID` 环境变量

### 飞书通知
1. 登录飞书开发者后台 https://open.feishu.cn/
2. 创建机器人，获取 webhook token
3. 设置 `LARK_TOKEN` 环境变量

## 随机延迟

为了避免被网站检测为机器人，可设置 `SIGN_MAX_DELAY` 环境变量：
- `0`：立即签到（默认）
- `300`：最多延迟 5 分钟
- `1800`：最多延迟 30 分钟

每天基于日期做种子，同一天的延迟时间固定。

## 常见问题

### 签到失败
- **Cookie 过期**：重新获取并更新 `COOKIE_RIGHT_FORUM`
- **网络问题**：检查网络连接
- **网站改版**：可能需要更新脚本

### 推送失败
- 检查推送服务的 token 是否正确
- 检查网络连接

## 日志

- GitHub Actions 运行历史可在 Actions 标签页查看
- 本地运行时会在控制台输出详细日志

## 免责声明

- 本脚本仅供学习交流使用
- 请勿频繁运行，以免给网站造成负担
- 请遵守网站的用户协议
- 作者不对使用本脚本产生的任何后果负责
