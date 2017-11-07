import base64
import json
import os
import threading
import time

import psycopg2
import psycopg2.extras
from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

import config
from util import timestamp_floor

REQUEST_COUNT_LOCK = threading.Lock()
REQUEST_COUNT = 0

def store_request_count(cursor):
    global REQUEST_COUNT
    current_count = 0
    with REQUEST_COUNT_LOCK:
        current_count = REQUEST_COUNT
        REQUEST_COUNT = 0

    if current_count == 0:
        return

    cursor.execute('''
        INSERT INTO requests (timestamp, count) VALUES (%(timestamp)s, %(count)s)
        ON CONFLICT (timestamp) DO UPDATE
        SET count = requests.count + %(count)s;
        ''',
        {'timestamp': timestamp_floor(config.REQUEST_COUNT_RESOLUTION), 'count': current_count}
    )



def derive_key(uuid, salt):
    return base64.urlsafe_b64encode(Scrypt(
        salt=salt,
        length=32,
        n=2**10,
        r=8,
        p=1,
        backend=default_backend()
    ).derive(uuid.encode()))


def hash_uuid(uuid):
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update((uuid + config.HASH_PEPPER).encode())
    return digest.finalize()


def connect():
    connection = psycopg2.connect(
        dbname=config.DB_NAME,
        user=config.DB_USERNAME,
        host=config.DB_HOST,
        password=config.DB_PASSWORD
    )

    connection.autocommit = True
    cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS spoilers (
            hash BYTEA PRIMARY KEY,
            timestamp INTEGER DEFAULT date_part('epoch', now()),
            salt BYTEA,
            token BYTEA
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            timestamp INTEGER PRIMARY KEY,
            count INTEGER
        )
    ''')

    return cursor


def insert_spoiler(cursor, uuid, content_type, description, content):
    uuid = uuid[1:]
    salt = os.urandom(8)

    data = json.dumps({
        'type': content_type,
        'description': description,
        'content': content,
    })
    token = Fernet(derive_key(uuid, salt)).encrypt(data.encode())

    cursor.execute(
        'INSERT INTO spoilers (hash, salt, token) VALUES (%s, %s, %s)',
        (hash_uuid(uuid), salt, token)
    )


def get_spoiler(cursor, uuid):    
    uuid = uuid[1:]
    cursor.execute(
        'SELECT salt, token FROM spoilers WHERE hash=%s',
        (hash_uuid(uuid),)
    )
    spoiler = cursor.fetchone()
    if not spoiler:
        print(f'failed to fetch "{uuid}"')
        return None

    global REQUEST_COUNT
    with REQUEST_COUNT_LOCK:
        REQUEST_COUNT += 1

    token = Fernet(derive_key(uuid, bytes(spoiler['salt']))).decrypt(bytes(spoiler['token']))
    return json.loads(token)
