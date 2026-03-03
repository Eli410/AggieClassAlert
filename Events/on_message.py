import json
import os

import aiohttp
import discord

from api import HOWDY_API
from taskDB import get_task, replace_task, write_tasks


async def on_message(client, message: discord.Message):
    if '@everyone' in message.content and not message.author.guild_permissions.administrator:
        await message.delete()
        return

    if message.author == client.user:
        return
    if message.channel.id != client.LINK_CHANNEL.id:
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
                await client.LINK_CHANNEL.send((operation, name, term, crn, val['time'], True))
            else:
                await client.LINK_CHANNEL.send((operation, name, term, crn, val['time'], False))
        elif operation == 'Delete':
            replace_task(int(val['user_id']), {'name': name, 'terms': term, 'CRN': crn}, None)
            await client.LINK_CHANNEL.send((operation, name, term, crn, val['time'], True))
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
        class_lines = "\n- ".join(
            f"{name} ({term}, {crn})" for name, term, crn, success in raw
        )
        await client.LINK_CHANNEL.send(
            f"Linked <@{discord_id}> ({email}) with {len(raw)} classes "
            f"({sum(1 for _, _, _, success in raw if success)} successful) from the website.\n"
            f"- {class_lines}"
        )

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
                    await client.LINK_CHANNEL.send(
                        f"Successfully sent {len(user_tasks)} tasks for <@{discord_id}> ({email}) to website."
                    )
                else:
                    await client.LINK_CHANNEL.send(
                        f"Failed to send tasks for <@{discord_id}> ({email}) to website. Status code: {response.status}"
                    )
                    await client.LINK_CHANNEL.send(f"Error data: {response_text}")

