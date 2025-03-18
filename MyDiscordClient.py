import discord
import time
from taskDB import get_task, replace_task
from discord.ext import tasks
from api import HOWDY_API
from collections import defaultdict
import traceback

channels = {
    'LOG_CHANNEL': 1338902656890175508,
    'ALERT_CHANNEL': 1229476856995254342
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


    async def check_availability_and_notify(self, user, alert, term_obj, task, alert_channel):
        name, terms, CRN, comp, value, completed = alert['name'], alert['terms'], alert['CRN'], alert['comp'], alert['value'], alert['completed']
        if completed:
            return 0

        isOpen = await term_obj.get_availability(CRN)

        if isOpen:
            embed=discord.Embed(title=f"Alert triggered", description=f"{name}", color=discord.Color.green())
            embed.set_author(name=user.name, icon_url=user.display_avatar.url)
            embed.set_footer(text=term_obj.display_name)

            await alert_channel.send(f'<@{user.id}> Here is your alert: ', embed=embed)
                
            alert['completed'] = True
            replace_task(task['user_id'], alert, alert)  # Update the task as completed

            return 1
        
        return 0
    
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
                    count += 1
                    if not alert['completed'] and classes[alert['terms']][alert['CRN']]:
                        users[user['user_id']].append(alert)
                    
            
            for user_id, alerts in users.items():
                user = self.get_user(user_id)
                embed = discord.Embed(title="Alerts triggered", description=f"", color=discord.Color.green())
                embed.set_author(name=user.name, icon_url=user.display_avatar.url)
                message = f"Alerts for {user.mention}:\n"
                for alert in alerts:
                    embed.add_field(name=f"{alert['name']} ({alert['CRN']})", value=f'{HOWDY_API.term_codes_to_desc[alert['terms']]}', inline=False)
                
                await self.ALERT_CHANNEL.send(message, embed=embed)
            
            for user_id in users:
                for alert in users[user_id]:
                    temp = alert.copy()
                    temp['completed'] = True
                    replace_task(user_id, alert, temp)
                    

            elapsed = time.time() - start
            game = discord.CustomActivity(
                name=f'Just checked {count} sections and notified {len(users)} users in {elapsed:.2f} seconds'
            )

            await self.change_presence(status=discord.Status.idle, activity=game)
        
        except Exception as e:
            await self.LOG_CHANNEL.send(f"Error in my_background_task:\n```{traceback.format_exc()}```")
    

    @my_background_task.before_loop
    async def before_my_task(self):
        await self.wait_until_ready()  # wait until the bot logs in
