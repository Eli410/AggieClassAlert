import discord
from discord.ext import commands
import time
from taskDB import get_task, replace_task, write_tasks
from discord.ext import tasks
from api import HOWDY_API
from collections import defaultdict
import traceback
import json
import datetime
from zoneinfo import ZoneInfo
import os
from userSettings import USER_PREFERENCES
import sys
import ast
from dotenv import load_dotenv
import aiohttp


load_dotenv()

channels = {
    'ERROR_LOG_CHANNEL': 1338902656890175508,
    'ALERT_CHANNEL': 1229476856995254342,
    'AVAILABILITY_LOG_CHANNEL': 1354172503366303825,
    'ALERT_CREATION_LOG_CHANNEL': 1354176644486791376,
    'DUMP_CHANNEL': 1359280915183964321,
    'LINK_CHANNEL': 1358494693859659877,
}

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = int(time.time())
        self.tree = discord.app_commands.CommandTree(self)
        
    async def setup_hook(self) -> None:
        # self.my_background_task.start()
        pass

    async def on_ready(self):
        for channel, channel_id in channels.items():
            setattr(self, channel, self.get_channel(channel_id))

        self.COMMANDS = await self.tree.fetch_commands()
        self.COMMANDS = {command.name: command for command in self.COMMANDS}

        await self.tree.sync()
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

    async def on_error(self, event_method, /, *args, **kwargs):
        # Log the error to the ERROR_LOG_CHANNEL
        error_message = f"Error in {event_method} with args {args} and kwargs {kwargs}"
        with open('error_log.txt', 'w') as f:
            f.write(f"{traceback.format_exc()}")
        await self.ERROR_LOG_CHANNEL.send(error_message, file=discord.File('error_log.txt', filename='error_log.txt'))
        os.remove('error_log.txt')
        return await super().on_error(event_method, *args, **kwargs)
    
    async def on_message(self, message: discord.Message):
        if '@everyone' in message.content and not message.author.guild_permissions.administrator:
            await message.delete()
            return

        if message.author == self.user:
            return
        if message.channel.id != self.LINK_CHANNEL.id:
            return
        if '```json' not in message.content:
            return
        
        json_data = message.content.replace('```json', '').replace('```', '').strip()
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            await message.channel.send(f"Invalid JSON format: {e}")
            return

            
        if 'field' in data:
            operation = data['field']
            val = data['value']
            term, crn, disabled = val['term'], val['CRN'], val.get('disabled', False)
            section_details = await HOWDY_API.get_section_details(term, crn)
            name = f"{section_details['SUBJECT_CODE']} {section_details['COURSE_NUMBER']}-{section_details['SECTION_NUMBER']}"

            if operation == 'Post':
                if write_tasks(int(val['user_id']), [(name, term, crn, disabled)]):
                    await self.LINK_CHANNEL.send((operation, name, term, crn, val['time'], True))
                else:
                    await self.LINK_CHANNEL.send((operation, name, term, crn, val['time'], False))
            elif operation == 'Delete':
                replace_task(int(val['user_id']), {'name': name, 'terms': term, 'CRN': crn}, None)
                await self.LINK_CHANNEL.send((operation, name, term, crn, val['time'], True))
        else:
            # link
            email, tup, discord_id, sync_id = data.values()
            raw = []
            for crn, term in tup:
                section_details = await HOWDY_API.get_section_details(term, crn)
                name = f"{section_details['SUBJECT_CODE']} {section_details['COURSE_NUMBER']}-{section_details['SECTION_NUMBER']}"
                if write_tasks(int(discord_id), [(name, term, crn)]):
                    raw.append((name, term, crn, True))
                else:
                    raw.append((name, term, crn, False))
            await self.LINK_CHANNEL.send(f"Linked <@{discord_id}> ({email}) with {len(raw)} classes ({sum(1 for _, _, _, success in raw if success)} successful) from the website.\n- {'\n- '.join(f'{name} ({term}, {crn})' for name, term, crn, success in raw)}")

            user_tasks = get_task(int(discord_id))
            header = {
                "X-AUTH-TOKEN": os.getenv('WEB_LINK_TOKEN'),
                "Content-Type": "application/json",
            }
            payload = {
                'email': email,
                'sync_id': sync_id,
                'list': [[task['CRN'], task['terms']] for task in user_tasks]
            }
            url = os.getenv('WEB_LINK_URL')
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=header, json=payload) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        await self.LINK_CHANNEL.send(f"Successfully sent {len(user_tasks)} tasks for <@{discord_id}> ({email}) to website.")
                    else:
                        await self.LINK_CHANNEL.send(f"Failed to send tasks for <@{discord_id}> ({email}) to website. Status code: {response.status}")
                        await self.LINK_CHANNEL.send(f"Error data: {response_text}")


    @tasks.loop(seconds=60) 
    async def my_background_task(self):
        try:
            count = 0
            start = time.time()
            await self.change_presence(
                status=discord.Status.online, 
                activity=discord.CustomActivity(name='Checking sections...')
                )
            
            
            classes = HOWDY_API.get_availability()
            if not classes:
                return
            users = defaultdict(list)
            all_tasks = get_task("ALL")
            for user in all_tasks:
                for alert in user['tasks']:
                    if not alert['completed']:
                        count += 1
                        try:
                            if classes[alert['terms']][alert['CRN']]:
                                users[user['user_id']].append(alert)
                        except Exception as e:
                            alert['error'] = e
                            users[user['user_id']].append(alert)

            
            for user_id, alerts in users.items():
                user = self.get_user(user_id)
                if not user:
                    await self.ERROR_LOG_CHANNEL.send(f"User with ID <@{user_id}> not found. Skipping alert notification.")
                    continue                    
                embed = discord.Embed(title="Alerts triggered", description=f"", color=discord.Color.green())
                embed.set_author(name=user.name, icon_url=user.display_avatar.url)
                message = f"Alerts for {user.mention}:\n"
                for i, alert in enumerate(alerts):
                    if i <= 24:
                        if 'error' in alert:
                            embed.add_field(name=f"Error in {alert['name']} ({alert['CRN']})", value=f"It has been disabled", inline=False)
                        else:
                            embed.add_field(name=f"{alert['name']} ({alert['CRN']})", value=f'{HOWDY_API.term_codes_to_desc[alert['terms']]}', inline=False)
                    else:
                        embed.description = "Some alerts are not displayed due to too many alerts"
                        break
                
                if len(embed.fields) > 0:
                    if USER_PREFERENCES.get_user_settings(user_id)['DM']:
                        try:
                            await user.send(embed=embed)
                        except:
                            await self.ALERT_CHANNEL.send(f"DM failed, sending in channel instead" + message, embed=embed)
                    else:
                        await self.ALERT_CHANNEL.send(message, embed=embed)
                    
                    await self.DUMP_CHANNEL.send(embed=embed)
            
            for user_id in users:
                for alert in users[user_id]:
                    temp = alert.copy()
                    temp['completed'] = True
                    if 'error' in temp:
                        del temp['error']
                    replace_task(user_id, alert, temp)
                    

            elapsed = time.time() - start
            game = discord.CustomActivity(
                name=f'Just checked {count} sections and notified {len(users)} users in {elapsed:.2f} seconds'
            )

            await self.change_presence(status=discord.Status.idle, activity=game)

            with open('log.json', 'w') as file:
                file.write(json.dumps(classes, indent=4))
            await self.AVAILABILITY_LOG_CHANNEL.send(file=discord.File('log.json', filename=f"{datetime.datetime.now(ZoneInfo('US/Central')).strftime('%Y-%m-%d %H:%M:%S')}.json"))
        
        except Exception as e:
            with open('error_log.txt', 'w') as f:
                f.write(f"{traceback.format_exc()}")
            await self.ERROR_LOG_CHANNEL.send(f"An error occurred in the background task: {e} {self.application.owner.mention}", file=discord.File('error_log.txt', filename='error_log.txt'))
            os.remove('error_log.txt')

    @my_background_task.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in
