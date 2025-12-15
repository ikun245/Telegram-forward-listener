# telegram_bot.py - 5.1.0 监听转发客户端 (AI炒群增强版)
# 功能: 监听转发 + AI智能炒群 + 报警 + 人工干预 + 活跃度检测

from telethon.sync import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.events import NewMessage
import asyncio
import json
import os
import sys
import random
import re
from datetime import datetime, timedelta
from collections import defaultdict, deque
from openai import AsyncOpenAI

# 用于处理媒体组的缓存和锁
media_group_cache = {}
media_group_lock = asyncio.Lock()

# 版本信息
VERSION = "5.1.0"
BANNER = f"""
╔══════════════════════════════════════════════════════════╗
║       Telegram 监听转发客户端 v{VERSION}                   ║
║       监听转发 | AI智能炒群 | 报警系统 | 人工干预           ║
╚══════════════════════════════════════════════════════════╝
"""

# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.json')


def load_config():
    """加载配置文件"""
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "api_id": "your_api_id",
            "api_hash": "your_api_hash",
            "master_account_id": 0,
            "bot_mappings": [],
            "proxy": {
                "proxy_type": "",
                "addr": "",
                "port": 0,
                "username": "",
                "password": ""
            },
            "admin_ids": [],
            "ai_chat": {
                "enabled": False,
                "api_key": "",
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
                "chats": [],
                "reply_probability": 30,
                "min_message_length": 3,
                "context_limit": 20,
                "cooldown_seconds": 30,
                "personality": "你是一个活泼开朗的年轻人，喜欢用网络用语，说话简短有趣，偶尔会用emoji。你的回复要像真人聊天一样自然，不要太正式，可以有点调皮。回复尽量简短，一般1-2句话，最多不超过50字。不要暴露自己是AI。",
                "typing_simulation": True,
                "random_emoji": True,
                "alert_keywords": ["机器人", "bot", "AI", "人工智能", "自动回复", "脚本"],
                "alert_enabled": True,
                "manual_mode": False,
                "other_ai_ids": [],
                "min_active_users": 3,
                "active_check_minutes": 10,
                "reply_delay_min": 2,
                "reply_delay_max": 5,
            }
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        print(f"⚠️ 已创建默认配置文件 {CONFIG_FILE}，请编辑后重新运行。")
        sys.exit(1)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(cfg):
    """保存配置文件"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=4)


# 加载配置
config = load_config()

api_id = config['api_id']
api_hash = config['api_hash']
master_account_id = config['master_account_id']
admin_ids = config.get('admin_ids', [])  # 额外管理员ID列表
bot_mappings = config.get('bot_mappings', [])
proxy_config = config.get('proxy', None)


def is_admin(user_id: int) -> bool:
    """检查用户是否是管理员（主账号或额外管理员）"""
    if user_id == master_account_id:
        return True
    return user_id in admin_ids

# 确保 ai_chat 配置存在
if 'ai_chat' not in config:
    config['ai_chat'] = {
        "enabled": False,
        "api_key": "",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "chats": [],
        "reply_probability": 30,
        "min_message_length": 3,
        "context_limit": 20,
        "cooldown_seconds": 30,
        "personality": "你是一个活泼开朗的年轻人，喜欢用网络用语，说话简短有趣，偶尔会用emoji。你的回复要像真人聊天一样自然，不要太正式，可以有点调皮。回复尽量简短，一般1-2句话，最多不超过50字。不要暴露自己是AI。",
        "typing_simulation": True,
        "random_emoji": True,
        "alert_keywords": ["机器人", "bot", "AI", "人工智能", "自动回复", "脚本"],
        "alert_enabled": True,
        "manual_mode": False,
        "other_ai_ids": [],
        "min_active_users": 3,
        "active_check_minutes": 10,
        "reply_delay_min": 2,
        "reply_delay_max": 5,
    }
    save_config(config)

# 确保新增配置项存在
ai_chat_defaults = {
    "alert_keywords": ["机器人", "bot", "AI", "人工智能", "自动回复", "脚本"],
    "alert_enabled": True,
    "manual_mode": False,
    "other_ai_ids": [],
    "min_active_users": 3,
    "active_check_minutes": 10,
    "reply_delay_min": 2,
    "reply_delay_max": 5,
}
for key, value in ai_chat_defaults.items():
    if key not in config['ai_chat']:
        config['ai_chat'][key] = value
        save_config(config)

# 配置代理
proxy = None
if proxy_config and proxy_config.get('proxy_type'):
    proxy_type = proxy_config['proxy_type']
    proxy_addr = proxy_config['addr']
    proxy_port = proxy_config['port']
    proxy_username = proxy_config.get('username')
    proxy_password = proxy_config.get('password')

    if proxy_type.lower() == 'socks5':
        proxy = ('socks5', proxy_addr, proxy_port, proxy_username, proxy_password)
    elif proxy_type.lower() == 'http':
        proxy = ('http', proxy_addr, proxy_port, proxy_username, proxy_password)
    else:
        print(f"⚠️ 不支持的代理类型: {proxy_type}")
        proxy = None

# 创建客户端
client = TelegramClient(os.path.join(SCRIPT_DIR, 'anon'), api_id, api_hash, proxy=proxy)

# forwarding_map 将在 main 函数中初始化
forwarding_map = {}

# 机器人运行状态
bot_running = True


class AIChatManager:
    """AI 炒群管理器"""

    def __init__(self, cfg: dict):
        self.config = cfg
        self.client = None
        self.chat_contexts = defaultdict(list)
        self.last_reply_time = defaultdict(lambda: datetime.min)
        self.my_user_id = None
        
        # 活跃度追踪 - 记录每个群组最近发言的用户
        self.recent_senders = defaultdict(lambda: deque(maxlen=50))
        
        # 报警状态
        self.alert_triggered = defaultdict(bool)
        self.alert_messages = defaultdict(list)
        
        # 待发送的人工消息队列
        self.manual_message_queue = defaultdict(list)

        self.emojis = ['😂', '🤣', '😊', '😄', '👍', '🔥', '💪', '😎', '🤔', '😏',
                       '🙃', '😜', '🤭', '😁', '👀', '💯', '✨', '🎉', '😋', '🥰',
                       '😤', '🤷', '😅', '🙈', '💀', '😭', '🤡', '👏', '🤝', '😌']

        self._init_client()

    def _init_client(self):
        """初始化 OpenAI 客户端"""
        ai_config = self.config.get('ai_chat', {})
        api_key = ai_config.get('api_key', '')
        base_url = ai_config.get('base_url', 'https://api.deepseek.com')

        if api_key and api_key not in ['', 'your_api_key', 'put your api key here']:
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
            print("✅ AI 聊天客户端已初始化")
        else:
            self.client = None
            print("ℹ️ AI 聊天 API Key 未配置")

    def update_config(self, cfg: dict):
        """更新配置"""
        self.config = cfg
        self._init_client()

    def is_enabled(self, chat_id: int) -> bool:
        """检查是否在指定群组启用了AI聊天"""
        ai_config = self.config.get('ai_chat', {})
        if not ai_config.get('enabled', False):
            return False
        # 检查是否处于人工模式
        if ai_config.get('manual_mode', False):
            return False
        return chat_id in ai_config.get('chats', [])

    def is_manual_mode(self) -> bool:
        """检查是否处于人工干预模式"""
        ai_config = self.config.get('ai_chat', {})
        return ai_config.get('manual_mode', False)

    def is_other_ai(self, user_id: int) -> bool:
        """检查是否是其他AI的ID"""
        ai_config = self.config.get('ai_chat', {})
        other_ai_ids = ai_config.get('other_ai_ids', [])
        return user_id in other_ai_ids

    def check_alert_keywords(self, message_text: str) -> tuple:
        """检查消息中是否包含报警关键词"""
        ai_config = self.config.get('ai_chat', {})
        if not ai_config.get('alert_enabled', True):
            return False, None
        
        keywords = ai_config.get('alert_keywords', [])
        message_lower = message_text.lower()
        
        for keyword in keywords:
            if keyword.lower() in message_lower:
                return True, keyword
        return False, None

    def track_sender(self, chat_id: int, sender_id: int):
        """追踪发言者"""
        now = datetime.now()
        self.recent_senders[chat_id].append({
            'sender_id': sender_id,
            'time': now
        })

    def get_active_users_count(self, chat_id: int) -> int:
        """获取指定时间段内的活跃用户数"""
        ai_config = self.config.get('ai_chat', {})
        check_minutes = ai_config.get('active_check_minutes', 10)
        cutoff_time = datetime.now() - timedelta(minutes=check_minutes)
        
        # 获取时间范围内的不同发送者
        unique_senders = set()
        for record in self.recent_senders[chat_id]:
            if record['time'] >= cutoff_time:
                unique_senders.add(record['sender_id'])
        
        return len(unique_senders)

    def should_skip_due_to_low_activity(self, chat_id: int) -> bool:
        """检查是否因活跃度过低而跳过回复"""
        ai_config = self.config.get('ai_chat', {})
        min_users = ai_config.get('min_active_users', 3)
        active_count = self.get_active_users_count(chat_id)
        return active_count < min_users

    def should_reply(self, chat_id: int, message_text: str) -> bool:
        """判断是否应该回复"""
        ai_config = self.config.get('ai_chat', {})

        min_length = ai_config.get('min_message_length', 3)
        if len(message_text.strip()) < min_length:
            return False

        cooldown = ai_config.get('cooldown_seconds', 30)
        last_time = self.last_reply_time[chat_id]
        if datetime.now() - last_time < timedelta(seconds=cooldown):
            return False

        probability = ai_config.get('reply_probability', 30)
        return random.randint(1, 100) <= probability

    def add_context(self, chat_id: int, sender_name: str, message: str, is_self: bool = False):
        """添加上下文消息"""
        ai_config = self.config.get('ai_chat', {})
        context_limit = ai_config.get('context_limit', 20)

        role = "我" if is_self else sender_name
        self.chat_contexts[chat_id].append({
            'role': role,
            'content': message,
            'time': datetime.now().strftime('%H:%M')
        })

        if len(self.chat_contexts[chat_id]) > context_limit:
            self.chat_contexts[chat_id] = self.chat_contexts[chat_id][-context_limit:]

    def _add_personality(self, text: str) -> str:
        """给回复添加个性化元素"""
        ai_config = self.config.get('ai_chat', {})

        if ai_config.get('random_emoji', False) and random.random() < 0.4:
            emoji = random.choice(self.emojis)
            if random.random() < 0.5:
                text = text + emoji
            else:
                text = emoji + text

        return text

    async def generate_reply(self, chat_id: int, trigger_message: str, sender_name: str) -> str:
        """生成AI回复"""
        if not self.client:
            return None

        ai_config = self.config.get('ai_chat', {})
        personality = ai_config.get('personality', '')
        model = ai_config.get('model', 'deepseek-chat')

        context_messages = self.chat_contexts[chat_id][-15:]

        context_str = ""
        for msg in context_messages:
            context_str += f"[{msg['time']}] {msg['role']}: {msg['content']}\n"

        system_prompt = f"""{personality}

你现在在一个群聊中，以下是最近的聊天记录：
{context_str}

现在 {sender_name} 说了: "{trigger_message}"

请你根据上下文，像一个真人一样回复这条消息。要求：
1. 回复要自然、口语化，像真人聊天
2. 回复要简短，通常1-2句话，最多不超过50字
3. 可以适当使用网络用语
4. 有时候可以不直接回答问题，而是聊相关的话题
5. 偶尔可以调侃一下，但不要过分
6. 不要暴露自己是AI
7. 如果话题无聊或者你觉得没必要回复，可以回复 [SKIP] 表示跳过

只需要输出回复内容，不要加任何前缀或解释。"""

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": trigger_message}
                ],
                max_tokens=100,
                temperature=0.9,
            )

            reply = response.choices[0].message.content.strip()

            if '[SKIP]' in reply or reply == '':
                return None

            reply = reply.replace('[SKIP]', '').strip()
            reply = self._add_personality(reply)

            return reply

        except Exception as e:
            print(f"❌ AI 生成回复失败: {e}")
            return None

    async def simulate_typing(self, text: str, is_direct_reply: bool = False) -> float:
        """模拟打字延迟"""
        ai_config = self.config.get('ai_chat', {})
        if not ai_config.get('typing_simulation', True):
            return 0

        # 如果是被@或回复，使用更长的延迟模拟思考和打字
        if is_direct_reply:
            delay_min = ai_config.get('reply_delay_min', 2)
            delay_max = ai_config.get('reply_delay_max', 5)
            return random.uniform(delay_min, delay_max)
        
        base_delay = len(text) * random.uniform(0.1, 0.2)
        delay = base_delay + random.uniform(0.5, 2.0)
        return min(delay, 5.0)

    def trigger_alert(self, chat_id: int, keyword: str, message_text: str, sender_name: str):
        """触发报警"""
        self.alert_triggered[chat_id] = True
        self.alert_messages[chat_id].append({
            'keyword': keyword,
            'message': message_text,
            'sender': sender_name,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })

    def clear_alert(self, chat_id: int):
        """清除报警状态"""
        self.alert_triggered[chat_id] = False
        self.alert_messages[chat_id] = []

    def add_manual_message(self, chat_id: int, message: str, reply_to: int = None):
        """添加人工消息到队列"""
        self.manual_message_queue[chat_id].append({
            'message': message,
            'reply_to': reply_to
        })

    def get_manual_message(self, chat_id: int):
        """获取并移除队列中的第一条人工消息"""
        if self.manual_message_queue[chat_id]:
            return self.manual_message_queue[chat_id].pop(0)
        return None


# 创建 AI 聊天管理器
ai_manager = AIChatManager(config)


def update_config_file(new_bot_mappings):
    """更新配置文件"""
    global bot_mappings, forwarding_map, config
    bot_mappings = new_bot_mappings
    config['bot_mappings'] = new_bot_mappings
    save_config(config)
    print("✅ config.json 已更新！")
    asyncio.create_task(rebuild_forwarding_map())


async def rebuild_forwarding_map():
    """重新构建转发映射"""
    global forwarding_map
    forwarding_map = {}

    for mapping in bot_mappings:
        source_chat_id_from_config = mapping['source_chat']
        target_bot_username_or_id = mapping['target_bot']
        try:
            try:
                source_chat_id_processed = int(source_chat_id_from_config)
            except ValueError:
                source_chat_id_processed = source_chat_id_from_config

            source_entity = await client.get_entity(source_chat_id_processed)
            target_bot_entity = await client.get_entity(str(target_bot_username_or_id))

            peer_id_for_map = await client.get_peer_id(source_entity)
            forwarding_map[peer_id_for_map] = target_bot_entity
            print(f"✅ 映射成功: {source_chat_id_from_config} -> {target_bot_username_or_id}")
        except Exception as e:
            print(f"❌ 映射失败: {source_chat_id_from_config}, 错误: {e}")


@client.on(NewMessage())
async def handler(event):
    """消息处理器 - 转发消息 + AI炒群"""
    global bot_running

    if not bot_running:
        return

    # 转发逻辑
    if event.chat_id in forwarding_map:
        target_bot_entity = forwarding_map[event.chat_id]

        if event.message.grouped_id:
            async with media_group_lock:
                if event.message.grouped_id not in media_group_cache:
                    media_group_cache[event.message.grouped_id] = {
                        'messages': [],
                        'task': None,
                        'target_bot': target_bot_entity
                    }
                media_group_cache[event.message.grouped_id]['messages'].append(event.message.id)

                if media_group_cache[event.message.grouped_id]['task']:
                    media_group_cache[event.message.grouped_id]['task'].cancel()

                media_group_cache[event.message.grouped_id]['task'] = asyncio.create_task(
                    process_media_group(event.message.grouped_id, event.chat_id)
                )
        else:
            try:
                await client.forward_messages(target_bot_entity, event.message.id, from_peer=event.chat_id)
            except Exception as e:
                print(f"❌ 转发失败: {e}")

    # AI 炒群逻辑
    await handle_ai_chat(event)


async def handle_ai_chat(event):
    """处理 AI 炒群"""
    global config
    
    me = await client.get_me()
    
    # 先追踪发言者（无论是否启用AI）
    if event.sender_id:
        ai_manager.track_sender(event.chat_id, event.sender_id)
    
    # 检查是否是其他AI的消息，避免互相扯皮
    if ai_manager.is_other_ai(event.sender_id):
        print(f"🚫 跳过其他AI [{event.sender_id}] 的消息")
        return
    
    if not ai_manager.is_enabled(event.chat_id):
        return

    if event.sender_id == me.id:
        return

    message_text = event.message.text or event.message.caption or ""
    if not message_text:
        return

    try:
        sender = await event.get_sender()
        sender_name = sender.first_name if sender else "某人"
        if hasattr(sender, 'last_name') and sender.last_name:
            sender_name += f" {sender.last_name}"
    except:
        sender_name = "某人"

    # 检查报警关键词
    has_alert, keyword = ai_manager.check_alert_keywords(message_text)
    if has_alert:
        ai_manager.trigger_alert(event.chat_id, keyword, message_text, sender_name)
        
        # 通知管理员
        try:
            alert_msg = f"""
🚨 *报警触发!*

📍 群组ID: `{event.chat_id}`
🔑 触发关键词: `{keyword}`
👤 发送者: {sender_name}
💬 消息内容: {message_text[:200]}

⚠️ AI炒群已自动暂停，使用 `/ai resume {event.chat_id}` 恢复
或使用 `/manual on` 切换到人工模式
"""
            await client.send_message(master_account_id, alert_msg, parse_mode='Markdown')
            print(f"🚨 报警触发: 群组 {event.chat_id}, 关键词: {keyword}")
        except Exception as e:
            print(f"❌ 发送报警通知失败: {e}")
        return

    # 检查该群是否已触发报警
    if ai_manager.alert_triggered.get(event.chat_id, False):
        return

    ai_manager.add_context(event.chat_id, sender_name, message_text)

    is_mentioned = False
    is_reply_to_me = False
    is_direct_reply = False

    my_username = me.username or ""

    if my_username and f"@{my_username}" in message_text:
        is_mentioned = True
        is_direct_reply = True

    if event.message.reply_to_msg_id:
        try:
            replied_msg = await event.message.get_reply_message()
            if replied_msg and replied_msg.sender_id == me.id:
                is_reply_to_me = True
                is_direct_reply = True
        except:
            pass

    should_reply = False

    if is_mentioned or is_reply_to_me:
        should_reply = random.randint(1, 100) <= 90
    else:
        # 检查活跃度
        if ai_manager.should_skip_due_to_low_activity(event.chat_id):
            print(f"⏸️ 群组 {event.chat_id} 活跃用户过少，跳过回复")
            return
        should_reply = ai_manager.should_reply(event.chat_id, message_text)

    if not should_reply:
        return

    reply = await ai_manager.generate_reply(event.chat_id, message_text, sender_name)

    if not reply:
        return

    # 根据是否是直接回复决定延迟时间
    typing_delay = await ai_manager.simulate_typing(reply, is_direct_reply)
    if typing_delay > 0:
        try:
            async with client.action(event.chat_id, 'typing'):
                await asyncio.sleep(typing_delay)
        except:
            await asyncio.sleep(typing_delay)

    try:
        if is_reply_to_me or (is_mentioned and random.random() < 0.7):
            await event.reply(reply)
        else:
            await client.send_message(event.chat_id, reply)

        ai_manager.last_reply_time[event.chat_id] = datetime.now()
        ai_manager.add_context(event.chat_id, "我", reply, is_self=True)

        print(f"🤖 AI回复 [{event.chat_id}]: {reply}")
    except Exception as e:
        print(f"❌ 发送AI回复失败: {e}")


async def process_media_group(grouped_id, from_peer):
    """处理媒体组"""
    await asyncio.sleep(1.5)
    async with media_group_lock:
        if grouped_id in media_group_cache:
            group_info = media_group_cache[grouped_id]
            message_ids = group_info['messages']
            target_bot = group_info['target_bot']

            try:
                await client.forward_messages(target_bot, message_ids, from_peer=from_peer)
            except Exception as e:
                print(f"❌ 媒体组转发失败: {e}")
            finally:
                del media_group_cache[grouped_id]


async def join_chat(chat_entity):
    """加入群组/频道"""
    try:
        await client(JoinChannelRequest(chat_entity))
        print(f"✅ 成功加入: {chat_entity.title}")
        return True
    except Exception as e:
        print(f"❌ 加入失败: {e}")
        return False


async def leave_chat(chat_entity):
    """退出群组/频道"""
    try:
        await client(LeaveChannelRequest(chat_entity))
        print(f"✅ 成功退出: {chat_entity.title}")
        return True
    except Exception as e:
        print(f"❌ 退出失败: {e}")
        return False


async def start_bot_interaction(bot_username):
    """向机器人发送 /start 开始交互"""
    try:
        bot_entity = await client.get_entity(bot_username)
        await client.send_message(bot_entity, '/start')
        print(f"✅ 已向 {bot_username} 发送 /start")
        return True
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False


def get_help_text():
    """获取帮助文本"""
    return """
📖 *命令帮助*

🔧 *基础命令:*
• `/help` - 显示此帮助信息
• `/status` - 查看机器人状态
• `/pause` - 暂停所有功能
• `/resume` - 恢复所有功能

🤖 *机器人交互:*
• `/start <@机器人>` - 向机器人发送 /start
• `/send <@机器人> <消息>` - 向机器人发送消息

📢 *频道管理:*
• `/join <链接或ID>` - 加入群组/频道
• `/leave <链接或ID>` - 退出群组/频道

🔗 *转发监听:*
• `/add_listen <源聊天> <@目标>` - 添加监听
• `/remove_listen <源聊天>` - 移除监听
• `/list_listen` - 列出所有监听

🤖 *AI炒群:*
• `/ai on` - 全局开启AI炒群
• `/ai off` - 全局关闭AI炒群
• `/ai add <群组ID>` - 添加炒群群组
• `/ai remove <群组ID>` - 移除炒群群组
• `/ai list` - 列出炒群群组
• `/ai prob <概率>` - 设置回复概率(0-100)
• `/ai cooldown <秒>` - 设置冷却时间
• `/ai personality <人设>` - 设置AI人设
• `/ai status` - 查看AI炒群状态
• `/ai test <消息>` - 测试AI回复
• `/ai apikey <key>` - 设置API Key
• `/ai baseurl <url>` - 设置API地址
• `/ai model <model>` - 设置模型

🚨 *报警与人工干预:*
• `/ai alert on/off` - 开启/关闭报警功能
• `/ai alert add <关键词>` - 添加报警关键词
• `/ai alert remove <关键词>` - 移除报警关键词
• `/ai alert list` - 列出报警关键词
• `/ai resume <群组ID>` - 恢复指定群的AI
• `/manual on` - 切换到人工干预模式
• `/manual off` - 关闭人工干预模式
• `/manual send <群组ID> <消息>` - 人工发送消息
• `/manual reply <群组ID> <消息ID> <消息>` - 回复指定消息

🤖 *多AI防扯皮:*
• `/ai addbot <用户ID>` - 添加其他AI的ID
• `/ai removebot <用户ID>` - 移除其他AI的ID
• `/ai listbot` - 列出所有AI ID

📊 *活跃度设置:*
• `/ai minusers <数量>` - 设置最少活跃用户数
• `/ai checktime <分钟>` - 设置活跃检查时间
• `/ai delay <最小秒> <最大秒>` - 设置回复延迟

👤 *账号管理:*
• `/profile name <名字>` - 修改名字
• `/profile bio <简介>` - 修改简介
• `/profile photo` - 修改头像(回复图片使用)

👥 *管理员设置:* (仅主账号可用)
• `/admin add <用户ID>` - 添加管理员
• `/admin remove <用户ID>` - 移除管理员
• `/admin list` - 列出所有管理员

📊 *其他:*
• `/myid` - 获取您的用户ID
• `/chatid` - 获取聊天ID
"""


async def handle_ai_command(event, args: str):
    """处理 AI 炒群命令"""
    global config

    parts = args.strip().split(' ', 1)
    sub_cmd = parts[0].lower() if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""

    ai_config = config.get('ai_chat', {})

    if sub_cmd == 'on':
        ai_config['enabled'] = True
        config['ai_chat'] = ai_config
        save_config(config)
        ai_manager.update_config(config)
        await event.reply("✅ AI炒群已全局开启")

    elif sub_cmd == 'off':
        ai_config['enabled'] = False
        config['ai_chat'] = ai_config
        save_config(config)
        await event.reply("✅ AI炒群已全局关闭")

    elif sub_cmd == 'add':
        if not sub_args:
            await event.reply("❌ 用法: `/ai add <群组ID>`", parse_mode='Markdown')
            return
        try:
            chat_id = int(sub_args)
            if chat_id not in ai_config.get('chats', []):
                if 'chats' not in ai_config:
                    ai_config['chats'] = []
                ai_config['chats'].append(chat_id)
                config['ai_chat'] = ai_config
                save_config(config)
                ai_manager.update_config(config)
                await event.reply(f"✅ 已添加炒群群组: `{chat_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该群组已在列表中")
        except ValueError:
            await event.reply("❌ 请输入有效的群组ID")

    elif sub_cmd == 'remove':
        if not sub_args:
            await event.reply("❌ 用法: `/ai remove <群组ID>`", parse_mode='Markdown')
            return
        try:
            chat_id = int(sub_args)
            if chat_id in ai_config.get('chats', []):
                ai_config['chats'].remove(chat_id)
                config['ai_chat'] = ai_config
                save_config(config)
                ai_manager.update_config(config)
                await event.reply(f"✅ 已移除炒群群组: `{chat_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该群组不在列表中")
        except ValueError:
            await event.reply("❌ 请输入有效的群组ID")

    elif sub_cmd == 'list':
        chats = ai_config.get('chats', [])
        if chats:
            text = "🤖 *AI炒群群组列表:*\n\n"
            for i, cid in enumerate(chats, 1):
                alert_status = "🚨" if ai_manager.alert_triggered.get(cid, False) else "✅"
                active_count = ai_manager.get_active_users_count(cid)
                text += f"{i}. `{cid}` {alert_status} (活跃: {active_count}人)\n"
            await event.reply(text, parse_mode='Markdown')
        else:
            await event.reply("📋 暂无炒群群组")

    elif sub_cmd == 'prob':
        if not sub_args:
            current = ai_config.get('reply_probability', 30)
            await event.reply(f"当前回复概率: {current}%\n用法: `/ai prob <0-100>`", parse_mode='Markdown')
            return
        try:
            prob = int(sub_args)
            if 0 <= prob <= 100:
                ai_config['reply_probability'] = prob
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 回复概率已设置为: {prob}%")
            else:
                await event.reply("❌ 概率必须在 0-100 之间")
        except ValueError:
            await event.reply("❌ 请输入有效的数字")

    elif sub_cmd == 'cooldown':
        if not sub_args:
            current = ai_config.get('cooldown_seconds', 30)
            await event.reply(f"当前冷却时间: {current}秒\n用法: `/ai cooldown <秒>`", parse_mode='Markdown')
            return
        try:
            seconds = int(sub_args)
            if seconds >= 0:
                ai_config['cooldown_seconds'] = seconds
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 冷却时间已设置为: {seconds}秒")
            else:
                await event.reply("❌ 冷却时间不能为负数")
        except ValueError:
            await event.reply("❌ 请输入有效的数字")

    elif sub_cmd == 'personality':
        if not sub_args:
            current = ai_config.get('personality', '未设置')
            await event.reply(f"当前人设:\n{current[:500]}...\n\n用法: `/ai personality <人设描述>`",
                              parse_mode='Markdown')
            return
        ai_config['personality'] = sub_args
        config['ai_chat'] = ai_config
        save_config(config)
        await event.reply("✅ AI人设已更新")

    elif sub_cmd == 'status':
        enabled = "✅ 开启" if ai_config.get('enabled', False) else "❌ 关闭"
        api_ok = "✅ 已配置" if ai_manager.client else "❌ 未配置"
        chats = ai_config.get('chats', [])
        prob = ai_config.get('reply_probability', 30)
        cooldown = ai_config.get('cooldown_seconds', 30)
        min_len = ai_config.get('min_message_length', 3)
        personality = ai_config.get('personality', '未设置')[:100]
        
        # 新增状态
        alert_enabled = "✅ 开启" if ai_config.get('alert_enabled', True) else "❌ 关闭"
        manual_mode = "✅ 开启" if ai_config.get('manual_mode', False) else "❌ 关闭"
        min_users = ai_config.get('min_active_users', 3)
        check_time = ai_config.get('active_check_minutes', 10)
        delay_min = ai_config.get('reply_delay_min', 2)
        delay_max = ai_config.get('reply_delay_max', 5)
        other_ais = len(ai_config.get('other_ai_ids', []))
        alert_keywords = ai_config.get('alert_keywords', [])

        status_text = f"""
🤖 *AI炒群状态*

• 全局开关: {enabled}
• API状态: {api_ok}
• 炒群群组数: {len(chats)}
• 回复概率: {prob}%
• 冷却时间: {cooldown}秒
• 最小触发长度: {min_len}字

🚨 *报警设置:*
• 报警功能: {alert_enabled}
• 人工模式: {manual_mode}
• 报警关键词: {', '.join(alert_keywords[:5])}{'...' if len(alert_keywords) > 5 else ''}

📊 *活跃度设置:*
• 最少活跃用户: {min_users}人
• 检查时间: {check_time}分钟
• 回复延迟: {delay_min}-{delay_max}秒

🤖 *防扯皮:*
• 其他AI数量: {other_ais}

📝 *当前人设:*
{personality}... 
"""
        await event.reply(status_text, parse_mode='Markdown')

    elif sub_cmd == 'test':
        if not sub_args:
            await event.reply("❌ 用法: `/ai test <测试消息>`", parse_mode='Markdown')
            return

        if not ai_manager.client:
            await event.reply("❌ AI客户端未初始化，请检查API配置")
            return

        await event.reply("⏳ 正在生成回复...")

        test_chat_id = -1
        ai_manager.add_context(test_chat_id, "测试用户", "大家好啊")
        ai_manager.add_context(test_chat_id, "另一个人", "你好呀")

        reply = await ai_manager.generate_reply(test_chat_id, sub_args, "测试用户")

        if reply:
            await event.reply(f"🤖 AI回复:\n{reply}")
        else:
            await event.reply("❌ AI选择不回复或生成失败")

        ai_manager.chat_contexts[test_chat_id] = []

    elif sub_cmd == 'apikey':
        if not sub_args:
            has_key = "✅ 已配置" if ai_config.get('api_key') else "❌ 未配置"
            await event.reply(f"API Key状态: {has_key}\n用法: `/ai apikey <your_api_key>`", parse_mode='Markdown')
            return
        ai_config['api_key'] = sub_args
        config['ai_chat'] = ai_config
        save_config(config)
        ai_manager.update_config(config)
        await event.reply("✅ API Key 已更新")

    elif sub_cmd == 'baseurl':
        if not sub_args:
            current = ai_config.get('base_url', 'https://api.deepseek.com')
            await event.reply(f"当前API地址: {current}\n用法: `/ai baseurl <url>`", parse_mode='Markdown')
            return
        ai_config['base_url'] = sub_args
        config['ai_chat'] = ai_config
        save_config(config)
        ai_manager.update_config(config)
        await event.reply(f"✅ API地址已设置为: {sub_args}")

    elif sub_cmd == 'model':
        if not sub_args:
            current = ai_config.get('model', 'deepseek-chat')
            await event.reply(f"当前模型: {current}\n用法: `/ai model <model_name>`", parse_mode='Markdown')
            return
        ai_config['model'] = sub_args
        config['ai_chat'] = ai_config
        save_config(config)
        await event.reply(f"✅ 模型已设置为: {sub_args}")

    # ========== 报警功能 ==========
    elif sub_cmd == 'alert':
        alert_parts = sub_args.strip().split(' ', 1)
        alert_cmd = alert_parts[0].lower() if alert_parts else ""
        alert_args = alert_parts[1] if len(alert_parts) > 1 else ""
        
        if alert_cmd == 'on':
            ai_config['alert_enabled'] = True
            config['ai_chat'] = ai_config
            save_config(config)
            await event.reply("✅ 报警功能已开启")
        
        elif alert_cmd == 'off':
            ai_config['alert_enabled'] = False
            config['ai_chat'] = ai_config
            save_config(config)
            await event.reply("✅ 报警功能已关闭")
        
        elif alert_cmd == 'add':
            if not alert_args:
                await event.reply("❌ 用法: `/ai alert add <关键词>`", parse_mode='Markdown')
                return
            keywords = ai_config.get('alert_keywords', [])
            if alert_args not in keywords:
                keywords.append(alert_args)
                ai_config['alert_keywords'] = keywords
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 已添加报警关键词: `{alert_args}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该关键词已存在")
        
        elif alert_cmd == 'remove':
            if not alert_args:
                await event.reply("❌ 用法: `/ai alert remove <关键词>`", parse_mode='Markdown')
                return
            keywords = ai_config.get('alert_keywords', [])
            if alert_args in keywords:
                keywords.remove(alert_args)
                ai_config['alert_keywords'] = keywords
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 已移除报警关键词: `{alert_args}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该关键词不存在")
        
        elif alert_cmd == 'list':
            keywords = ai_config.get('alert_keywords', [])
            if keywords:
                text = "🚨 *报警关键词列表:*\n\n"
                for i, kw in enumerate(keywords, 1):
                    text += f"{i}. `{kw}`\n"
                await event.reply(text, parse_mode='Markdown')
            else:
                await event.reply("📋 暂无报警关键词")
        
        else:
            await event.reply("❌ 用法: `/ai alert on/off/add/remove/list`", parse_mode='Markdown')

    elif sub_cmd == 'resume':
        if not sub_args:
            await event.reply("❌ 用法: `/ai resume <群组ID>`", parse_mode='Markdown')
            return
        try:
            chat_id = int(sub_args)
            if ai_manager.alert_triggered.get(chat_id, False):
                ai_manager.clear_alert(chat_id)
                await event.reply(f"✅ 已恢复群组 `{chat_id}` 的AI炒群", parse_mode='Markdown')
            else:
                await event.reply("ℹ️ 该群组未触发报警")
        except ValueError:
            await event.reply("❌ 请输入有效的群组ID")

    # ========== 多AI防扯皮 ==========
    elif sub_cmd == 'addbot':
        if not sub_args:
            await event.reply("❌ 用法: `/ai addbot <用户ID>`", parse_mode='Markdown')
            return
        try:
            bot_id = int(sub_args)
            other_ais = ai_config.get('other_ai_ids', [])
            if bot_id not in other_ais:
                other_ais.append(bot_id)
                ai_config['other_ai_ids'] = other_ais
                config['ai_chat'] = ai_config
                save_config(config)
                ai_manager.update_config(config)
                await event.reply(f"✅ 已添加其他AI: `{bot_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该ID已在列表中")
        except ValueError:
            await event.reply("❌ 请输入有效的用户ID")

    elif sub_cmd == 'removebot':
        if not sub_args:
            await event.reply("❌ 用法: `/ai removebot <用户ID>`", parse_mode='Markdown')
            return
        try:
            bot_id = int(sub_args)
            other_ais = ai_config.get('other_ai_ids', [])
            if bot_id in other_ais:
                other_ais.remove(bot_id)
                ai_config['other_ai_ids'] = other_ais
                config['ai_chat'] = ai_config
                save_config(config)
                ai_manager.update_config(config)
                await event.reply(f"✅ 已移除其他AI: `{bot_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该ID不在列表中")
        except ValueError:
            await event.reply("❌ 请输入有效的用户ID")

    elif sub_cmd == 'listbot':
        other_ais = ai_config.get('other_ai_ids', [])
        if other_ais:
            text = "🤖 *其他AI ID列表:*\n\n"
            for i, aid in enumerate(other_ais, 1):
                text += f"{i}. `{aid}`\n"
            await event.reply(text, parse_mode='Markdown')
        else:
            await event.reply("📋 暂无其他AI ID")

    # ========== 活跃度设置 ==========
    elif sub_cmd == 'minusers':
        if not sub_args:
            current = ai_config.get('min_active_users', 3)
            await event.reply(f"当前最少活跃用户数: {current}\n用法: `/ai minusers <数量>`", parse_mode='Markdown')
            return
        try:
            num = int(sub_args)
            if num >= 0:
                ai_config['min_active_users'] = num
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 最少活跃用户数已设置为: {num}")
            else:
                await event.reply("❌ 数量不能为负数")
        except ValueError:
            await event.reply("❌ 请输入有效的数字")

    elif sub_cmd == 'checktime':
        if not sub_args:
            current = ai_config.get('active_check_minutes', 10)
            await event.reply(f"当前活跃检查时间: {current}分钟\n用法: `/ai checktime <分钟>`", parse_mode='Markdown')
            return
        try:
            mins = int(sub_args)
            if mins > 0:
                ai_config['active_check_minutes'] = mins
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 活跃检查时间已设置为: {mins}分钟")
            else:
                await event.reply("❌ 时间必须大于0")
        except ValueError:
            await event.reply("❌ 请输入有效的数字")

    elif sub_cmd == 'delay':
        if not sub_args:
            delay_min = ai_config.get('reply_delay_min', 2)
            delay_max = ai_config.get('reply_delay_max', 5)
            await event.reply(f"当前回复延迟: {delay_min}-{delay_max}秒\n用法: `/ai delay <最小秒> <最大秒>`", parse_mode='Markdown')
            return
        try:
            delay_parts = sub_args.split()
            if len(delay_parts) != 2:
                await event.reply("❌ 用法: `/ai delay <最小秒> <最大秒>`", parse_mode='Markdown')
                return
            delay_min = float(delay_parts[0])
            delay_max = float(delay_parts[1])
            if delay_min >= 0 and delay_max >= delay_min:
                ai_config['reply_delay_min'] = delay_min
                ai_config['reply_delay_max'] = delay_max
                config['ai_chat'] = ai_config
                save_config(config)
                await event.reply(f"✅ 回复延迟已设置为: {delay_min}-{delay_max}秒")
            else:
                await event.reply("❌ 延迟时间无效")
        except ValueError:
            await event.reply("❌ 请输入有效的数字")

    else:
        await event.reply("❌ 未知命令，使用 `/help` 查看帮助", parse_mode='Markdown')


async def handle_manual_command(event, args: str):
    """处理人工干预命令"""
    global config
    
    parts = args.strip().split(' ', 2)
    sub_cmd = parts[0].lower() if parts else ""
    
    ai_config = config.get('ai_chat', {})
    
    if sub_cmd == 'on':
        ai_config['manual_mode'] = True
        config['ai_chat'] = ai_config
        save_config(config)
        ai_manager.update_config(config)
        await event.reply("✅ 已切换到人工干预模式，AI将暂停自动回复")
    
    elif sub_cmd == 'off':
        ai_config['manual_mode'] = False
        config['ai_chat'] = ai_config
        save_config(config)
        ai_manager.update_config(config)
        await event.reply("✅ 已关闭人工干预模式，AI恢复自动回复")
    
    elif sub_cmd == 'send':
        if len(parts) < 3:
            await event.reply("❌ 用法: `/manual send <群组ID> <消息>`", parse_mode='Markdown')
            return
        try:
            chat_id = int(parts[1])
            message = parts[2]
            
            # 模拟打字延迟
            delay = random.uniform(1, 3)
            try:
                async with client.action(chat_id, 'typing'):
                    await asyncio.sleep(delay)
            except:
                await asyncio.sleep(delay)
            
            await client.send_message(chat_id, message)
            await event.reply(f"✅ 已向群组 `{chat_id}` 发送消息", parse_mode='Markdown')
        except ValueError:
            await event.reply("❌ 请输入有效的群组ID")
        except Exception as e:
            await event.reply(f"❌ 发送失败: {e}")
    
    elif sub_cmd == 'reply':
        if len(parts) < 3:
            await event.reply("❌ 用法: `/manual reply <群组ID> <消息ID> <消息>`\n或: `/manual reply <群组ID> <消息>` (回复最新消息)", parse_mode='Markdown')
            return
        try:
            chat_id = int(parts[1])
            remaining = parts[2].split(' ', 1)
            
            # 检查是否指定了消息ID
            try:
                reply_to_id = int(remaining[0])
                message = remaining[1] if len(remaining) > 1 else ""
            except ValueError:
                # 没有指定消息ID，回复最新消息
                reply_to_id = None
                message = parts[2]
            
            if not message:
                await event.reply("❌ 请输入要发送的消息")
                return
            
            # 模拟打字延迟
            delay = random.uniform(2, 4)
            try:
                async with client.action(chat_id, 'typing'):
                    await asyncio.sleep(delay)
            except:
                await asyncio.sleep(delay)
            
            await client.send_message(chat_id, message, reply_to=reply_to_id)
            await event.reply(f"✅ 已向群组 `{chat_id}` 发送回复", parse_mode='Markdown')
        except ValueError:
            await event.reply("❌ 请输入有效的群组ID")
        except Exception as e:
            await event.reply(f"❌ 发送失败: {e}")
    
    elif sub_cmd == 'status':
        manual_mode = "✅ 开启" if ai_config.get('manual_mode', False) else "❌ 关闭"
        
        # 列出已触发报警的群组
        alert_chats = [cid for cid, triggered in ai_manager.alert_triggered.items() if triggered]
        
        status_text = f"""
🖐️ *人工干预状态*

• 人工模式: {manual_mode}
• 报警群组数: {len(alert_chats)}
"""
        if alert_chats:
            status_text += "\n🚨 *已报警群组:*\n"
            for cid in alert_chats:
                alerts = ai_manager.alert_messages.get(cid, [])
                if alerts:
                    last_alert = alerts[-1]
                    status_text += f"• `{cid}` - {last_alert['keyword']} ({last_alert['time']})\n"
        
        await event.reply(status_text, parse_mode='Markdown')
    
    else:
        await event.reply("❌ 用法: `/manual on/off/send/reply/status`", parse_mode='Markdown')


async def handle_profile_command(event, args: str):
    """处理账号资料命令"""
    parts = args.strip().split(' ', 1)
    sub_cmd = parts[0].lower() if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""
    
    if sub_cmd == 'name':
        if not sub_args:
            me = await client.get_me()
            current = f"{me.first_name or ''} {me.last_name or ''}".strip()
            await event.reply(f"当前名字: {current}\n用法: `/profile name <名字>` 或 `/profile name <名字> <姓氏>`", parse_mode='Markdown')
            return
        
        try:
            name_parts = sub_args.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            await client(UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name
            ))
            await event.reply(f"✅ 名字已修改为: {first_name} {last_name}".strip())
        except Exception as e:
            await event.reply(f"❌ 修改失败: {e}")
    
    elif sub_cmd == 'bio':
        if not sub_args:
            try:
                full = await client(GetFullUserRequest('me'))
                current_bio = full.full_user.about or "未设置"
                await event.reply(f"当前简介: {current_bio}\n用法: `/profile bio <简介>`", parse_mode='Markdown')
            except:
                await event.reply("用法: `/profile bio <简介>`", parse_mode='Markdown')
            return
        
        try:
            await client(UpdateProfileRequest(about=sub_args))
            await event.reply(f"✅ 简介已修改为: {sub_args}")
        except Exception as e:
            await event.reply(f"❌ 修改失败: {e}")
    
    elif sub_cmd == 'photo':
        # 检查是否回复了图片消息
        if not event.reply_to_msg_id:
            await event.reply("❌ 请回复一张图片使用此命令")
            return
        
        try:
            replied = await event.get_reply_message()
            if not replied.photo:
                await event.reply("❌ 回复的消息不是图片")
                return
            
            # 下载图片
            photo_path = await replied.download_media()
            if not photo_path:
                await event.reply("❌ 下载图片失败")
                return
            
            # 上传为头像
            await client(UploadProfilePhotoRequest(
                file=await client.upload_file(photo_path)
            ))
            
            # 删除临时文件
            try:
                os.remove(photo_path)
            except:
                pass
            
            await event.reply("✅ 头像已更新")
        except Exception as e:
            await event.reply(f"❌ 修改失败: {e}")
    
    else:
        await event.reply("❌ 用法: `/profile name/bio/photo`", parse_mode='Markdown')


async def handle_admin_command(event, args: str):
    """处理管理员设置命令（仅主账号可用）"""
    global config, admin_ids
    
    # 只有主账号可以管理管理员
    if event.sender_id != master_account_id:
        await event.reply("❌ 只有主账号可以管理管理员")
        return
    
    parts = args.strip().split(' ', 1)
    sub_cmd = parts[0].lower() if parts else ""
    sub_args = parts[1] if len(parts) > 1 else ""
    
    if sub_cmd == 'add':
        if not sub_args:
            await event.reply("❌ 用法: `/admin add <用户ID>`", parse_mode='Markdown')
            return
        try:
            user_id = int(sub_args)
            if user_id == master_account_id:
                await event.reply("❌ 主账号无需添加")
                return
            if user_id not in admin_ids:
                admin_ids.append(user_id)
                config['admin_ids'] = admin_ids
                save_config(config)
                await event.reply(f"✅ 已添加管理员: `{user_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该用户已是管理员")
        except ValueError:
            await event.reply("❌ 请输入有效的用户ID")
    
    elif sub_cmd == 'remove':
        if not sub_args:
            await event.reply("❌ 用法: `/admin remove <用户ID>`", parse_mode='Markdown')
            return
        try:
            user_id = int(sub_args)
            if user_id in admin_ids:
                admin_ids.remove(user_id)
                config['admin_ids'] = admin_ids
                save_config(config)
                await event.reply(f"✅ 已移除管理员: `{user_id}`", parse_mode='Markdown')
            else:
                await event.reply("❌ 该用户不是管理员")
        except ValueError:
            await event.reply("❌ 请输入有效的用户ID")
    
    elif sub_cmd == 'list':
        text = "👥 *管理员列表:*\n\n"
        text += f"👑 主账号: `{master_account_id}`\n\n"
        if admin_ids:
            text += "📋 *其他管理员:*\n"
            for i, aid in enumerate(admin_ids, 1):
                text += f"{i}. `{aid}`\n"
        else:
            text += "暂无其他管理员"
        await event.reply(text, parse_mode='Markdown')
    
    else:
        await event.reply("❌ 用法: `/admin add/remove/list`", parse_mode='Markdown')


async def main():
    """主函数"""
    global bot_running, config

    print(BANNER)

    try:
        await client.start(password=lambda: input('请输入两步验证密码 (如果没有请直接回车): '))
    except Exception as e:
        print(f"❌ 客户端启动失败: {e}")
        return

    print("✅ 客户端已启动！")
    print(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    me = await client.get_me()
    ai_manager.my_user_id = me.id
    print(f"👤 当前账号: {me.first_name} (@{me.username}) [ID: {me.id}]")

    await rebuild_forwarding_map()
    print(f"📋 已加载 {len(forwarding_map)} 个转发映射")

    ai_status = "开启" if config.get('ai_chat', {}).get('enabled', False) else "关闭"
    ai_chats = len(config.get('ai_chat', {}).get('chats', []))
    print(f"🤖 AI炒群: {ai_status}，已配置 {ai_chats} 个群组")
    print("=" * 60)
    print("💡 机器人正在运行，等待消息...")
    print("=" * 60)

    # 处理来自管理员的命令
    @client.on(NewMessage(func=lambda e: e.is_private and is_admin(e.sender_id)))
    async def command_handler(event):
        global bot_running, config, admin_ids

        text = event.message.text or ""
        command = text.split(' ', 1)
        cmd = command[0].lower()
        args = command[1] if len(command) > 1 else ""

        if cmd == '/help':
            await event.reply(get_help_text(), parse_mode='Markdown')

        elif cmd == '/start':
            if not args:
                await event.reply("❌ 用法: `/start <@机器人用户名>`", parse_mode='Markdown')
                return

            bot_username = args.strip()
            if not bot_username.startswith('@'):
                bot_username = '@' + bot_username

            await event.reply(f"⏳ 正在向 {bot_username} 发送 /start...")
            success = await start_bot_interaction(bot_username)
            if success:
                await event.reply(f"✅ 已成功向 {bot_username} 发送 /start")
            else:
                await event.reply("❌ 发送失败")

        elif cmd == '/send':
            parts = args.split(' ', 1)
            if len(parts) < 2:
                await event.reply("❌ 用法: `/send <@机器人> <消息>`", parse_mode='Markdown')
                return

            bot_username = parts[0].strip()
            message_text = parts[1].strip()

            if not bot_username.startswith('@'):
                bot_username = '@' + bot_username

            try:
                bot_entity = await client.get_entity(bot_username)
                await client.send_message(bot_entity, message_text)
                await event.reply(f"✅ 已向 {bot_username} 发送消息")
            except Exception as e:
                await event.reply(f"❌ 发送失败: {e}")

        elif cmd == '/pause':
            if not bot_running:
                await event.reply("⏸️ 已经处于暂停状态")
            else:
                bot_running = False
                await event.reply("⏸️ 已暂停所有功能")

        elif cmd == '/resume':
            if bot_running:
                await event.reply("▶️ 已经在运行中")
            else:
                bot_running = True
                await event.reply("▶️ 已恢复运行")

        elif cmd == '/status':
            ai_config = config.get('ai_chat', {})
            ai_enabled = "✅ 开启" if ai_config.get('enabled', False) else "❌ 关闭"
            ai_chats_count = len(ai_config.get('chats', []))
            ai_prob = ai_config.get('reply_probability', 30)
            ai_cooldown = ai_config.get('cooldown_seconds', 30)

            status_text = f"""
📊 *机器人状态*

🔄 运行状态: {'✅ 运行中' if bot_running else '⏸️ 已暂停'}
📋 转发映射数: {len(forwarding_map)}
⏰ 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🤖 *AI炒群状态:*
• 全局开关: {ai_enabled}
• 炒群群组数: {ai_chats_count}
• 回复概率: {ai_prob}%
• 冷却时间: {ai_cooldown}秒
• API配置: {'✅' if ai_manager.client else '❌'}
"""
            await event.reply(status_text, parse_mode='Markdown')

        elif cmd == '/myid':
            await event.reply(f"👤 您的用户ID: `{event.sender_id}`", parse_mode='Markdown')

        elif cmd == '/chatid':
            if event.reply_to_msg_id:
                replied_msg = await event.get_reply_message()
                if replied_msg and replied_msg.forward:
                    fwd = replied_msg.forward
                    if fwd.chat_id:
                        await event.reply(f"💬 转发来源ID: `{fwd.chat_id}`", parse_mode='Markdown')
                    elif fwd.sender_id:
                        await event.reply(f"💬 转发来源用户ID: `{fwd.sender_id}`", parse_mode='Markdown')
                else:
                    await event.reply("❌ 请回复一条转发的消息")
            else:
                await event.reply(f"💬 当前聊天ID: `{event.chat_id}`", parse_mode='Markdown')

        elif cmd == '/join':
            if not args:
                await event.reply("❌ 用法: `/join <链接或ID>`", parse_mode='Markdown')
                return
            try:
                chat_entity = await client.get_entity(args)
                success = await join_chat(chat_entity)
                if success:
                    await event.reply(f"✅ 已加入: {chat_entity.title}")
                else:
                    await event.reply("❌ 加入失败")
            except Exception as e:
                await event.reply(f"❌ 错误: {e}")

        elif cmd == '/leave':
            if not args:
                await event.reply("❌ 用法: `/leave <链接或ID>`", parse_mode='Markdown')
                return
            try:
                chat_entity = await client.get_entity(args)
                success = await leave_chat(chat_entity)
                if success:
                    await event.reply(f"✅ 已退出: {chat_entity.title}")
                else:
                    await event.reply("❌ 退出失败")
            except Exception as e:
                await event.reply(f"❌ 错误: {e}")

        elif cmd == '/add_listen':
            parts = args.split(' ', 1)
            if len(parts) != 2:
                await event.reply("❌ 用法: `/add_listen <源聊天> <@目标>`", parse_mode='Markdown')
                return

            source_chat_arg = parts[0]
            target_bot = parts[1].strip()

            if not target_bot.startswith('@'):
                await event.reply("❌ 目标必须以 '@' 开头")
                return

            try:
                await client.get_entity(target_bot)
                existing = next((m for m in bot_mappings if str(m['source_chat']) == str(source_chat_arg)), None)

                if existing:
                    new_mappings = [m for m in bot_mappings if str(m['source_chat']) != str(source_chat_arg)]
                    new_mappings.append({'source_chat': source_chat_arg, 'target_bot': target_bot})
                    update_config_file(new_mappings)
                    await event.reply("✅ 已更新监听")
                else:
                    new_mappings = bot_mappings + [{'source_chat': source_chat_arg, 'target_bot': target_bot}]
                    update_config_file(new_mappings)
                    await event.reply("✅ 已添加监听")
            except Exception as e:
                await event.reply(f"❌ 失败: {e}")

        elif cmd == '/remove_listen':
            if not args:
                await event.reply("❌ 用法: `/remove_listen <源聊天>`", parse_mode='Markdown')
                return

            new_mappings = [m for m in bot_mappings if str(m['source_chat']) != str(args)]
            if len(new_mappings) < len(bot_mappings):
                update_config_file(new_mappings)
                await event.reply("✅ 已移除监听")
            else:
                await event.reply("❌ 未找到该监听")

        elif cmd == '/list_listen':
            if bot_mappings:
                text = "📋 *监听列表:*\n\n"
                for i, m in enumerate(bot_mappings, 1):
                    text += f"{i}. `{m['source_chat']}` → `{m['target_bot']}`\n"
                await event.reply(text, parse_mode='Markdown')
            else:
                await event.reply("📋 暂无监听配置")

        elif cmd == '/ai':
            await handle_ai_command(event, args)

        elif cmd == '/manual':
            await handle_manual_command(event, args)

        elif cmd == '/profile':
            await handle_profile_command(event, args)

        elif cmd == '/admin':
            await handle_admin_command(event, args)

    # 保持运行
    print("🚀 开始监听消息...")
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
