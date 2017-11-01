import os
import time
import html
import threading
import sqlite3
from uuid import uuid4
from collections import defaultdict

import telegram.error
from telegram import (
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Updater, InlineQueryHandler, ChosenInlineResultHandler,
    MessageHandler, CallbackQueryHandler, CommandHandler, Filters
)
import validators
import logging


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


# how many seconds before old taps are ignored
MUTLIPLE_CLICK_TIMEOUT = 20
# store image urls as variables so it's easier to understand what they are
IMAGE_ERROR = 'http://i.imgur.com/zZMQBmK.png'
IMAGE_MAJOR_CUSTOM = 'http://i.imgur.com/kuIyXod.png'
IMAGE_MINOR_CUSTOM = 'http://i.imgur.com/xFbwNIp.png'
IMAGE_MAJOR_NORMAL = 'http://i.imgur.com/3qqCZZk.png'
IMAGE_MINOR_NORMAL = 'http://i.imgur.com/csh5H5O.png'


class ClickCounter:
    def __init__(self, required_clicks):
        self.last_click = 0
        self.count = 0
        self.required_clicks = required_clicks

    def click(self):
        if time.time() - self.last_click >= MUTLIPLE_CLICK_TIMEOUT:
            self.count = 0
        self.count += 1
        self.last_click = time.time()
        return self.count >= self.required_clicks
        

class User:
    def __init__(self):
        self.conversation_state = 0
        self.click_counters = defaultdict(lambda: ClickCounter(2))

    def record_click(self, uuid):
        if not decode_uuid(uuid)['is_major']:
            return True

        if self.click_counters[uuid].click():
            del self.click_counters[uuid]
            return True

        return False


def get_uuid(is_major=False, ignore=False, unused1=False, unused2=False, old=None):
    """
    Creates a uuid where the first character stores data about the spoiler
    bit:          3              2             1        0
    meaning: {major flag} {url/ignore flag} {unused} {unused}
    """
    flag = int(is_major) << 3 | int(ignore) << 2 | int(unused1) << 1 | unused2
    return format(flag, 'x') + (old[1:] if old else str(uuid4()))


def decode_uuid(uuid):
    flag = int(uuid[0], 16)
    return {
        'is_major': bool(flag & 8),
        'ignore': bool(flag & 4),
       #'unused': bool(flag & 2),
       #'unused': bool(flag & 1)
    }


def html_escape(s):  
    return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def db_insert_spoiler(uuid, content_type, description, content):
    with db_lock:
        db_cursor.execute(
            'INSERT INTO spoilers (uuid, type, description, content) VALUES (?,?,?,?)',
            (uuid[1:].lower(), content_type, description, content)
        )
        db_connection.commit()


def db_get_spoiler(uuid):
    db_cursor.execute('SELECT type, description, content FROM spoilers WHERE uuid=?', (uuid[1:],))
    return db_cursor.fetchone()


def get_article(title, description, thumb_url, text, uuid, reply_markup=None):
    return InlineQueryResultArticle(
        id=uuid,
        title=title,
        description=description,
        thumb_url=thumb_url,
        thumb_width=512,
        thumb_height=512,
        input_message_content=InputTextMessageContent(
            message_text=text,
            parse_mode='HTML'
        ),
        reply_markup=reply_markup
    )


def get_single_buttton_inline_keyboard(text, callback_data=None, url=None, switch_inline_query=None):
    """Returns a single button InlineKeyboardMarkup"""
    return InlineKeyboardMarkup([[InlineKeyboardButton(
        text=text,
        callback_data=callback_data,
        url=url,
        switch_inline_query=switch_inline_query
    )]])


def query_split(query):
    """Attempts to split a query into a tuple of (description, content)"""
    temp_split = [split.strip() for split in query.split(':::', 1)]
    if len(temp_split) >= 2 and temp_split[0] and temp_split[1]:
        return temp_split[0], temp_split[0]
    return '', query.strip()


def get_inline_results(query):
    was_fetched = False
    old_uuid = None
    content_type = 'Text'
    if query.startswith('id:'):
        uuid = query[3:].lower().strip()
        db_cursor.execute('SELECT type, description, content FROM spoilers WHERE uuid=?', (uuid[1:],))
        spoiler = db_cursor.fetchone()
        if spoiler:
            old_uuid = uuid
            description = spoiler['description']
            content = spoiler['content']
            content_type = spoiler['type']

    if not old_uuid:
        description, content = query_split(query)
    if not content:
        return []

    if content_type == 'Text':
        content_type = 'Text only'

    is_url = bool(validators.url(content)) or bool(validators.url('http://' + content))
    if is_url:
        get_inline_keyboard = lambda text: get_single_buttton_inline_keyboard('Show spoiler', url=content)
    else:
        get_inline_keyboard = lambda text: get_single_buttton_inline_keyboard(text, callback_data=uuid)

    ignore = is_url or bool(old_uuid)
    results = []
    # if we are able to split query into a custom description + custom content
    if description and content:
        # add those options to our results
        # custom major
        uuid = get_uuid(is_major=True, ignore=ignore, old=old_uuid)
        results.append(get_article(
            title='Custom Major Spoiler',
            description=f'{content_type}, custom title, double tap',
            thumb_url=IMAGE_MAJOR_CUSTOM,
            text=f'<b>Major Spoiler:</b> <pre>{description}</pre>',
            uuid=uuid,
            reply_markup=get_inline_keyboard('Double tap to show spoiler')
        ))
        # custom minor
        uuid = get_uuid(is_major=False, ignore=ignore, old=old_uuid)
        results.append(get_article(
            title='Custom Minor Spoiler',
            description=f'{content_type}, custom title, single tap',
            thumb_url=IMAGE_MINOR_CUSTOM,
            text=f'<i>Minor Spoiler:</i> <pre>{description}</pre>',
            uuid=uuid,
            reply_markup=get_inline_keyboard('Show spoiler')
        ))
    else:
        # add normal spoiler options to our results
        # normal major
        uuid = get_uuid(is_major=True, ignore=ignore, old=old_uuid)
        results.append(get_article(
            title='Major Spoiler!',
            description=f'{content_type}, double tap',
            thumb_url=IMAGE_MAJOR_NORMAL,
            text='<b>Major Spoiler!</b>',
            uuid=uuid,
            reply_markup=get_inline_keyboard('Double tap to show spoiler')
        ))
        # normal minor
        uuid = get_uuid(is_major=False, ignore=ignore, old=old_uuid)
        results.append(get_article(
            title='Minor Spoiler',
            description=f'{content_type}, single tap',
            thumb_url=IMAGE_MINOR_NORMAL,
            text='<i>Minor Spoiler</i>',
            uuid=uuid,
            reply_markup=get_inline_keyboard('Show spoiler')
        ))

    return results


def on_inline(bot, update):
    query = update.inline_query.query
    query = html.unescape(query)

    update.inline_query.answer(
        get_inline_results(query),
        cache_time=1,
        is_personal=True,
        switch_pm_text='Advanced spoiler (media etc.)...',
        switch_pm_parameter='new'
    )


def on_inline_chosen(bot, update):
    """Stores the chosen inline result in the db, if necessary"""
    result = update.chosen_inline_result
    uuid = result.result_id
    
    if decode_uuid(uuid)['ignore']:
        return

    description, content = query_split(result.query)

    db_insert_spoiler(uuid, 'Text', description, html_escape(content))


def send_spoiler(bot, user_id, spoiler):
    #TODO:handle PM-ing other types
    #document, photo, video, audio, sticker, voice
    if spoiler['type'] != 'Text':
        raise NotImplemented

    bot.send_message(
        chat_id=user_id,
        text=spoiler['content'],
        parse_mode='HTML'
    )


def on_callback_query(bot, update, users):

    query = update.callback_query
    uuid = query.data

    print('cbquery', query)
    spoiler = db_get_spoiler(uuid)
    if not spoiler:
        update.callback_query.answer(text='Spoiler not found. Too old?')
        return

    from_id = query.from_user.id
    user_data = users[from_id]

    if not user_data.record_click(uuid):
        update.callback_query.answer(text='Please tap again to see the spoiler')
        return

    if spoiler['type'] == 'Text' and len(spoiler['content']) <= 200:
        update.callback_query.answer(
            text=spoiler['content'],
            show_alert=True
        )
    else:
        try:
            send_spoiler(bot, from_id, spoiler)
            update.callback_query.answer(text='The spoiler has been sent to you as a direct message.')
        except (telegram.error.BadRequest, telegram.error.Unauthorized):
            #TODO check what other errors could happen
            update.callback_query.answer(url=f't.me/spoilerobetabot?start={uuid}')


def on_message(bot, update, users):
    print('message', update.message)
    #TODO:use this and message.text_html for handling the "waiting for content" conversation state


def cmd_start(bot, update, args, users):
    #TODO:allow preparing an advanced spoiler by advancing user conversation state
    if args:
        spoiler = db_get_spoiler(args[0])
        if spoiler:
            send_spoiler(bot, update.message.from_user.id, spoiler)


def cmd_clear(bot, update):
    update.message.reply_text(250 * '.\n')


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    users = defaultdict(User)
    updater = Updater(os.environ['tg_bot_spoilero'])

    dp = updater.dispatcher

    dp.add_handler(InlineQueryHandler(on_inline))
    dp.add_handler(ChosenInlineResultHandler(on_inline_chosen))
    dp.add_handler(CallbackQueryHandler(
        lambda bot, update: on_callback_query(bot, update, users)
    ))
    dp.add_handler(CommandHandler(
        'start',
        lambda bot, update, args: cmd_start(bot, update, args, users),
        pass_args=True
    ))
    dp.add_handler(CommandHandler('clear', cmd_clear))
    dp.add_handler(MessageHandler(
        Filters.all,
        lambda bot, update: on_message(bot, update, users)
    ))

    dp.add_error_handler(error)

    updater.start_polling()

    # TODO maybe custom loop to clear old user click records?
    updater.idle()


if __name__ == '__main__':
    db_connection = sqlite3.connect('spoilerobot.db', check_same_thread=False)
    db_connection.row_factory = sqlite3.Row
    db_cursor = db_connection.cursor()
    db_cursor.execute('''
        CREATE TABLE IF NOT EXISTS spoilers (
            uuid TEXT PRIMARY KEY,
            timestamp INTEGER DEFAULT (strftime('%s', 'now')),
            type TEXT,
            description TEXT,
            content TEXT
        )
    ''')
    db_connection.commit()
    db_lock = threading.Lock()

    main()