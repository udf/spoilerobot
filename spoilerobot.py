import logging
import os
import sqlite3
import threading
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

from user import User
from util import *
import handlers


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# store image urls as variables so it's easier to understand what they are
IMAGE_MAJOR_CUSTOM = 'http://i.imgur.com/kuIyXod.png'
IMAGE_MINOR_CUSTOM = 'http://i.imgur.com/xFbwNIp.png'
IMAGE_MAJOR_NORMAL = 'http://i.imgur.com/3qqCZZk.png'
IMAGE_MINOR_NORMAL = 'http://i.imgur.com/csh5H5O.png'


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


def query_split(query):
    """Attempts to split a query into a tuple of (description, content)"""
    temp_split = [split.strip() for split in query.split(':::', 1)]
    if len(temp_split) >= 2 and temp_split[0] and temp_split[1]:
        return temp_split[0], temp_split[1]
    return '', query.strip()


def get_inline_results(query):
    was_fetched = False
    old_uuid = None
    content_type = 'Text'
    if query.startswith('id:'):
        uuid = query[3:].lower().strip()
        spoiler = db_get_spoiler(uuid)
        if spoiler:
            old_uuid = uuid
            description = spoiler['description']
            content = spoiler['content']
            content_type = spoiler['type']

    if not old_uuid:
        description, content = query_split(query)
    if not content:
        return []

    is_url = bool(validators.url(content)) or bool(validators.url('http://' + content))
    if is_url:
        get_inline_keyboard = lambda text: get_single_buttton_inline_keyboard(
            'Show spoiler', url=content)
    else:
        get_inline_keyboard = lambda text: get_single_buttton_inline_keyboard(
            text, callback_data=uuid)

    ignore = is_url or bool(old_uuid)
    description = html_escape(description)
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
    query = html_unescape(query)

    update.inline_query.answer(
        get_inline_results(query),
        cache_time=1,
        is_personal=True,
        switch_pm_text='Advanced spoiler (media etc.)…',
        switch_pm_parameter='inline'
    )


def on_inline_chosen(bot, update):
    """Stores the chosen inline result in the db, if necessary"""
    result = update.chosen_inline_result
    uuid = result.result_id

    if decode_uuid(uuid)['ignore']:
        return

    description, content = query_split(html_unescape(result.query))

    log_update(update, f"created Text from inline")
    db_insert_spoiler(uuid, 'Text', description, content)


def send_spoiler(bot, user_id, spoiler):
    getattr(handlers, spoiler['type']).send(
        bot,
        user_id,
        content=spoiler['content']
    )


def on_callback_query(bot, update, users):
    query = update.callback_query
    uuid = query.data

    spoiler = db_get_spoiler(uuid)
    if not spoiler:
        update.callback_query.answer(text='Spoiler not found. Too old?')
        return

    log_update(update, f"requested {spoiler['type']}")

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
            update.callback_query.answer(
                text='The spoiler has been sent to you as a direct message.')
        except (telegram.error.BadRequest, telegram.error.Unauthorized):
            update.callback_query.answer(url=f't.me/spoilerobot?start={uuid}')


def on_message(bot, update, users):
    user = users[update.message.from_user.id]
    if user.handle_conversation(bot, update) == 'END':
        uuid = get_uuid()

        log_update(update, f"created {user.spoiler_type}")
        db_insert_spoiler(uuid, user.spoiler_type, user.spoiler_description, user.spoiler_content)

        update.message.reply_text(
            text='Done! Your advanced spoiler is ready.',
            reply_markup=get_single_buttton_inline_keyboard(
                'Send it',
                switch_inline_query='id:'+uuid
            )
        )
        user.reset_state()


def cmd_start(bot, update, args, users):
    user = users[update.message.from_user.id]

    if args:
        if args[0] == 'inline':
            return user.handle_start(bot, update, True)

        spoiler = db_get_spoiler(args[0])
        if spoiler:
            return send_spoiler(bot, update.message.from_user.id, spoiler)

    user.handle_start(bot, update)


def cmd_cancel(bot, update, users):
    users[update.message.from_user.id].handle_cancel(bot, update)


def cmd_clear(bot, update):
    update.message.reply_text(250 * '.\n')


def cmd_help(bot, update):
    update.message.reply_text(
        text='Type /start to prepare an advanced spoiler with a custom title.\n\n'
        'You can type quick spoilers by using @SpoileroBot in inline mode:\n'
        '<pre>@SpoileroBot spoiler here…</pre>\n\n'
        'Custom titles can also be used from inline mode as follows:\n'
        '<pre>@SpoileroBot title for the spoiler:::contents of the spoiler</pre>\n'
        'Note that the title will be immediately visible!',
        parse_mode='HTML'
    )


def log_update(update, msg):
    logger.info(
        f"{update.effective_user.username} ({update.effective_user.id}) {msg}"
    )


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
    dp.add_handler(CommandHandler(
        'cancel',
        lambda bot, update: cmd_cancel(bot, update, users)
    ))
    dp.add_handler(CommandHandler('clear', cmd_clear))
    dp.add_handler(CommandHandler('help', cmd_help))

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
