import logging
import sqlite3

import ics
import aiohttp
import asyncio
import arrow
import yaml
from telethon import TelegramClient, events


async def process_date(date: arrow.Arrow, extras: dict):
	if 'FREQ' in extras.keys() and extras['FREQ'] == 'WEEKLY':
		if 'INTERVAL' in extras.keys():
			return True if int(date.date().day - arrow.now().date().day) % int(extras['INTERVAL']) * 7 == 0 else False

		return True if int(date.date().day - arrow.now().date().day) % 7 == 0 else False
	else:
		raise Exception('No FREQ in extras')


async def handle(event: ics.event.Event) -> dict:
	return {
		'name': event.name,
		'begin': event.begin,
		'end': event.end,
		'description': event.description,
		'location': event.location,
		'extras': dict(x.split('=') for x in event.extra[0].value.split(';'))
	}


async def get_calendar(url: str) -> []:
	async with aiohttp.ClientSession() as session:
		async with session.get(url) as resp:
			c = ics.Calendar(await resp.text())

	return [await handle(event) for event in c.events]
	# return [event for event in c.events]

async def main(config):
	logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=config['log_level'])
	logger = logging.getLogger(__name__)
	url = 'https://calendar.google.com/calendar/ical/69utla364f1vvc87v7vo6q95og%40group.calendar.google.com/private-f266f3e4cc5d22a5e6eedc8ff9a51efd/basic.ics'
	con = sqlite3.connect('users.db')
	cur = con.cursor()
	# cur.execute('''DROP TABLE users''')
	cur.execute(
		"""CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, userid INTEGER, groupid TEXT)""")

	client = TelegramClient(**config['telethon_settings'])
	print("Starting")
	await client.start(bot_token=config['bot_token'])
	print("Started")

	@client.on(events.NewMessage(pattern='/plan'))
	async def send_timetable(event):
		if event.message.sender_id in [x[0] for x in cur.execute("SELECT userid FROM users")]:
			message = list()
			group_id = cur.execute("SELECT groupid FROM users WHERE userid = ?", (event.message.sender_id,)).fetchone()[
				0]
			calendar = await get_calendar(url)
			for vevent in calendar:
				x = await process_date(vevent['begin'], vevent['extras'])
				if x and (group_id in vevent['description']):
					message.append({'Event': vevent['name'],
					                'Begins': vevent['begin'].format('HH:mm'),
					                'Ends': vevent['end'].format('HH:mm'),
					                'Description': vevent['description'],
					                'Location': vevent['location']})

			message.sort(key=lambda data: data['Begins'])

			await event.reply('\n----------\n'.join(['\n'.join(': '.join(x) for x in comp.items()) for comp in
			                                         message]) if message else 'Nothing to do today')
		else:
			await event.reply(
				'First you have to enroll yourself to subscribers list by typing /subscribe -g <your group> od by picking it from inline list :)')

	@client.on(events.NewMessage(pattern='/subscribe'))
	async def add_subscriber(event):
		if event.message.sender_id not in [x[0] for x in cur.execute("SELECT userid FROM users")]:
			cur.execute("INSERT INTO users(userid, groupid) VALUES (?, ?)",
			            (event.message.sender_id, event.text.split(' ')[1]))
			con.commit()

			await event.reply(f'Enrolled to {event.text.split(" ")[1]}')
		else:
			await event.reply('You are enrolled already. If you want to change group unsubsribe and subscribe again')

	@client.on(events.NewMessage(pattern='/unsubscribe'))
	async def del_subscriber(event):
		if event.message.sender_id in [x[0] for x in cur.execute("SELECT userid FROM users")]:
			cur.execute("DELETE FROM users WHERE userid = ?", (event.message.sender_id,))
			con.commit()

			await event.reply('Removed!')
		# await client.send_message(await client.get_entity(event.message.peer_id.user_id), 'Removed!')
		else:
			await event.reply('You are not enrolled, so y u askin for removal? lol.')

	# await client.send_message(await client.get_entity(event.message.peer_id.user_id),
	#                           'You are not enrolled, so y u askin for removal? lol.')

	@client.on(events.NewMessage(pattern='/todos'))
	async def send_todos(event):
		await event.reply('Not implemented yet (not gonna happen tbh.)')
	# 	if 'ekursy' in event.text:
	# 		url = event.text.split(' ')[1]
	# 		cal = await get_calendar(url)
	# 		message = list()
	# 		for vevent in cal:
	# 			message.append({
	# 				'empty': 0
	# 			})
	#
	# 	pass

	@client.on(events.InlineQuery())
	async def inline_handle(event):
		await event.answer(
			[event.builder.article('Give me a timetable!', text='/plan'),
			 event.builder.article('Give me my todos!', text='/todos'),
			 event.builder.article('Enroll me to T1-1!', text='/subscribe T1-1'),
			 event.builder.article('Enroll me to T1-2!', text='/subscribe T1-2'),
			 event.builder.article('Enroll me to T2-1!', text='/subscribe T2-1'),
			 event.builder.article('Enroll me to T2-2!', text='/subscribe T2-2'),
			 event.builder.article('Unsubscribe', text='/unsubscribe')
			 ])

	async with client:
		print("Good morning!")
		await client.run_until_disconnected()


if __name__ == '__main__':
	with open("config.yml", 'r') as f:
		config = yaml.safe_load(f)
		asyncio.get_event_loop().run_until_complete(main(config))
