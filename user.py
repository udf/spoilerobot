from collections import defaultdict
import time
import html
import telegram
from util import *
import handlers


# how many seconds before old taps are ignored
MULTIPLE_CLICK_TIMEOUT = 20


class ClickCounter:
    def __init__(self, required_clicks):
        self.last_click = 0
        self.count = 0
        self.required_clicks = required_clicks

    def click(self):
        if time.time() - self.last_click >= MULTIPLE_CLICK_TIMEOUT:
            self.count = 0
        self.count += 1
        self.last_click = time.time()
        return self.count >= self.required_clicks


class User:
    def __init__(self):
        self.click_counters = defaultdict(lambda: ClickCounter(2))
        self.started_from_inline = False
        self.handle_conversation = None
        self.spoiler_type = None
        self.spoiler_content = None
        self.spoiler_description = None
        self.reset_state()

    def reset_state(self):
        self.spoiler_type = None
        self.spoiler_content = None
        self.spoiler_description = None
        self.handle_conversation = self.conversation_neutral

    def record_click(self, uuid):
        if not decode_uuid(uuid)['is_major']:
            return True

        if self.click_counters[uuid].click():
            del self.click_counters[uuid]
            return True

        return False

    def handle_start(self, bot, update, from_inline=False):
        if self.handle_conversation != self.conversation_neutral:
            return

        update.message.reply_text(
            text='Preparing a spoiler. To cancel, type /cancel.\n\n'
            'First send the content to be spoiled. It can be text, photo, or any other media.'
        )
        self.handle_conversation = self.conversation_handle_content
        self.started_from_inline = from_inline

    def handle_cancel(self, bot, update):
        if self.handle_conversation == self.conversation_neutral:
            return
        self.handle_conversation = self.conversation_neutral

        reply_markup = None
        if self.started_from_inline:
            reply_markup = get_single_buttton_inline_keyboard('OK', switch_inline_query='')
        update.message.reply_text(
            text='The spoiler preparation has been cancelled.',
            reply_markup=reply_markup
        )

    def conversation_neutral(self, bot, update):
        # only handle_start can change the state from here
        pass

    def conversation_handle_content(self, bot, update):
        handler = handlers.get_handler(update.message, update.message.effective_attachment)
        if not handler:
            update.message.reply_text('Unrecognized media type.')
            return

        self.spoiler_type = handler.__name__
        self.spoiler_content = handler.get_content(update.message)
        self.handle_conversation = self.conversation_handle_title

        update.message.reply_text(
            text='Now send a title for the spoiler (maximum 256 characters). '
            'It will be immediately visible and can be used to add a small description for your spoiler.\n'
            'Type a dash (-) now if you do not want a title for your spoiler.'
        )

    def conversation_handle_title(self, bot, update):
        message = update.message
        if not message.text:
            return

        if len(message.text) > 256:
            update.message.reply_text(
                text='The given title is too long (maximum 256 characters).'
            )
            return

        self.spoiler_description = '' if message.text == '-' else message.text
        return 'END'
