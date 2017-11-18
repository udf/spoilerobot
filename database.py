import base64
import json
import os
import threading
import time

import psycopg2
import psycopg2.extras
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.exceptions import InvalidSignature

import config
from util import timestamp_floor


def derive_key(uuid, salt):
    """derives a key from a uuid+unique salt using scrypt"""
    return base64.urlsafe_b64encode(
        Scrypt(
            salt=salt,
            length=32,
            n=2**10,
            r=8,
            p=1,
            backend=default_backend()
        ).derive(uuid.encode())
    )


def hash_uuid(uuid):
    """
    hashes a uuid using SHA256 (these are the primary keys of the database)
    we can't use a unique salt here because we need the hash to find the row
    """
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update((uuid + config.HASH_PEPPER).encode())
    return digest.finalize()


class Database:
    def __init__(self):
        self.request_count = 0
        # because certain database operations take place over multiple commands and threads
        # we need a lock to prevent any race conditions
        self.lock = threading.Lock()
        self.connect()

    def connect(self):
        self.connection = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USERNAME,
            host=config.DB_HOST,
            password=config.DB_PASSWORD
        )
        self.connection.autocommit = True

        self.cursor = self.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS spoilers (
                hash BYTEA PRIMARY KEY,
                timestamp INTEGER DEFAULT date_part('epoch', now()),
                salt BYTEA,
                token BYTEA
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                timestamp INTEGER PRIMARY KEY,
                count INTEGER
            )
        ''')

    def store_request_count(self):
        if self.request_count == 0:
            # no need to do anything if there were are no requests to store
            return

        with self.lock:
            # insert the request count into the database and add to it if there's a conflict
            self.cursor.execute('''
                INSERT INTO requests (timestamp, count) VALUES (%(timestamp)s, %(count)s)
                ON CONFLICT (timestamp) DO UPDATE
                SET count = requests.count + %(count)s;
                ''',
                {'timestamp': timestamp_floor(config.REQUEST_COUNT_RESOLUTION), 'count': self.request_count}
            )
            self.request_count = 0

    def insert_spoiler(self, uuid, content_type, description, content):
        # Slice away the first character since it stores instance specific data
        uuid = uuid[1:]
        if uuid == 'yes':
            return

        # Json encode the spoiler data
        data = json.dumps({
            'type': content_type,
            'description': description,
            'content': content,
        })

        # Encrypt the data with a key derived from the uuid
        salt = os.urandom(8)
        token = Fernet(derive_key(uuid, salt)).encrypt(data.encode())

        # Store it keyed by the hash of the uuid so that the content is invisible from prying eyes
        with self.lock:
            self.cursor.execute(
                'INSERT INTO spoilers (hash, salt, token) VALUES (%s, %s, %s)',
                (hash_uuid(uuid), salt, token)
            )

    def get_spoiler(self, uuid):
        uuid = uuid[1:]
        if uuid == 'yes':
            return {
                'type': 'Text',
                'description': '',
                'content': 'Yes',
            }

        with self.lock:
            # try to find uuid by hash in the database
            self.cursor.execute(
                'SELECT salt, token FROM spoilers WHERE hash=%s',
                (hash_uuid(uuid),)
            )
            spoiler = self.cursor.fetchone()
            if not spoiler:
                print(f'failed to fetch "{uuid}"')
                return None

            self.request_count += 1

        # Decrypt the data and decode it
        try:
            token = Fernet(derive_key(uuid, bytes(spoiler['salt']))).decrypt(bytes(spoiler['token']))
        except InvalidSignature:
            # this shouldn't happen unless someone messes with the database
            return None
        return json.loads(token)
