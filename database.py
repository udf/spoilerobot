import base64
import json
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


def split_uuid(uuid):
    """
    Splits a uuid into a database key and encryption key by hashing it and
    then splitting the hash (the hash is needed because uuid can be of variable length)
    """
    digest = hashes.Hash(hashes.SHA512(), backend=default_backend())
    digest.update((uuid + config.HASH_PEPPER).encode())
    digest = digest.finalize()
    return digest[:32], base64.urlsafe_b64encode(digest[32:])


class Database:
    def __init__(self):
        self.request_count = 0
        # we need a lock to prevent double counting (or forgetting) requests
        self.request_lock = threading.Lock()
        self.connect()
        self.banned_users = self.get_banned_users()

    # utility methods
    def connect(self):
        self.connection = psycopg2.connect(
            dbname=config.DB_NAME,
            user=config.DB_USERNAME,
            host=config.DB_HOST,
            password=config.DB_PASSWORD
        )
        self.connection.autocommit = True

        cursor = self.get_cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS spoilers_v2 (
                hash BYTEA PRIMARY KEY,
                timestamp INTEGER DEFAULT date_part('epoch', now()),
                token BYTEA,
                owner INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requests (
                timestamp INTEGER PRIMARY KEY,
                count INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                expires INTEGER
            )
        ''')

    def get_cursor(self, use_dict_factory=True):
        #TODO Reconnect if connection dropped?
        return self.connection.cursor(
            cursor_factory=psycopg2.extras.DictCursor if use_dict_factory else None
        )

    def forget_old_owners(self, forget_time):
        cursor = self.get_cursor()
        cursor.execute(
            'UPDATE spoilers_v2 SET owner = 0 WHERE timestamp <= %s AND owner > 0;',
            (time.time() - forget_time,)
        )
        return cursor.rowcount

    # banned user management
    def get_banned_users(self):
        cursor = self.get_cursor()
        cursor.execute('SELECT * FROM banned_users;')
        results = cursor.fetchall()
        banned_users = {}
        for result in results:
            banned_users[int(result['user_id'])] = int(result['expires'])
        return banned_users

    def ban_user(self, user_id, expires):
        cursor = self.get_cursor()
        cursor.execute('''
            INSERT INTO banned_users (user_id, expires) VALUES (%(user_id)s, %(expires)s)
            ON CONFLICT (user_id) DO UPDATE
            SET expires = %(expires)s;
            ''',
            {'user_id': user_id, 'expires': expires}
        )
        cursor.execute(
            'DELETE from spoilers_v2 WHERE owner = %s;',
            (user_id,)
        )
        self.banned_users[user_id] = expires
        return cursor.rowcount

    def is_user_banned(self, user_id):
        user_id = int(user_id)
        if user_id not in self.banned_users:
            return False

        if time.time() < self.banned_users[user_id]:
            return True

        self.remove_banned_user(user_id)
        return False

    def remove_banned_user(self, user_id):
        user_id = int(user_id)
        if user_id not in self.banned_users:
            return False

        del self.banned_users[user_id]
        self.get_cursor().execute(
            'DELETE FROM banned_users WHERE user_id=%s',
            (user_id,)
        )
        return True

    # statistics
    def store_request_count(self):
        with self.request_lock:
            request_count = self.request_count
            self.request_count = 0

        if request_count == 0:
            # no need to do anything if there were are no requests to store
            return

        cursor = self.get_cursor()
        # insert the request count into the database and add to it if there's a conflict
        cursor.execute('''
            INSERT INTO requests (timestamp, count) VALUES (%(timestamp)s, %(count)s)
            ON CONFLICT (timestamp) DO UPDATE
            SET count = requests.count + %(count)s;
            ''',
            {'timestamp': timestamp_floor(config.REQUEST_COUNT_RESOLUTION), 'count': request_count}
        )

    # spoiler management
    def insert_spoiler(self, uuid, content_type, description, content, owner):
        # Slice away the first character since it stores instance specific data
        uuid = uuid[1:]
        if uuid == 'yes':
            return

        # Json encode the spoiler data
        data = json.dumps({
            'type': content_type,
            'description': description,
            'content': content,
        }).encode()

        # Encrypt the data with a key derived from the uuid
        db_hash, key = split_uuid(uuid)
        token = Fernet(key).encrypt(data)

        # Store it keyed by the first part of the hash of the uuid
        cursor = self.get_cursor()
        cursor.execute(
            'INSERT INTO spoilers_v2 (hash, token, owner) VALUES (%s, %s, %s)',
            (db_hash, token, owner)
        )

    def _spoiler_convert_v1_v2(self, old_hash, uuid, data, timestamp):
        # Takes a spoiler data+timestamp and inserts it into the v2 table
        db_hash, key = split_uuid(uuid)
        token = Fernet(key).encrypt(data)

        cursor = self.get_cursor()
        cursor.execute(
            'INSERT INTO spoilers_v2 (timestamp, hash, token, owner) VALUES (%s, %s, %s, %s)',
            (timestamp, db_hash, token, 0)
        )
        cursor.execute(
            'DELETE FROM spoilers WHERE hash=%s',
            (old_hash,)
        )

    def get_spoiler_v1(self, uuid, increment_stats=True):
        """
        Tries to get a spoiler from the old (v1) schema
        If found it is inserted into the new (v2) schema
        """
        # try to find uuid by hash in the database
        db_hash = hash_uuid(uuid)
        cursor = self.get_cursor()
        cursor.execute(
            'SELECT timestamp, salt, token FROM spoilers WHERE hash=%s',
            (db_hash,)
        )
        spoiler = cursor.fetchone()

        if not spoiler:
            return None
            
        if increment_stats:
            with self.request_lock:
                self.request_count += 1

        # Decrypt the data and decode it
        try:
            data = Fernet(derive_key(uuid, bytes(spoiler['salt']))).decrypt(bytes(spoiler['token']))
        except InvalidSignature:
            # this shouldn't happen unless someone messes with the database
            return None

        # move it to the new schema
        self._spoiler_convert_v1_v2(db_hash, uuid, data, spoiler['timestamp'])

        return json.loads(data)

    def get_spoiler(self, uuid, increment_stats=True):
        uuid = uuid[1:]
        if not uuid:
            return None
            
        if uuid == 'yes':
            return {
                'type': 'Text',
                'description': '',
                'content': 'Yes',
            }

        db_hash, key = split_uuid(uuid)

        # try to find uuid by hash in the database
        cursor = self.get_cursor()
        cursor.execute(
            'SELECT token FROM spoilers_v2 WHERE hash=%s',
            (db_hash,)
        )
        spoiler = cursor.fetchone()

        if not spoiler:
            return self.get_spoiler_v1(uuid)

        if increment_stats:
            with self.request_lock:
                self.request_count += 1

        # Decrypt the data and decode it
        try:
            data = Fernet(key).decrypt(bytes(spoiler['token']))
        except InvalidSignature:
            # this shouldn't happen unless someone messes with the database
            return None
        return json.loads(data)
