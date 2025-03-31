import discord
import time
from taskDB import get_task, replace_task
from discord.ext import tasks
from api import HOWDY_API
from collections import defaultdict
import traceback
import json
import datetime
from zoneinfo import ZoneInfo
import os

channels = {
    'ERROR_LOG_CHANNEL': 1338902656890175508,
    'ALERT_CHANNEL': 1229476856995254342,
    'AVAILABILITY_LOG_CHANNEL': 1354172503366303825,
    'ALERT_CREATION_LOG_CHANNEL': 1354176644486791376,
}

class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_time = int(time.time())
        self.tree = discord.app_commands.CommandTree(self)
        
    async def setup_hook(self) -> None:
        self.my_background_task.start()
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
                embed = discord.Embed(title="Alerts triggered", description=f"", color=discord.Color.green())
                embed.set_author(name=user.name, icon_url=user.display_avatar.url)
                message = f"Alerts for {user.mention}:\n"
                for alert in alerts:
                    if 'error' in alert:
                        user = await self.fetch_user(user_id)
                        await user.send(f'An error occured in your alert, it has been disabled\n```json\n{alert}\n```')
                    else:
                        embed.add_field(name=f"{alert['name']} ({alert['CRN']})", value=f'{HOWDY_API.term_codes_to_desc[alert['terms']]}', inline=False)
                
                if len(embed.fields) > 0:
                    await self.ALERT_CHANNEL.send(message, embed=embed)
            
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
