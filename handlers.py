import telegram
import html
import json
from functools import wraps


def decode_content(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        kwargs['content'] = json.loads(kwargs['content'])
        return function(*args, **kwargs)
    return wrapped


class Photo:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        bot.send_photo(
            chat_id=user_id,
            photo=content['id'],
            caption=content.get('caption', '')
        )

    @staticmethod
    def get_content(message):
        best_photo = message.photo[0]
        for i in range(1, len(message.photo)):
            this_photo = message.photo[i]
            if this_photo.width > best_photo.width or this_photo.height > best_photo.height:
                best_photo = this_photo

        return json.dumps({
            'id': best_photo.file_id,
            'caption': message.caption or ''
        })


class Audio:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Document:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Video:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Voice:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Sticker:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class VideoNote:
    __name__ = 'Video Note'

    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Location:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Venue:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Contact:
    @staticmethod
    @decode_content
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(message):
        raise NotImplemented


class Text:
    @staticmethod
    def send(bot, user_id, content):
        bot.send_message(
            chat_id=user_id,
            text=content
        )

    @staticmethod
    def get_content(message):
        return message.text


class HTML:
    @staticmethod
    def send(bot, user_id, content):
        bot.send_message(
            chat_id=user_id,
            text=content,
            parse_mode='HTML'
        )

    @staticmethod
    def get_content(message):
        return message.text_html


ATTACHMENT_MAPPING = {
    telegram.Audio: Audio,
    telegram.Contact: Contact,
    telegram.Document: Document,
    telegram.Location: Location,
    telegram.PhotoSize: Photo,
    telegram.Sticker: Sticker,
    telegram.Venue: Venue,
    telegram.Video: Video,
    telegram.VideoNote: VideoNote,
    telegram.Voice: Voice
}


def get_handler(message, attachment):
    if attachment is None:
        if html.unescape(message.text_html) == message.text:
            return Text
        else:
            return HTML

    if isinstance(attachment, list):
        attachment = attachment[0]

    return ATTACHMENT_MAPPING.get(attachment.__class__, None)