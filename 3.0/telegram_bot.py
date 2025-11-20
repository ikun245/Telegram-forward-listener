# telegram_bot.py
from telethon.sync import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.events import NewMessage
import asyncio
import json

# 用于处理媒体组的缓存和锁
media_group_cache = {}
media_group_lock = asyncio.Lock()

# 从 config.json 读取配置
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

api_id = config['api_id']
api_hash = config['api_hash']
master_account_id = config['master_account_id']
bot_mappings = config['bot_mappings']
proxy_config = config.get('proxy', None)

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
        print(f"不支持的代理类型: {proxy_type}")
        proxy = None
else:
    proxy = None

client = TelegramClient('anon', api_id, api_hash, proxy=proxy)

# forwarding_map 将在 main 函数中初始化
forwarding_map = {}

def update_config_file(new_bot_mappings):
    global bot_mappings, forwarding_map
    bot_mappings = new_bot_mappings
    config['bot_mappings'] = new_bot_mappings
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    print("config.json 已更新！")
    print(f"更新后的 bot_mappings: {bot_mappings}")
    # 重新构建 forwarding_map
    asyncio.create_task(rebuild_forwarding_map())

async def rebuild_forwarding_map():
    global forwarding_map
    forwarding_map = {}

    for mapping in bot_mappings:
        source_chat_id_from_config = mapping['source_chat']
        target_bot_username_or_id = mapping['target_bot']
        try:
            # 尝试将 source_chat_id 转换为整数，如果失败则保持原样 (可能是用户名)
            try:
                source_chat_id_processed = int(source_chat_id_from_config)
            except ValueError:
                source_chat_id_processed = source_chat_id_from_config

            source_entity = await client.get_entity(source_chat_id_processed)
            # 确保目标机器人是用户名 (字符串形式)
            target_bot_entity = await client.get_entity(str(target_bot_username_or_id))
            
            # 使用 client.get_peer_id 来获取与 event.chat_id 匹配的 ID
            peer_id_for_map = await client.get_peer_id(source_entity)
            forwarding_map[peer_id_for_map] = target_bot_entity
            print(f"成功获取实体: 源聊天 {source_chat_id_from_config} (Peer ID: {peer_id_for_map}), 目标机器人 {target_bot_username_or_id} ({target_bot_entity.id})")
        except Exception as e:
            print(f"错误：获取实体失败，源聊天: {source_chat_id_from_config}, 目标机器人: {target_bot_username_or_id}, 错误: {e}")

@client.on(NewMessage())
async def handler(event):
    print(f"handler: 收到消息，chat_id: {event.chat_id}, 消息文本: {event.message.text}")
    if event.chat_id in forwarding_map:
        target_bot_entity = forwarding_map[event.chat_id]

        if event.message.grouped_id:
            # 这是一个媒体组的一部分
            async with media_group_lock:
                if event.message.grouped_id not in media_group_cache:
                    media_group_cache[event.message.grouped_id] = {
                        'messages': [],
                        'task': None,
                        'target_bot': target_bot_entity
                    }
                media_group_cache[event.message.grouped_id]['messages'].append(event.message.id)

                # 如果已经有一个延迟任务，取消它并重新启动
                if media_group_cache[event.message.grouped_id]['task']:
                    media_group_cache[event.message.grouped_id]['task'].cancel()

                # 启动一个新的延迟任务来处理媒体组
                media_group_cache[event.message.grouped_id]['task'] = asyncio.create_task(
                    process_media_group(event.message.grouped_id, event.chat_id)
                )
            print(f"handler: 消息属于媒体组 {event.message.grouped_id}，已缓存。")
        else:
            # 单个消息，立即转发
            print(f"handler: 单个消息，将转发到机器人: {target_bot_entity.username}")
            try:
                await client.forward_messages(target_bot_entity, event.message.id, from_peer=event.chat_id)
                print(f"handler: 单个消息已成功转发给机器人: {target_bot_entity.username}")
            except Exception as e:
                print(f"handler: 转发单个消息到机器人 {target_bot_entity.username} 失败: {e}")

async def process_media_group(grouped_id, from_peer):
    await asyncio.sleep(1.5)  # 等待更多媒体组消息到达，可调整
    async with media_group_lock:
        if grouped_id in media_group_cache:
            group_info = media_group_cache[grouped_id]
            message_ids = group_info['messages']
            target_bot = group_info['target_bot']

            print(f"process_media_group: 正在转发媒体组 {grouped_id}，包含 {len(message_ids)} 条消息到 {target_bot.username}")
            try:
                # forward_messages 可以接受一个消息ID列表来转发整个媒体组
                await client.forward_messages(target_bot, message_ids, from_peer=from_peer)
                print(f"process_media_group: 媒体组 {grouped_id} 已成功转发到 {target_bot.username}")
            except Exception as e:
                print(f"process_media_group: 转发媒体组 {grouped_id} 到 {target_bot.username} 失败: {e}")
            finally:
                del media_group_cache[grouped_id] # 转发完成后从缓存中移除

async def join_chat(chat_entity):
    try:
        await client(JoinChannelRequest(chat_entity))
        print(f"成功加入群组/频道: {chat_entity.title}")
    except Exception as e:
        print(f"加入群组/频道 {chat_entity.title} 失败: {e}")

async def leave_chat(chat_entity):
    try:
        await client(LeaveChannelRequest(chat_entity))
        print(f"成功退出群组/频道: {chat_entity.title}")
    except Exception as e:
        print(f"退出群组/频道 {chat_entity.title} 失败: {e}")

async def main():
    # 添加两步验证密码输入
    password = None
    try:
        await client.start(password=lambda: input('Please enter your 2FA password: '))
    except Exception as e:
        print(f"Telethon 客户端启动失败: {e}")
        return

    print("客户端已启动！")

    # 初始构建转发映射
    await rebuild_forwarding_map()
    print(f"初始转发映射 (forwarding_map): {forwarding_map}")

    # 处理来自主账号的命令
    @client.on(NewMessage(func=lambda e: e.is_private and e.sender_id == master_account_id))
    async def command_handler(event):
        command = event.message.text.split(' ', 1)
        cmd = command[0]
        args = command[1] if len(command) > 1 else ""

        if cmd == '/join':
            try:
                chat_entity = await client.get_entity(args)
                await join_chat(chat_entity)
                await event.reply(f"尝试加入 {chat_entity.title}")
            except Exception as e:
                await event.reply(f"加入失败: {e}")

        elif cmd == '/leave':
            try:
                chat_entity = await client.get_entity(args)
                await leave_chat(chat_entity)
                await event.reply(f"尝试退出 {chat_entity.title}")
            except Exception as e:
                await event.reply(f"退出失败: {e}")

        elif cmd == '/add_listen':
            parts = args.split(' ', 1)
            if len(parts) == 2:
                source_chat_arg = parts[0]
                target_bot_username_or_id = parts[1]
                # 确保目标机器人是用户名 (字符串形式)
                target_bot_username_or_id = str(target_bot_username_or_id).strip()
                if not target_bot_username_or_id.startswith('@'):
                    await event.reply("错误：目标机器人用户名必须以 '@' 开头。")
                    return
                
                try:
                    # 尝试获取目标机器人实体以验证其存在
                    await client.get_entity(target_bot_username_or_id)

                    # 检查是否已存在此 source_chat 的映射
                    existing_mapping = next((m for m in bot_mappings if str(m['source_chat']) == str(source_chat_arg)), None)

                    if existing_mapping:
                        if existing_mapping['target_bot'] == target_bot_username_or_id:
                            await event.reply(f"'{source_chat_arg}' 已在监听列表中，并转发给 '{target_bot_username_or_id}'。")
                        else:
                            # 更新现有映射
                            new_bot_mappings = [m for m in bot_mappings if str(m['source_chat']) != str(source_chat_arg)]
                            new_bot_mappings.append({'source_chat': source_chat_arg, 'target_bot': target_bot_username_or_id})
                            update_config_file(new_bot_mappings)
                            await event.reply(f"已更新 '{source_chat_arg}' 的监听，现在转发给 '{target_bot_username_or_id}'。")
                    else:
                        # 添加新的映射
                        new_bot_mappings = bot_mappings + [{'source_chat': source_chat_arg, 'target_bot': target_bot_username_or_id}]
                        update_config_file(new_bot_mappings)
                        await event.reply(f"已将 '{source_chat_arg}' 添加到监听列表，转发给 '{target_bot_username_or_id}'。")

                except Exception as e:
                    await event.reply(f"添加监听失败或目标机器人不存在: {e}")
            else:
                await event.reply("用法: /add_listen <群组/频道链接或 ID> <目标机器人用户名 (以@开头)>")

        elif cmd == '/remove_listen':
            if args:
                source_chat_arg = args
                new_bot_mappings = [m for m in bot_mappings if str(m['source_chat']) != str(source_chat_arg)]
                if len(new_bot_mappings) < len(bot_mappings):
                    update_config_file(new_bot_mappings)
                    await event.reply(f"已将 '{source_chat_arg}' 从监听列表中移除。")
                else:
                    await event.reply(f"'{source_chat_arg}' 不在监听列表中。")
            else:
                await event.reply("用法: /remove_listen <群组/频道链接或 ID>")

        elif cmd == '/list_listen':
            if bot_mappings:
                list_str = "\n".join([f"源聊天: {m['source_chat']} -> 目标机器人: {m['target_bot']}" for m in bot_mappings])
                await event.reply(f"当前监听映射:\n{list_str}")
            else:
                await event.reply("当前没有监听任何群组或频道。")

    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
