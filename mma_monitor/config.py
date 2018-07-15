import os

# E-Mail settings.

# GMail account to send from.
GMAIL_USERNAME = 'myuser@gmail.com'
GMAIL_PASSWORD = 'mypassword'
# Add all relevant E-Mail addresses to this list.
EMAILS_LIST = ['example@email.com']

# mma-torrents settings.

# mma-torrents account details to download with.
MMA_TORRENTS_USERNAME = 'username'
MMA_TORRENTS_PASSWORD = 'password'

# General settings.

# If True, E-Mail reports will be sent.
SHOULD_SEND_REPORT = True
# If True, new episode torrents will be downloaded from mma-torrents.
SHOULD_DOWNLOAD_TORRENTS = True
# The directory to save downloaded torrent files in.
TORRENTS_DIRECTORY = r'C:\Temp\Torrents' if os.name == 'nt' else '/tmp/torrents'
# Log file path. If None, no log file will be created.
LOG_FILE_PATH = None
# JSON file path. If None, JSON will be created next to the script file.
JSON_FILE_PATH = None
