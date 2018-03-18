from smtp import SMTPClient, SMTPDisconnectedException
import logging


class SMTPConnection:
    def __init__(self, reconnection_count, login, passwd, server,
                 disble_ssl):
        self._reconnection_count = reconnection_count
        self._smtp_client_kwargs = {'login': login,
                                    'passwd': passwd,
                                    'server': server,
                                    'disable_ssl': disble_ssl}

    def create_connection(self):
        logging.info("Connecting to server")
        while self._reconnection_count > 0:
            try:
                return SMTPClient(**self._smtp_client_kwargs)
            except SMTPDisconnectedException:
                logging.info(
                    f"Try reconnecting to server ({self._reconnection_count}"
                    " attempts left)")
                self._reconnection_count -= 1
