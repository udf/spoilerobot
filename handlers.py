import telegram
import html

class Photo:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Audio:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Document:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Video:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Voice:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Sticker:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class VideoNote:
    __name__ = 'Video Note'

    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Location:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Venue:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Contact:
    @staticmethod
    def send(bot, user_id, content):
        raise NotImplemented

    @staticmethod
    def get_content(update):
        raise NotImplemented


class Text:
    @staticmethod
    def send(bot, user_id, content):
        bot.send_message(
            chat_id=user_id,
            text=content
        )

    @staticmethod
    def get_content(update):
        return update.message.text


class HTML:
    @staticmethod
    def send(bot, user_id, content):
        bot.send_message(
            chat_id=user_id,
            text=content,
            parse_mode='HTML'
        )

    @staticmethod
    def get_content(update):
        return update.message.text_html


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