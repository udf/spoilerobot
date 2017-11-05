import telegram
import html
import json
from functools import wraps


def build_content(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


def send_content(send_function, user_id, content):
    return send_function(chat_id=user_id, **content)


class Photo:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_photo, user_id, content)

    @staticmethod
    def get_content(message):
        best_photo = message.photo[0]
        for i in range(1, len(message.photo)):
            this_photo = message.photo[i]
            if this_photo.width * this_photo.height > best_photo.width * best_photo.height:
                best_photo = this_photo

        return build_content(photo=best_photo.file_id, caption=message.caption)


class Audio:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_audio, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(audio=message.audio.file_id, caption=message.caption)


class Document:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_document, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(document=message.document.file_id, caption=message.caption)


class Video:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_video, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(video=message.video.file_id, caption=message.caption)


class Voice:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_voice, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(voice=message.voice.file_id, caption=message.caption)


class Sticker:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_sticker, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(sticker=message.sticker.file_id)


class VideoNote:
    __name__ = 'Video Note'

    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_video_note, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(video_note=message.video_note.file_id)


class Location:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_location, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(
            latitude=message.location.latitude,
            longitude=message.location.longitude
        )


class Contact:
    @staticmethod
    def send(bot, user_id, content):
        send_content(bot.send_contact, user_id, content)

    @staticmethod
    def get_content(message):
        return build_content(
            phone_number=message.contact.phone_number,
            first_name=message.contact.first_name,
            last_name=message.contact.last_name
        )


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