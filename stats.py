from datetime import datetime
import os

# Force matplotlib to not use any Xwindow backend.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as md
import telegram

from database import Database
from config import BOT_TOKEN, REQUEST_COUNT_RESOLUTION
from util import timestamp_floor

DESTINATION_CHAT = os.environ['spoilero_stats_destination']


db_cursor = Database().get_cursor()
CURRENT_TIMESTAMP = timestamp_floor(24*3600)
CUTOFF_TIMESTAMP = CURRENT_TIMESTAMP - 24*3600*5
YESTERDAY_TIMESTAMP = CURRENT_TIMESTAMP - 24*3600
CUTOFF_TIME = datetime.utcfromtimestamp(CUTOFF_TIMESTAMP)
CURRENT_TIME = datetime.utcfromtimestamp(CURRENT_TIMESTAMP)
bins = 720

# setup plot
fig, ax1 = plt.subplots(figsize=(9,5))
plt.title('{} (until {})'.format(
    'Statistics for the past 5 days',
    CURRENT_TIME.strftime('%Y-%m-%d %H:%M UTC')
))
ax1.set_xlabel('Time (UTC)')



# fetch data
db_cursor.execute(
    'SELECT timestamp, count FROM requests WHERE timestamp >= %s AND timestamp < %s',
    (CUTOFF_TIMESTAMP, CURRENT_TIMESTAMP)
)
requests = db_cursor.fetchall()

# process data
x = [datetime.utcfromtimestamp(request['timestamp']) for request in requests]
counts = [request['count'] for request in requests]
requests_today = sum(
    request['count'] for request in requests if request['timestamp'] >= YESTERDAY_TIMESTAMP
)

# plot data
ax1.hist(x, bins=bins, weights=counts, color='xkcd:sky blue')
ax1.axis(xmin=CUTOFF_TIME, xmax=CURRENT_TIME)
ax1.set_ylabel('Requests', color='xkcd:bright blue')
ax1.tick_params('y', colors='xkcd:bright blue')



# fetch data
db_cursor.execute('''
    (SELECT timestamp FROM spoilers) UNION ALL (SELECT timestamp FROM spoilers_v2)
''')
spoilers = sorted(spoiler['timestamp'] for spoiler in db_cursor.fetchall() if spoiler['timestamp'] < CURRENT_TIMESTAMP)
total_spoilers = len(spoilers)

# process data
x = [datetime.utcfromtimestamp(timestamp) for timestamp in spoilers]
y = list(range(total_spoilers))
x.append(CURRENT_TIME)
y.append(y[-1])
spoiler_count = sum(1 for timestamp in spoilers if timestamp >= CUTOFF_TIMESTAMP)
spoilers_today = sum(1 for timestamp in spoilers if timestamp >= YESTERDAY_TIMESTAMP)

# plot data
ax2 = ax1.twinx()
ax2.xaxis.set_major_formatter(md.DateFormatter('%m/%d'))
ax2.plot(x, y, color='xkcd:red')
ax2.axis(xmin=CUTOFF_TIME, xmax=CURRENT_TIME, ymin=total_spoilers - spoiler_count - 1)
ax2.set_ylabel('Total spoilers', color='xkcd:red')
ax2.tick_params('y', colors='xkcd:red')

# save
fig.tight_layout()
plt.savefig('stats.png', dpi=100)


# send
caption = (
    'In the past 24 hours:\n'
    f'{spoilers_today} spoilers created\n'
    f'{requests_today} requests made\n'
    '#SpoileroStats'
)
print(caption)

bot = telegram.Bot(BOT_TOKEN)
bot.send_photo(
    chat_id=DESTINATION_CHAT,
    photo=open('stats.png', 'rb'),
    caption=caption
)
os.remove('stats.png')
