import time
from collections import defaultdict
from config import (
    RATE_LIMIT_DECAY_PERIOD, RATE_LIMIT_PRESSURE_LIMIT, RATE_LIMIT_BAN_TIME,
    ADMIN_ID
)
from util import pretty_timestamp


class UserPressure:
    def __init__(self):
        self.pressure = 0
        self.last_hit = 0
        self.inbox = ''


def hit(user_id, database, bot):
    user = PRESSURES[user_id]

    current_time = time.time()
    time_delta = current_time - user.last_hit
    user.pressure += -time_delta / RATE_LIMIT_DECAY_PERIOD + 1
    user.pressure = max(0, user.pressure)
    user.last_hit = current_time

    if user.pressure > RATE_LIMIT_PRESSURE_LIMIT:
        ban_expiry = current_time + RATE_LIMIT_BAN_TIME
        pretty_expiry = pretty_timestamp(ban_expiry)
        remove_count = database.ban_user(user_id, ban_expiry)
        user.inbox = (
            f'You have been banned from creating new spoilers until {pretty_expiry}.\n'
            f'As a result of this, {remove_count} of your most recent spoilers have been permanently deleted.\n\n'
            f'Please contact <a href="tg://user?id={ADMIN_ID}">my owner</a> if you feel this was done in error!'
        )
        try_inbox(user_id, bot)
        bot.send_message(
            chat_id=ADMIN_ID,
            text=f'{user_id} has been banned until {pretty_expiry}; {remove_count} spoilers were removed.'
        )


def try_inbox(user_id, bot):
    user = PRESSURES[user_id]
    if not user.inbox:
        return

    try:
        bot.send_message(chat_id=user_id, text=user.inbox, parse_mode='HTML')
        user.inbox = ''
    except:
        pass


PRESSURES = defaultdict(UserPressure)