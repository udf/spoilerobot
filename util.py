import html
import os

from telegram import (
    InlineQueryResultArticle, InputTextMessageContent,
    InlineKeyboardMarkup, InlineKeyboardButton
)


def get_uuid(is_major=False, ignore=False, unused1=False, unused2=False, old=None):
    """
    Creates a uuid where the first character stores data about the spoiler
    bit:          3              2             1        0
    meaning: {major flag} {url/ignore flag} {unused} {unused}
    """
    ignore = ignore or bool(old)
    flag = int(is_major) << 3 | int(ignore) << 2 | int(unused1) << 1 | unused2
    return format(flag, 'x') + (old[1:] if old else os.urandom(24).hex())


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


def html_unescape(s):  
    return html.unescape(str(s).replace('<br/>', '\n'))


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
