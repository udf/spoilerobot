import logging
from collections import defaultdict
from signal import signal, SIGINT, SIGTERM, SIGABRT

import telegram.error
from telegram.ext import (
    Updater, InlineQueryHandler, ChosenInlineResultHandler,
    MessageHandler, CallbackQueryHandler, CommandHandler, Filters
)
import validators

from user import User
from util import *
import config
from database import Database
import handlers


logger = logging.getLogger()
logFormatter = logging.Formatter("%(asctime)s - %(levelname)-5.5s - %(message)s")
logger.setLevel(logging.INFO)

fileHandler = logging.FileHandler('bot.log')
fileHandler.setFormatter(logFormatter)
logger.addHandler(fileHandler)

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
logger.addHandler(consoleHandler)


# store image urls as variables so it's easier to understand what they are
IMAGE_MINOR = 'https://i.imgur.com/qrViKOz.png'
IMAGE_MAJOR = 'https://i.imgur.com/6oSoT16.png'


def query_split(query):
    """Attempts to split a query into a tuple of (description, content)"""
    temp_split = [split.strip() for split in query.split(':::', 1)]
    if len(temp_split) >= 2 and temp_split[0] and temp_split[1]:
        return temp_split[0], temp_split[1]
    return '', query.strip()


def get_inline_results(query):
    old_uuid = None
    content_type = 'Text'
    content = ''
    description = ''
    if query.startswith('id:'):
        uuid = query[3:].lower().strip()
        spoiler = database.get_spoiler(uuid)
        if spoiler:
            old_uuid = uuid
            description = spoiler['description']
            content = spoiler['content']
            content_type = spoiler['type']
        else:
            content_type = 'Text (id not found)'

    if not old_uuid:
        description, content = query_split(query)
    if not content:
        return []

    is_url = (
        isinstance(content, str) and
        (bool(validators.url(content)) or bool(validators.url('http://' + content)))
    )
    if is_url:
        def get_inline_keyboard(text):
            return get_single_buttton_inline_keyboard('Show spoiler', url=content)
        content_type = 'URL'
    else:
        def get_inline_keyboard(text):
            return get_single_buttton_inline_keyboard(text, callback_data=uuid)

    # modify the inline description and reply text of the result if a custom title has been set
    if description and content:
        description = f'<pre>{html_escape(description)}</pre>'
        description_fmt = f'{content_type}, custom title, {{}}'
        text_fmt = '<{0}>{1}:</{0}> {3}'
    else:
        description_fmt = f'{content_type}, {{}}'
        text_fmt = '<{0}>{1}{2}</{0}>'

    results = []
    # add options to our results
    uuid = get_uuid(is_major=True, ignore=is_url, old=old_uuid)
    results.append(get_article(
        title='Major Spoiler',
        description=description_fmt.format('double tap'),
        thumb_url=IMAGE_MAJOR,
        text=text_fmt.format('b', 'Major Spoiler', '!', description),
        uuid=uuid,
        reply_markup=get_inline_keyboard('Double tap to show spoiler')
    ))

    uuid = get_uuid(is_major=False, ignore=is_url, old=old_uuid)
    results.append(get_article(
        title='Minor Spoiler',
        description=description_fmt.format('single tap'),
        thumb_url=IMAGE_MINOR,
        text=text_fmt.format('i', 'Minor Spoiler', '', description),
        uuid=uuid,
        reply_markup=get_inline_keyboard('Show spoiler')
    ))

    return results


def on_inline(bot, update):
    query = update.inline_query.query

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

    description, content = query_split(result.query)

    log_update(update, f"created Text from inline")
    database.insert_spoiler(uuid, 'Text', description, content)


def send_spoiler(bot, user_id, spoiler):
    getattr(handlers, spoiler['type']).send(
        bot,
        user_id,
        content=spoiler['content']
    )


def on_callback_query(bot, update, users):
    uuid = update.callback_query.data
    from_id = update.callback_query.from_user.id

    if not users[from_id].record_click(uuid):
        update.callback_query.answer(text='Please tap again to see the spoiler')
        return

    spoiler = database.get_spoiler(uuid)
    if not spoiler:
        update.callback_query.answer(text='Spoiler not found. Too old?', cache_time=3600)
        return
    is_major = decode_uuid(uuid)['is_major']

    log_update(update, f"requested {spoiler['type']} major={is_major}")

    if spoiler['type'] == 'Text' and len(spoiler['content']) <= 200:
        cache_time = 0 if is_major else 3600
        update.callback_query.answer(
            text=spoiler['content'],
            show_alert=True,
            cache_time=cache_time
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
        database.insert_spoiler(uuid, user.spoiler_type, user.spoiler_description, user.spoiler_content)

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

        spoiler = database.get_spoiler(args[0])
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
    def on_signal(signum, frame):
        if updater.running:
            updater.stop()
        else:
            exit(1)


    users = defaultdict(User)
    updater = Updater(config.BOT_TOKEN)

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


    for sig in (SIGINT, SIGTERM, SIGABRT):
        signal(sig, on_signal)

    # TODO maybe clear old user click records?
    next_request_save = 0
    while updater.running:
        if time.time() >= next_request_save:
            next_request_save = time.time() + 5
            database.store_request_count()

        time.sleep(1)


if __name__ == '__main__':
    database = Database()
    main()
