import os

# the telegram bot token
BOT_TOKEN = os.environ['tg_bot_spoilero']

# the user_id of the administrator
ADMIN_ID = int(os.environ['tg_bot_spoilero_admin'])

# postgresql database configs
DB_NAME = 'spoilerobot'
DB_USERNAME = 'spoilerobot'
DB_HOST = 'localhost'
DB_PASSWORD = os.environ['tg_bot_spoilero_db_pwd']

# pepper is used to season the hash of the uuid so that it's harder to brute force a uuid
if 'tg_spoilero_pepper' not in os.environ:
    print('Please add tg_spoilero_pepper={} to your environmental variables'.format(
        os.urandom(8).hex()
    ))
    exit(1)
HASH_PEPPER = os.environ['tg_spoilero_pepper']

# the time in seconds in between timestamps of the request count statistic
REQUEST_COUNT_RESOLUTION = 600

# how many seconds before old taps are ignored
MULTIPLE_CLICK_TIMEOUT = 20

# how long in seconds to cache minor spoilers on the client-side
MINOR_SPOILER_CACHE_TIME = 3600

# The maximun length (in bytes) for a inline query before an advanced spoilers has to be used
# (this is a telegram limitation)
MAX_INLINE_LENGTH = 256


# Rate limit configurations
# If the pressure of a user reaches the limit, then the user is temporarily banned
# On each hit, pressure is calculated as follows:
# new_pressure = old_pressure - x + 1
# (where x is the time between the current and previous hit as a fraction of RATE_LIMIT_DECAY_PERIOD)
# ie deltas greater than DECAY_PERIOD decreases pressure
#    while deltas less than DECAY_PERIOD increases pressure (by a maximun of 1)

# How long in seconds before a new hit has no effect on the pressure of a user
RATE_LIMIT_DECAY_PERIOD = 300

# The maximum amount of pressure before a user is banned
RATE_LIMIT_PRESSURE_LIMIT = 10

# How long in seconds a user should be banned for
RATE_LIMIT_BAN_TIME = 24*60*60

# How long in seconds before a spoiler's owner if forgotten
# When a user is banned, all their recent spoilers are deleted
# this value controls how far back "recent" actually is
SPOILER_OWNER_FORGET_AFTER = 60 * 20