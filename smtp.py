import base64
import logging
import socket
import ssl

from mail import Mail

SMTP_SERVER = ('smtp.gmail.com', 465)


class SMTPException(Exception):
    pass


class SMTPTemporaryException(SMTPException):
    pass


class SMTPPermanentException(SMTPException):
    pass


class SMTPDisconnectedException(SMTPException):
    pass


class SMTPClient:
    def __init__(self, login, passwd, server=None, disable_ssl=False):
        self._server = SMTP_SERVER if server is None else server
        self._disable_ssl = disable_ssl
        self._sock_file = None
        self._login = login
        self._passwd = passwd
        self._connect()

    @property
    def server(self):
        return self._server

    def _connect(self):
        self._create_sock(self._server, self._disable_ssl)
        self._ehlo()
        self._auth_login(self._login, self._passwd)

    def _disconnect(self):
        self._socket.close()
        raise SMTPDisconnectedException('Server is not available')

    def _create_sock(self, server, disable_ssl):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(7)
        if not disable_ssl:
            self._socket = ssl.wrap_socket(self._socket,
                                           ssl_version=ssl.PROTOCOL_SSLv23)

        try:
            self._socket.connect(server)
        except socket.error:
            self._disconnect()

        self._recv_data(sock=self._socket)

    def _handle_response_code(self, code, resp):
        code_type = code // 100
        if code_type > 3:
            self._socket.close()
            exc = SMTPTemporaryException(resp) if code_type == 4 \
                else SMTPPermanentException(resp)
            raise exc

    def _recv_data(self, sock=None):
        sock = sock if sock is not None else self._socket
        if self._sock_file is None:
            self._sock_file = sock.makefile('rb')
        data = []
        while True:
            try:
                line = self._sock_file.readline()
            except OSError:
                self._disconnect()

            if not line:
                self._disconnect()

            data.append(line)
            if line[3:4] != b'-':
                break

        return b''.join(data)

    def _recv(self):
        try:
            data = self._recv_data()
        except socket.error:
            self._disconnect()

        try:
            code = int(data[:3])
        except ValueError:
            code = -1

        resp = data[4:].decode().strip()
        logging.debug(f'\nResponse\ncode: {code}\nmsg: {resp}')
        return code, resp

    def _send(self, message, to_base64=False):
        message = message.encode()
        if to_base64:
            message = base64.b64encode(message)
        message += b'\r\n'

        try:
            self._socket.sendall(message)
        except socket.error:
            self._disconnect()

    def _send_msg_to_server(self, message, to_base64=False, handle_resp=True):
        logging.debug(f"Request: '{message}'")

        self._send(message, to_base64=to_base64)
        if handle_resp:
            code, resp = self._recv()
            self._handle_response_code(code, resp)
            return code, resp

    def _ehlo(self):
        self._send_msg_to_server('EHLO owrld')

    def _auth_login(self, login, passwd):
        self._send_msg_to_server('AUTH LOGIN')
        self._send_msg_to_server(login, to_base64=True)
        self._send_msg_to_server(passwd, to_base64=True)

    def _mail_from(self):
        self._send_msg_to_server(f'MAIL FROM:<{self._login}>')

    def _rcpt_to(self, address):
        self._send_msg_to_server(f'RCPT TO:<{address}>')

    def _data(self, data):
        self._send_msg_to_server('DATA')
        self._send(data)
        self._send('.')
        self._recv()

    def close(self):
        self._send_msg_to_server('QUIT', handle_resp=False)
        self._socket.close()

    def send_mail(self, mail, bcc=None):
        self._mail_from()
        recipients = mail.recipients
        if bcc is not None:
            Mail.validate_emails(bcc)
            recipients.extend(bcc)

        for recipient in recipients:
            self._rcpt_to(recipient)
        self._data(str(mail))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
