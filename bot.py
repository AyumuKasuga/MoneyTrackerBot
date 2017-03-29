import os
import json
import signal
import asyncio
import functools
from datetime import datetime
from calendar import monthrange

import telepot
import telepot.aio
from telepot.namedtuple import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from storage import MoneyTrackerStorage


def make_keyboard(lists):
    keyboard = [[] for _ in range(len(lists))]
    for idx, row in enumerate(lists):
        for label in row:
            keyboard[idx].append(KeyboardButton(text=label))
    keyboard.append([KeyboardButton(text='/cancel')])
    return keyboard


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

    def get_total_msg(self, total, limit):
        msg = 'Total spent in this month: *{}*'.format(total)
        if limit:
            now = datetime.now()
            days_left = monthrange(now.year, now.month)[1] - now.day + 1
            delta = int(limit) - int(total)
            delta = 0 if delta < 0 else delta
            delta_today = int(delta/days_left)
            msg += '''\nAccording your montly limit {}
you have *{}* left for this month (*{}* for today). 📊'''.format(limit, delta, delta_today)
            if delta == 0:
                msg += ' 🙀'
            else:
                msg += ' 😸'
        return msg

    async def send_total(self, chat_id):
        msg = self.get_total_msg(*self.st.get_total_and_limit())
        await self.sendMessage(
            chat_id,
            msg,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardRemove()
        )

    def export_worksheet(self, chat_id):
        self.loop.create_task(self.sendChatAction(chat_id, 'upload_document'))
        document_name = '{0}.pdf'.format(datetime.now().strftime('%B_%Y'))
        worksheet_content = self.st.export_worksheet()
        self.loop.create_task(
            self.sendDocument(chat_id, document=(document_name, worksheet_content))
        )

    def save_entry(self, chat_id, data, msg_id):
        username = self.users.get(chat_id)
        try:
            total_month, limit_month = self.st.add_entry(
                data['sum'],
                data['category'],
                username,
                data['description']
            )
        except Exception as e:
            print(e)
            self.loop.create_task(self.editMessageText(
                (chat_id, msg_id),
                'Error! Try again!\n' + str(e))
            )
        else:
            msg = '\u2705 Added!'
            msg += self.get_total_msg(total_month, limit_month)
            self.loop.create_task(
                self.editMessageText((chat_id, msg_id), msg, parse_mode='Markdown')
            )
            if self.config.get('broadcast'):
                broadcast_users = set(self.users.keys()) - {chat_id}
                broadcast_msg = '{username} just added *{sum}* {category} {description}'.format(
                    username=self.users.get(chat_id),
                    sum=data['sum'],
                    category=data['category'],
                    description=data['description']
                )
                for uid in broadcast_users:
                    self.loop.create_task(
                        self.sendMessage(uid, broadcast_msg, parse_mode='Markdown')
                    )

    async def on_chat_message(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        print(msg['text'])
        if chat_id not in self.users:
            print("unknown chat_id: ", chat_id)
            self.loop.create_task(self.sendMessage(
                chat_id,
                'Sorry, I do not know who you are! '
                'If you want to learn more about MoneyTrackerBot please visit '
                'https://github.com/AyumuKasuga/MoneyTrackerBot'
            ))
            return

        if msg['text'].startswith('/start'):
            self.loop.create_task(self.sendMessage(chat_id, 'Welcome!'))
        elif msg['text'].startswith('/total'):
            self.loop.create_task(self.send_total(chat_id))
        elif msg['text'].startswith('/download'):
            self.loop.run_in_executor(
                None,
                functools.partial(self.export_worksheet, chat_id)
            )
        elif msg['text'].startswith('/add'):
            self.sessions[chat_id] = {}
            self.loop.create_task(
                self.sendMessage(
                    chat_id,
                    '\U0001f4b8 Please enter sum that you just spent',
                    reply_markup=ReplyKeyboardRemove()
                )
            )
        elif msg['text'].startswith('/setlimit'):
            try:
                limit = int(msg['text'].split(' ')[1])
            except Exception as e:
                self.loop.create_task(
                    self.sendMessage(
                        chat_id,
                        str(e),
                        reply_markup=ReplyKeyboardRemove()
                    )
                )
            else:
                with (await self.lock):
                    self.loop.run_in_executor(
                        None,
                        functools.partial(self.st.set_limit, limit)
                    )
                self.loop.create_task(
                    self.sendMessage(
                        chat_id,
                        'Okay, Your montly limit will set to {}.'.format(limit),
                        reply_markup=ReplyKeyboardRemove()
                    )
                )

        elif msg['text'].startswith('/cancel'):
            if chat_id in self.sessions:
                self.sessions.pop(chat_id)
            self.loop.create_task(
                self.sendMessage(
                    chat_id,
                    'Okay, forgot everything \U0001f642',
                    reply_markup=ReplyKeyboardRemove()
                )
            )
        else:
            if chat_id not in self.sessions:
                self.loop.create_task(self.sendMessage(chat_id, '\U0001f914'))
            elif len(self.sessions[chat_id]) == 0:
                if msg['text'].isdigit():
                    markup = ReplyKeyboardMarkup(
                        keyboard=make_keyboard(self.config.get("categories")),
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                    self.loop.create_task(self.sendMessage(
                        chat_id,
                        '\U0001f4dd Okay! Now select a category',
                        reply_markup=markup)
                    )
                    self.sessions[chat_id].update({'sum': msg['text']})
                else:
                    self.loop.create_task(self.sendMessage(
                        chat_id,
                        '\u274c Please enter correct sum (only digest without dots)'
                    ))
            elif not self.sessions[chat_id].get('category'):
                self.sessions[chat_id].update({'category': msg['text']})
                markup = ReplyKeyboardMarkup(
                    keyboard=make_keyboard(self.config.get("descriptions")),
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                self.loop.create_task(self.sendMessage(
                    chat_id,
                    'Okay! Now write or select description',
                    reply_markup=markup
                ))
            elif not self.sessions[chat_id].get('description'):
                self.sessions[chat_id].update({'description': msg['text']})
                data = self.sessions.pop(chat_id)
                await self.sendMessage(
                    chat_id,
                    'Thank you! Now we are trying to save your entry.',
                    reply_markup=ReplyKeyboardRemove()
                )
                wait_msg = await self.sendMessage(
                    chat_id,
                    '\U0001f551 please wait...',
                    parse_mode='Markdown',
                )
                with (await self.lock):
                    self.loop.run_in_executor(
                        None,
                        functools.partial(self.save_entry, chat_id, data, wait_msg['message_id'])
                    )


def bye(signame):
    print("got signal %s: exit" % signame)
    loop.stop()


with open('conf/config.json') as f:
    config = json.loads(f.read())

loop = asyncio.get_event_loop()
for signame in ('SIGTERM', 'SIGINT'):
    loop.add_signal_handler(getattr(signal, signame), functools.partial(bye, signame))
token = config.pop("telegram_token")
st = MoneyTrackerStorage(
    keyfile='conf/MoneyTracker.json',
    spreadsheet_name=config["spreadsheet_name"]
)
bot = MoneyTrackerBot(token=token, config=config, st=st, loop=loop)
loop.create_task(bot.message_loop())
print("pid %s listening..." % os.getpid())

try:
    loop.run_forever()
finally:
    loop.close()
