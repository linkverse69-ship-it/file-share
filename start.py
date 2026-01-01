import asyncio
import os
from datetime import datetime
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerChannel, InputPeerChat, Channel
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
import random

API_ID = os.getenv('API_ID', '26878711')
API_HASH = os.getenv('API_HASH', 'f0225e059f2d5beb398c95b2d8506df1')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://yatoo:yatoo@telegrambot.emo44ma.mongodb.net/?appName=telegrambot')
BOT_TOKEN = os.getenv('BOT_TOKEN', '6454133526:AAFMG9qJUO1RziEY4s_DzursYY4351dOnD8')

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client['telegram_adbot']
sessions_collection = db['sessions']
logs_collection = db['logs']
settings_collection = db['settings']

class AdBot:
    def __init__(self):
        self.bot = None
        self.user_clients = {}
        self.active_campaigns = {}
        self.user_conversations = {}
        self.pending_campaigns = {}
        self.stopped_campaigns = {}
        
    async def start(self):
        self.bot = TelegramClient('bot', API_ID, API_HASH)
        await self.bot.start(bot_token=BOT_TOKEN)
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            user_id = event.sender_id
            await event.respond(
                "Welcome to Advanced Ad Bot\n\n"
                "Disclaimer:\n"
                "Use only for groups you own or have permission\n"
                "Respect group rules & local laws\n"
                "This tool is free, account safety is your responsibility\n\n"
                "Commands:\n"
                "/login - Connect your Telegram account\n"
                "/send_ads - Start sending advertisements\n"
                "/logs - View sending logs\n"
                "/settings - Configure bot settings\n"
                "/logout - Disconnect your account\n"
                "/status - Check campaign status\n"
                "/stop - Stop active campaign",
                buttons=[
                    [Button.inline("Login Now", b"login")],
                    [Button.inline("My Stats", b"stats")]
                ]
            )
        
        @self.bot.on(events.CallbackQuery(pattern=b"login"))
        async def login_callback(event):
            await event.answer()
            await self.initiate_login(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"stats"))
        async def stats_callback(event):
            await event.answer()
            await self.show_stats(event)
        
        @self.bot.on(events.CallbackQuery(pattern=b"stop_campaign"))
        async def stop_callback(event):
            await event.answer()
            user_id = event.sender_id
            if user_id in self.active_campaigns:
                self.active_campaigns[user_id]['stop'] = True
                campaign = self.active_campaigns[user_id]
                self.stopped_campaigns[user_id] = {
                    'message': campaign['message'],
                    'round_delay': campaign['round_delay'],
                    'send_gap': campaign['send_gap'],
                    'client': campaign['client']
                }
                await event.respond(
                    "Campaign stopped.\n\nUse the button below to restart it.",
                    buttons=[[Button.inline("Start Campaign Again", b"restart_campaign")]]
                )
            else:
                await event.respond("No active campaign found.")
        
        @self.bot.on(events.CallbackQuery(pattern=b"restart_campaign"))
        async def restart_callback(event):
            await event.answer()
            user_id = event.sender_id
            if user_id in self.stopped_campaigns:
                campaign_data = self.stopped_campaigns[user_id]
                self.pending_campaigns[user_id] = {
                    'id': f"{user_id}_{datetime.utcnow().timestamp()}",
                    'message': campaign_data['message'],
                    'round_delay': campaign_data['round_delay'],
                    'send_gap': campaign_data['send_gap'],
                    'stop': False,
                    'client': campaign_data['client']
                }
                await event.respond("Campaign restarted! Sending ads now...")
                asyncio.create_task(
                    self.send_campaign(user_id, event.chat_id)
                )
                del self.stopped_campaigns[user_id]
            else:
                await event.respond("No stopped campaign found. Please use /send_ads to create a new campaign.")
        
        @self.bot.on(events.CallbackQuery(pattern=b"continue_all"))
        async def continue_callback(event):
            await event.answer()
            user_id = event.sender_id
            if user_id in self.user_conversations:
                self.user_conversations[user_id]['continue'] = True
        
        @self.bot.on(events.CallbackQuery(pattern=b"back"))
        async def back_callback(event):
            await event.answer()
            user_id = event.sender_id
            if user_id in self.user_conversations:
                self.user_conversations[user_id]['continue'] = False
        
        @self.bot.on(events.CallbackQuery(pattern=b"start_campaign"))
        async def start_campaign_callback(event):
            await event.answer()
            user_id = event.sender_id
            if user_id in self.pending_campaigns:
                await event.respond("Ads started! Sending to all groups...")
                asyncio.create_task(
                    self.send_campaign(user_id, event.chat_id)
                )
            else:
                await event.respond("No pending campaign found. Please use /send_ads to configure a new campaign.")
        
        @self.bot.on(events.NewMessage(pattern='/login'))
        async def login_handler(event):
            await self.initiate_login(event)
        
        @self.bot.on(events.NewMessage(pattern='/send_ads'))
        async def send_ads_handler(event):
            await self.send_ads_workflow(event)
        
        @self.bot.on(events.NewMessage(pattern='/logs'))
        async def logs_handler(event):
            await self.show_logs(event)
        
        @self.bot.on(events.NewMessage(pattern='/settings'))
        async def settings_handler(event):
            await self.show_settings(event)
        
        @self.bot.on(events.NewMessage(pattern='/logout'))
        async def logout_handler(event):
            await self.logout_user(event)
        
        @self.bot.on(events.NewMessage(pattern='/status'))
        async def status_handler(event):
            await self.show_campaign_status(event)
        
        @self.bot.on(events.NewMessage(pattern='/stop'))
        async def stop_handler(event):
            user_id = event.sender_id
            if user_id in self.active_campaigns:
                self.active_campaigns[user_id]['stop'] = True
                campaign = self.active_campaigns[user_id]
                self.stopped_campaigns[user_id] = {
                    'message': campaign['message'],
                    'round_delay': campaign['round_delay'],
                    'send_gap': campaign['send_gap'],
                    'client': campaign['client']
                }
                await event.respond(
                    "Campaign stopped.\n\nUse the button below to restart it.",
                    buttons=[[Button.inline("Start Campaign Again", b"restart_campaign")]]
                )
            else:
                await event.respond("No active campaign to stop.")
        
        print("Bot started successfully!")
        
        await self.load_sessions()
        await self.bot.run_until_disconnected()
    
    async def load_sessions(self):
        async for session_doc in sessions_collection.find():
            user_id = session_doc['user_id']
            session_string = session_doc['session_string']
            try:
                client = TelegramClient(
                    StringSession(session_string),
                    API_ID,
                    API_HASH
                )
                await client.connect()
                if await client.is_user_authorized():
                    self.user_clients[user_id] = client
                    print(f"Loaded session for user {user_id}")
            except Exception as e:
                print(f"Failed to load session for user {user_id}: {e}")
    
    async def initiate_login(self, event):
        user_id = event.sender_id
        
        if user_id in self.user_clients:
            await event.respond("You're already logged in!")
            return
        
        async with self.bot.conversation(user_id) as conv:
            await conv.send_message(
                "Login initiated...\n\n"
                "Send your phone number (with country code, e.g., +1234567890):"
            )
            
            try:
                phone_msg = await conv.get_response(timeout=300)
                phone = phone_msg.text.strip()
                
                client = TelegramClient(
                    StringSession(),
                    API_ID,
                    API_HASH
                )
                await client.connect()
                
                await client.send_code_request(phone)
                await conv.send_message(
                    "OTP sent!\n\n"
                    "Now send the OTP in this format: #ycode123d5"
                )
                
                code_msg = await conv.get_response(timeout=300)
                code_text = code_msg.text.strip()
                if '#ycode' in code_text and 'd5' in code_text:
                    code = code_text.replace('#y', '').replace('code', '').replace('d', '').replace('5', '').strip()
                else:
                    code = ''.join(filter(str.isdigit, code_text))
                
                try:
                    await client.sign_in(phone, code)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'password' in error_msg or 'two' in error_msg:
                        await conv.send_message("2FA enabled. Send your cloud password:")
                        pwd_msg = await conv.get_response(timeout=300)
                        password = pwd_msg.text.strip()
                        try:
                            await client.sign_in(password=password)
                        except Exception as pwd_error:
                            await conv.send_message(f"Password authentication failed: {str(pwd_error)}")
                            await client.disconnect()
                            return
                    else:
                        await conv.send_message(f"Sign in failed: {str(e)}")
                        await client.disconnect()
                        return
                
                if not await client.is_user_authorized():
                    await conv.send_message("Authentication failed. Please try again.")
                    await client.disconnect()
                    return
                
                session_string = client.session.save()
                await sessions_collection.update_one(
                    {'user_id': user_id},
                    {'$set': {
                        'user_id': user_id,
                        'session_string': session_string,
                        'phone': phone,
                        'created_at': datetime.utcnow()
                    }},
                    upsert=True
                )
                
                self.user_clients[user_id] = client
                
                me = await client.get_me()
                name = me.first_name if me and me.first_name else "User"
                await conv.send_message(
                    f"Login successful!\n\n"
                    f"Name: {name}\n"
                    f"Phone: {phone}\n\n"
                    f"Use /send_ads to start sending advertisements!"
                )
                
            except asyncio.TimeoutError:
                await conv.send_message("Timeout! Please try /login again.")
            except Exception as e:
                await conv.send_message(f"Login failed: {str(e)}")
    
    async def send_ads_workflow(self, event):
        user_id = event.sender_id
        
        if user_id not in self.user_clients:
            await event.respond("Please /login first!")
            return
        
        if user_id in self.active_campaigns:
            await event.respond("You already have an active campaign! Use /status to check it or /stop to cancel it.")
            return
        
        client = self.user_clients[user_id]
        
        async with self.bot.conversation(user_id) as conv:
            await conv.send_message("Send your custom ad message:")
            
            try:
                msg_response = await conv.get_response(timeout=600)
                ad_message = msg_response.text
                
                await conv.send_message("Scanning your joined groups...")
                
                dialogs = await client.get_dialogs()
                
                from telethon.tl.types import Chat, Channel
                groups = []
                for d in dialogs:
                    entity = d.entity
                    if isinstance(entity, Chat):
                        groups.append(d)
                    elif isinstance(entity, Channel):
                        if hasattr(entity, 'megagroup') and entity.megagroup and not entity.broadcast:
                            groups.append(d)
                
                total_groups = len(groups)
                
                if total_groups == 0:
                    await conv.send_message("No groups found. Please join some groups first.")
                    return
                
                await conv.send_message(
                    f"Total groups detected: {total_groups}\n\n"
                    "Do you want to send ads to all?",
                    buttons=[
                        [Button.inline("Continue", b"continue_all")],
                        [Button.inline("Back", b"back")]
                    ]
                )
                
                self.user_conversations[user_id] = {'continue': None}
                
                while self.user_conversations[user_id]['continue'] is None:
                    await asyncio.sleep(0.5)
                
                if not self.user_conversations[user_id]['continue']:
                    await conv.send_message("Cancelled.")
                    del self.user_conversations[user_id]
                    return
                
                del self.user_conversations[user_id]
                
                await conv.send_message(
                    "Set round delay in seconds\n"
                    "(minimum 60):"
                )
                delay_response = await conv.get_response(timeout=300)
                round_delay = max(60, int(delay_response.text.strip()))
                
                await conv.send_message(
                    "Set send gap per message\n"
                    "Allowed range: 10.0 to 15.0 seconds.\n"
                    "Send a number (e.g., 10, 12, 15):"
                )
                gap_response = await conv.get_response(timeout=300)
                send_gap = float(gap_response.text.strip())
                send_gap = max(10.0, min(15.0, send_gap))
                
                campaign_id = f"{user_id}_{datetime.utcnow().timestamp()}"
                
                self.pending_campaigns[user_id] = {
                    'id': campaign_id,
                    'message': ad_message,
                    'round_delay': round_delay,
                    'send_gap': send_gap,
                    'stop': False,
                    'client': client,
                    'total_groups': total_groups
                }
                
                await conv.send_message(
                    "Campaign configured!\n\n"
                    f"Groups: {total_groups}\n"
                    f"Round delay: {round_delay}s\n"
                    f"Send gap: {send_gap}s\n\n"
                    "Click 'Start Campaign' to begin sending ads.",
                    buttons=[
                        [Button.inline("Start Campaign", b"start_campaign")],
                        [Button.inline("Cancel", b"back")]
                    ]
                )
                
            except asyncio.TimeoutError:
                await conv.send_message("Timeout! Please try again.")
            except Exception as e:
                await conv.send_message(f"Error: {str(e)}")
    
    async def send_campaign(self, user_id, chat_id):
        if user_id not in self.pending_campaigns:
            return
        
        campaign = self.pending_campaigns[user_id]
        self.active_campaigns[user_id] = campaign
        del self.pending_campaigns[user_id]
        
        client = campaign['client']
        message = campaign['message']
        round_delay = campaign['round_delay']
        send_gap = campaign['send_gap']
        
        round_num = 1
        
        while not campaign['stop']:
            dialogs = await client.get_dialogs()
            
            from telethon.tl.types import Chat, Channel
            groups = []
            for d in dialogs:
                entity = d.entity
                if isinstance(entity, Chat):
                    groups.append(d)
                elif isinstance(entity, Channel):
                    if hasattr(entity, 'megagroup') and entity.megagroup and not entity.broadcast:
                        groups.append(d)
            
            total_groups = len(groups)
            sent = 0
            failed = 0
            
            progress_msg = await self.bot.send_message(
                chat_id,
                f"🔄 Round {round_num} - Starting campaign...\n\n"
                f"📊 Progress: {sent}/{total_groups}\n"
                f"✅ Sent: {sent}\n"
                f"❌ Failed: {failed}"
            )
            
            for idx, group in enumerate(groups, 1):
                if campaign['stop']:
                    break
                
                try:
                    await client.send_message(group.id, message)
                    sent += 1
                    
                    await logs_collection.insert_one({
                        'user_id': user_id,
                        'campaign_id': campaign['id'],
                        'group_id': group.id,
                        'group_name': group.name,
                        'status': 'sent',
                        'timestamp': datetime.utcnow(),
                        'round': round_num
                    })
                    
                except Exception as e:
                    failed += 1
                    await logs_collection.insert_one({
                        'user_id': user_id,
                        'campaign_id': campaign['id'],
                        'group_id': group.id,
                        'group_name': group.name,
                        'status': 'failed',
                        'error': str(e),
                        'timestamp': datetime.utcnow(),
                        'round': round_num
                    })
                
                if idx % 5 == 0 or idx == total_groups:
                    try:
                        await progress_msg.edit(
                            f"🔄 Round {round_num} - Sending advertisements...\n\n"
                            f"📊 Progress: {idx}/{total_groups}\n"
                            f"✅ Sent: {sent}\n"
                            f"❌ Failed: {failed}"
                        )
                    except:
                        pass
                
                await asyncio.sleep(send_gap)
            
            next_round_groups = 0
            if not campaign['stop']:
                try:
                    future_dialogs = await client.get_dialogs()
                    from telethon.tl.types import Chat, Channel
                    future_groups = []
                    for d in future_dialogs:
                        entity = d.entity
                        if isinstance(entity, Chat):
                            future_groups.append(d)
                        elif isinstance(entity, Channel):
                            if hasattr(entity, 'megagroup') and entity.megagroup and not entity.broadcast:
                                future_groups.append(d)
                    next_round_groups = len(future_groups)
                except:
                    next_round_groups = total_groups
            
            try:
                await progress_msg.edit(
                    f"✨ Round {round_num} Complete!\n\n"
                    f"📊 Total Groups: {total_groups}\n"
                    f"✅ Successfully Sent: {sent}\n"
                    f"❌ Failed: {failed}\n"
                    f"⏳ Next round starts in {round_delay} seconds...\n"
                    f"🔄 Next round will scan {next_round_groups} groups"
                )
            except:
                pass
            
            if campaign['stop']:
                try:
                    await self.bot.send_message(
                        chat_id, 
                        "🛑 Campaign stopped successfully!\n\nUse the button below to restart it.",
                        buttons=[[Button.inline("Start Campaign Again", b"restart_campaign")]]
                    )
                except:
                    pass
                break
            
            round_num += 1
            await asyncio.sleep(round_delay)
        
        if user_id in self.active_campaigns:
            del self.active_campaigns[user_id]
    
    async def show_logs(self, event):
        user_id = event.sender_id
        
        logs = await logs_collection.find(
            {'user_id': user_id}
        ).sort('timestamp', -1).limit(10).to_list(10)
        
        if not logs:
            await event.respond("No logs found.")
            return
        
        log_text = "📊 Recent Logs:\n\n"
        for log in logs:
            status_text = "✅ SENT" if log['status'] == 'sent' else "❌ FAILED"
            log_text += (
                f"{status_text} - {log['group_name']}\n"
                f"   Round: {log['round']} | {log['timestamp'].strftime('%H:%M:%S')}\n\n"
            )
        
        await event.respond(log_text)
    
    async def show_stats(self, event):
        user_id = event.sender_id
        
        total_sent = await logs_collection.count_documents({
            'user_id': user_id,
            'status': 'sent'
        })
        
        total_failed = await logs_collection.count_documents({
            'user_id': user_id,
            'status': 'failed'
        })
        
        await event.respond(
            f"📈 Your Statistics:\n\n"
            f"✅ Total Sent: {total_sent}\n"
            f"❌ Total Failed: {total_failed}\n"
            f"📊 Success Rate: {total_sent/(total_sent+total_failed)*100 if total_sent+total_failed > 0 else 0:.1f}%"
        )
    
    async def show_settings(self, event):
        await event.respond(
            "⚙️ Settings:\n\n"
            "Configure your preferences here.\n"
            "(Feature coming soon)"
        )
    
    async def logout_user(self, event):
        user_id = event.sender_id
        
        if user_id in self.active_campaigns:
            await event.respond("Please stop your active campaign first using /stop")
            return
        
        if user_id in self.user_clients:
            await self.user_clients[user_id].disconnect()
            del self.user_clients[user_id]
        
        await sessions_collection.delete_one({'user_id': user_id})
        await event.respond("Logged out successfully!")
    
    async def show_campaign_status(self, event):
        user_id = event.sender_id
        
        if user_id not in self.active_campaigns:
            await event.respond("No active campaign.")
            return
        
        campaign = self.active_campaigns[user_id]
        
        client = campaign['client']
        dialogs = await client.get_dialogs()
        
        from telethon.tl.types import Chat, Channel
        current_groups = []
        for d in dialogs:
            entity = d.entity
            if isinstance(entity, Chat):
                current_groups.append(d)
            elif isinstance(entity, Channel):
                if hasattr(entity, 'megagroup') and entity.megagroup and not entity.broadcast:
                    current_groups.append(d)
        
        await event.respond(
            f"📢 Active Campaign:\n\n"
            f"👥 Current Groups: {len(current_groups)}\n"
            f"⏱️ Round delay: {campaign['round_delay']}s\n"
            f"⏳ Send gap: {campaign['send_gap']}s\n"
            f"▶️ Status: Running",
            buttons=[
                [Button.inline("Stop Campaign", b"stop_campaign")]
            ]
        )

if __name__ == '__main__':
    bot = AdBot()
    asyncio.run(bot.start())
