# spoilerobot
The source code for the Spoiler-o-bot, a Telegram spoiler creation bot
You can try it out by typing @spoilerobot (inline) in Telegram


# Usage
- Setup [PostgreSQL](https://www.postgresql.org/) on your system  
- Create a user and database for the bot by becoming the postgres user and executing

      $ createuser spoilerobot
      $ createdb spoilerobot -U spoilerobot
      $ psql -U spoilerobot
      spoilerobot=> \password
      [enter a password for the bot's database user]

- Store this password in the `tg_bot_spoilero_db_pwd` environmental variable (or modify `config.py`)
- Install dependencies with `pip install python-telegram-bot validators cryptography psycopg2`
- Run the script and follow the instructions on creating your unique pepper (note that your pepper should remain the same for each instance of the bot and database)

- You can now run it with `tg_bot_spoilero=TOKEN python spoilerobot.py`