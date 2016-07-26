import os
import json
import signal
import asyncio
import functools

import telepot
import telepot.aio
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardHide

from storage import MoneyTrackerStorage


class MoneyTrackerBot(telepot.aio.Bot):

    def __init__(self, *args, config=None, st=None, **kwargs):
        super(MoneyTrackerBot, self).__init__(*args, **kwargs)
        self.config = config
        self.st = st
        self.users = {int(x[0]): x[1] for x in self.config["users"].items()}
        self.sessions = {}
        self.lock = asyncio.Lock(loop=self.loop)

    @staticmethod
    def get_command(msg):
        if 'entities' in msg:
            for entity in msg['entities']:
                if entity['type'] == 'bot_command':
                    offset, length = entity['offset'], entity['length']
                    return msg['text'][offset:length], msg['text'][offset+length:].strip()
        return None, None

    async def send_total(self, chat_id):
        msg = 'Total spent in this month: {}'.format(self.st.get_total())
        await self.sendMessage(chat_id, msg, reply_markup=ReplyKeyboardHide())

    def save_entry(self, chat_id, data):
        username = self.users.get(chat_id)
        self.loop.create_task(self.sendMessage(chat_id, '\U0001f551 please wait...'))
        try:
            total_month = self.st.add_entry(
                data['sum'],
                data['category'],
                username,
                data['description']
            )
        except Exception as e:
            print(e)
            self.loop.create_task(self.sendMessage(chat_id, 'Error! Try again!\n' + str(e)))
        else:
            msg = '\u2705 Added! Total spent in this month: {}'.format(total_month)
            self.loop.create_task(self.sendMessage(chat_id, msg, reply_markup=ReplyKeyboardHide()))

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        print(msg['text'])
        if chat_id not in self.users:
            print("unknown chat_id: ", chat_id)
            self.loop.create_task(self.sendMessage(chat_id, 'Sorry, i do not know who you are'))
            return
        if msg['text'].startswith('/start'):
            self.loop.create_task(self.sendMessage(chat_id, 'Welcome!'))
        elif msg['text'].startswith('/total'):
            self.loop.create_task(self.send_total(chat_id))
        elif msg['text'].startswith('/add'):
            self.sessions[chat_id] = {}
            self.loop.create_task(self.sendMessage(chat_id, '\U0001f4b8 Please enter sum that you just spent', reply_markup=ReplyKeyboardHide()))
        elif msg['text'].startswith('/cancel'):
            if chat_id in self.sessions:
                self.sessions.pop(chat_id)
            self.loop.create_task(self.sendMessage(chat_id, 'Okay, forgot everything \U0001f642', reply_markup=ReplyKeyboardHide()))
        else:
            if chat_id not in self.sessions:
                self.loop.create_task(self.sendMessage(chat_id, '\U0001f914'))
            elif len(self.sessions[chat_id]) == 0:
                if msg['text'].isdigit():
                    markup = ReplyKeyboardMarkup(keyboard=[
                        [KeyboardButton(text='\U0001f354 \U0001f35f'), KeyboardButton(text='\U0001f373'), KeyboardButton(text='\U0001f4b0')],
                        [KeyboardButton(text='\U0001f485'), KeyboardButton(text='\U0001f455'), KeyboardButton(text='\U0001f48a')],
                        [KeyboardButton(text='\U0001f3ac \U0001f46f'), KeyboardButton(text='\U0001f6bd\U0001f6c1'), KeyboardButton(text='\U0001f3e0')],
                        [KeyboardButton(text='\U0001f47e')],
                        [KeyboardButton(text='/cancel')]
                    ], resize_keyboard=True, one_time_keyboard=True)
                    self.loop.create_task(self.sendMessage(chat_id, '\U0001f4dd Okay! Now select a category', reply_markup=markup))
                    self.sessions[chat_id].update({'sum': msg['text']})
                else:
                    self.loop.create_task(self.sendMessage(chat_id, '\u274c Please enter correct sum (only digest without dots)'))
            elif not self.sessions[chat_id].get('category'):
                self.sessions[chat_id].update({'category': msg['text']})
                markup = ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text='\U0001f4b8')],
                    [KeyboardButton(text='Lunch'), KeyboardButton(text='Vegetables'), KeyboardButton(text='Supermarket')],
                    [KeyboardButton(text='/cancel')]
                ], resize_keyboard=True, one_time_keyboard=True)
                self.loop.create_task(self.sendMessage(chat_id, 'Okay! Now write or select description', reply_markup=markup))
            elif not self.sessions[chat_id].get('description'):
                self.sessions[chat_id].update({'description': msg['text']})
                data = self.sessions.pop(chat_id)
                with (await self.lock):
                    self.loop.run_in_executor(None, functools.partial(self.save_entry, chat_id, data))


def bye(signame):
    print("got signal %s: exit" % signame)
    loop.stop()


with open('conf/config.json') as f:
    config = json.loads(f.read())

loop = asyncio.get_event_loop()
for signame in ('SIGTERM', 'SIGINT'):
    loop.add_signal_handler(getattr(signal, signame), functools.partial(bye, signame))
token = config.pop("telegram_token")
st = MoneyTrackerStorage(keyfile='conf/MoneyTracker.json', spreadsheet_name=config["spreadsheet_name"])
bot = MoneyTrackerBot(token=token, config=config, st=st, loop=loop)
loop.create_task(bot.message_loop())
print("pid %s listening..." % os.getpid())

try:
    loop.run_forever()
finally:
    loop.close()
