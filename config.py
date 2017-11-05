import os

BOT_TOKEN = os.environ['tg_bot_spoilero']

DB_NAME = 'spoilerobot'
DB_USERNAME = 'spoilerobot'
DB_HOST = 'localhost'
DB_PASSWORD = os.environ['tg_bot_spoilero_db_pwd']

if 'tg_spoilero_pepper' not in os.environ:
    print('Please add tg_spoilero_pepper={} to your environmental variables'.format(
        os.urandom(8).hex()
    ))
    exit(1)
HASH_PEPPER = os.environ['tg_spoilero_pepper']
