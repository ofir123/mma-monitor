from copy import deepcopy
import smtplib
import sys
import os
from email.mime.text import MIMEText

import requests_html
from guessit import guessit
import logbook
import ujson

from mma_monitor import config
from mma_monitor.shows import SHOWS_LIST

MMA_TORRENTS_BASE_URL = 'https://mma-torrents.com'

logger = logbook.Logger('MMATorrentsMonitor')


def _get_log_handlers():
    """
    Initializes all relevant log handlers.

    :return: A list of log handlers.
    """
    handlers = [
        logbook.StreamHandler(sys.stdout, level=logbook.INFO, bubble=True),
    ]
    if config.LOG_FILE_PATH:
        handlers.append(logbook.RotatingFileHandler(
            config.LOG_FILE_PATH, level=logbook.DEBUG, backup_count=1, max_size=5 * 1024 * 1024, bubble=True))
    return handlers


def _send_message(to_email, subject, content):
    server = None
    try:
        logger.info('Connecting to GMail...')
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(config.GMAIL_USERNAME, config.GMAIL_PASSWORD)

        logger.info(f'Sending email to {to_email}...')

        message = MIMEText(content.encode('utf8'), _charset='utf8')
        message['Subject'] = subject
        message['From'] = config.GMAIL_USERNAME
        message['To'] = to_email

        server.sendmail(config.GMAIL_USERNAME, [to_email], message.as_string())
    except:
        logger.exception('Failed to send email!')
    finally:
        if server:
            server.quit()


def _load_last_state(file_path):
    """
    Load last state from local JSON file.

    :param file_path: The JSON file path.
    :return: The map between show names and their last season and episode.
    """
    logger.info('Loading last state from: {}'.format(file_path))
    if not os.path.isfile(file_path):
        logger.info('File doesn\'t exist! Starting from scratch...')
        return {show: {'episode': -1, 'torrent': None} for show in SHOWS_LIST}
    return ujson.load(open(file_path, 'r', encoding='UTF-8'))


def _validate_show(show):
    """
    Make sure the show version is relevant.
    Accept only shows in 720p quality, with no title or the title "Preliminaries",
    and not from the "Ebi" release group.

    :param show: The show object to verify.
    :return: True if the show version is relevant, and False otherwise.
    """
    show_format = show.get('format', '').lower()
    episode_title = show.get('episode_title', '').lower()
    return show.get('screen_size') == '720p' and show_format == 'hdtv' and \
        (not episode_title or 'prelim' in episode_title and 'early' not in episode_title) and \
        show.get('release_group', '').lower() != 'ebi'


def check_today_torrents(last_state, session):
    """
    Check all new torrents from today, and create a filtered list of torrent URLs, based on last_state.

    :param last_state: A map between each show and the last reported episode for it.
    :param session: The current mma-torrents session.
    :return: A list of torrents to download.
    """
    logger.info('Checking today\'s torrents...')
    r = session.get(MMA_TORRENTS_BASE_URL + '/torrents-today.php')
    r.raise_for_status()
    if not r.content:
        logger.error('Got empty content from website! Skipping state update...')
        return last_state

    # Copy previous state and overwrite new stuff.
    new_state = deepcopy(last_state)

    for a in r.html.find('a'):
        href = a.attrs.get('href', '')
        title = a.attrs.get('title')

        if title and 'torrents-details.php' in href:
            # Check if the episode is new, and relevant.
            show = guessit(title)

            if _validate_show(show):
                episode_title = show.get('episode_title', '').lower()
                show_title = '{}{}'.format(
                    show.get('title', '').lower(), ' - {}'.format(episode_title) if episode_title else '')
                show_state = last_state.get(show_title)

                if show_state:
                    episode_number = show.get('season', 0) * 100 + show.get('episode', 0)

                    if show_state['episode'] < episode_number:
                        logger.info('New episode was found - {}: Episode {}'.format(show_title, episode_number))
                        torrent_id = href.split('id=')[1].split('&')[0]
                        new_state[show_title] = {
                            'episode': episode_number,
                            'torrent': f'https://mma-torrents.com/download.php?id={torrent_id}'
                        }
                    else:
                        logger.debug('Found an already existing episode - {}: Episode {}. Skipping...'.format(
                            show_title, episode_number))
    return new_state


def report(diff_state):
    """
    Send E-Mail report about new episodes.

    :param diff_state: A dict representing the diff from the last state.
    """
    logger.info('Creating E-Mail report...')
    # Create message text.
    new_episodes_text = ''
    for show_name, episode_details in sorted(diff_state.items()):
        new_episodes_text += '{}: Episode {}\r\n'.format(
            show_name.title().replace('Ufc', 'UFC'), episode_details['episode'])

    # Send messages.
    for to_address in config.EMAILS_LIST:
        _send_message(to_address, config.SUBJECT, new_episodes_text)


def download(diff_state, session):
    """
    Download new episode torrents.

    :param diff_state: A dict representing the diff from the last state.
    :param session: The current mma-torrents session.
    """
    logger.info('Download new torrents...')
    for show_name, episode_details in diff_state.items():
        torrent_response = session.get(episode_details['torrent'])
        if torrent_response.status_code == 200 and torrent_response.content:
            # Success! Save the new torrent file and update the state.
            file_name = '{}_{}'.format(show_name.replace(' ', '_'), episode_details['episode'])
            logger.info('Found torrent! File name: {}'.format(file_name))
            result_path = os.path.join(config.TORRENTS_DIRECTORY, file_name + '.torrent')
            open(result_path, 'wb').write(torrent_response.content)


def main():
    """
    Scans mma-torrents and downloads new episodes.
    """
    with logbook.NestedSetup(_get_log_handlers()).applicationbound():
        file_path = config.JSON_FILE_PATH or \
                    os.path.join(os.path.dirname(os.path.realpath(__file__)), 'last_state.json')
        last_state = _load_last_state(file_path)
        with requests_html.HTMLSession() as session:
            # Login to mma-torrents.
            r = session.post(MMA_TORRENTS_BASE_URL + '/account-login.php', data={
                'username': config.MMA_TORRENTS_USERNAME,
                'password': config.MMA_TORRENTS_PASSWORD
            })
            r.raise_for_status()

            new_state = check_today_torrents(last_state, session)
            # Create a diff state, for downloads and reporting.
            diff_state = {k: v for k, v in new_state.items() if v['episode'] > last_state[k]['episode']}

            if config.SHOULD_DOWNLOAD_TORRENTS and diff_state:
                download(diff_state, session)

            if config.SHOULD_SEND_REPORT and diff_state:
                report(diff_state)
            else:
                logger.info('Nothing to report - No mail was sent.')
        # Update state file.
        ujson.dump(new_state, open(file_path, 'w'), indent=4)
        logger.info('All done!')


if __name__ == '__main__':
    main()
