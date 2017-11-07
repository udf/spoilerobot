import telegram
import html
from functools import wraps


def build_content(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}


def send_content(send_function, user_id, content):
    return send_function(chat_id=user_id, **content)


class GenericHandler:
    """Wrapper class for most handlers"""
    def __init__(self, name, get_send_function, extract_content):
        self.__name__ = name
        self.get_send_function = get_send_function
        self.extract_content = extract_content
    
    def send(self, bot, user_id, content):
        send_content(self.get_send_function(bot), user_id, content)

    def get_content(self, message):
        return self.extract_content(message)


class Photo:
    """Wrapper class for handling photos"""
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


class Text:
    """Wrapper class for handling plain text messages"""
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
    """Wrapper class for handling messages with formatting entities"""
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


Audio = GenericHandler(
    'Audio',
    lambda bot: bot.send_audio,
    lambda message: build_content(
        audio=message.audio.file_id,
        caption=message.caption
    )
)


Document = GenericHandler(
    'Document',
    lambda bot: bot.send_document,
    lambda message: build_content(document=message.document.file_id, caption=message.caption)
)


Video = GenericHandler(
    'Video',
    lambda bot: bot.send_video,
    lambda message: build_content(video=message.video.file_id, caption=message.caption)
)


Voice = GenericHandler(
    'Voice',
    lambda bot: bot.send_voice,
    lambda message: build_content(voice=message.voice.file_id, caption=message.caption)
)


Sticker = GenericHandler(
    'Sticker',
    lambda bot: bot.send_sticker,
    lambda message: build_content(sticker=message.sticker.file_id)
)


VideoNote = GenericHandler(
    'Video Note',
    lambda bot: bot.send_video_note,
    lambda message: build_content(video_note=message.video_note.file_id)
)


Location = GenericHandler(
    'Location',
    lambda bot: bot.send_location,
    lambda message: build_content(
        latitude=message.location.latitude,
        longitude=message.location.longitude
    )
)


Contact = GenericHandler(
    'Contact',
    lambda bot: bot.send_contact,
    lambda message: build_content(
        phone_number=message.contact.phone_number,
        first_name=message.contact.first_name,
        last_name=message.contact.last_name
    )
)


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