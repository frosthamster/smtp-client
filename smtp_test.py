import sys

if sys.version_info[:2] < (3, 6):
    print('This code need Python 3.6 or higher')
    sys.exit(10)

import base64
import tempfile
import textwrap
import unittest
from ssl import SSLSocket
from unittest.mock import patch
import re
from os import path
from mail import Mail, EmailValidationException, build_emails, \
    get_attachments_content
from smtp import SMTPClient, SMTPPermanentException

test_mail = 'test@gmail.com'
test_pwd = 'pwd'
BOUNDARY_RE = re.compile(r'boundary="(=+\d+==)"')
DEFAULT_RESPONSES = {b'EHLO owrld\r\n': b'250 ok',
                     b'AUTH LOGIN\r\n': b'334 ok',
                     base64.b64encode(test_mail.encode()) + b'\r\n': b'334 ok',
                     base64.b64encode(test_pwd.encode()) + b'\r\n': b'335 ok',
                     b'QUIT\r\n': b'221 closing'}


class MockSocketFile:
    def readline(self, *args, **kw):
        return Tests.mock_recv(None, None)


@patch.object(SSLSocket, 'connect', lambda *args, **kw: None)
@patch.object(SSLSocket, 'sendall', lambda *args: Tests.mock_send(*args))
@patch.object(SSLSocket, 'recv', lambda *args: Tests.mock_recv(*args))
@patch.object(SSLSocket, 'makefile', lambda e, *args: MockSocketFile())
class Tests(unittest.TestCase):
    responses = {}
    requests = []
    current_requests = []

    def setUp(self):
        Tests.responses = DEFAULT_RESPONSES
        Tests.current_requests = []
        Tests.requests = []

    @staticmethod
    def get_requests(additional_requests=None):
        standard_requests = [b'EHLO owrld\r\n',
                             b'AUTH LOGIN\r\n',
                             base64.b64encode(test_mail.encode()) + b'\r\n',
                             base64.b64encode(test_pwd.encode()) + b'\r\n']
        if additional_requests is not None:
            standard_requests.extend(additional_requests)
        standard_requests.append(b'QUIT\r\n')
        return standard_requests

    @staticmethod
    def mock_send(mock_obj, data):
        Tests.requests.append(data)
        Tests.current_requests.append(data)

    @staticmethod
    def mock_recv(mock_obj, length):
        if len(Tests.current_requests) == 0:
            return b'500 err'
        req = Tests.current_requests.pop()

        if req in Tests.responses:
            return Tests.responses[req]
        return b'500 err'

    def test_connected_to_server(self):
        with SMTPClient(test_mail, test_pwd):
            pass
        self.assertListEqual(self.requests, self.get_requests())

    def test_not_connected_to_server(self):
        with self.assertRaises(SMTPPermanentException):
            SMTPClient(test_mail, test_pwd + '!')

    def test_mail_validation(self):
        with self.assertRaises(EmailValidationException):
            Mail('sender@@gmail.com', [], 'subject', message='test msg')
        with self.assertRaises(EmailValidationException):
            Mail('sender@gmail.com', ['wrong mail'], 'subject',
                 message='test msg')

    def test_mail_format(self):
        message = 'test msg\nline2\n.'
        file_content = 'file content'

        with tempfile.TemporaryDirectory() as dir:
            with open(path.join(dir, 'tmpfile'), mode='w') as file:
                file.write(file_content)
                file.close()

                mail = Mail('sender@gmail.com',
                            ['rec1@gmail.com', 'rec2@gmail.com'],
                            'subject', message=message,
                            attachments=get_attachments_content([file.name]))
        mail = str(mail)
        delimiter = BOUNDARY_RE.search(mail).group(1)

        message = base64.b64encode(message.encode()).decode()
        file_content = base64.b64encode(file_content.encode()).decode()

        valid_mail = textwrap.dedent("""\
                    Content-Type: multipart/mixed; boundary="{}"
                    MIME-Version: 1.0
                    Subject: subject
                    From: sender@gmail.com
                    To: rec1@gmail.com, rec2@gmail.com
                    
                    --{}
                    Content-Type: text/plain; charset="utf-8"
                    MIME-Version: 1.0
                    Content-Transfer-Encoding: base64
                    
                    {}
                    
                    --{}
                    Content-Type: application/octet-stream
                    MIME-Version: 1.0
                    Content-Transfer-Encoding: base64
                    Content-Disposition: attachment; filename="tmpfile"
                    
                    {}
                    
                    --{}--
                    """.format(delimiter, delimiter, message, delimiter,
                               file_content, delimiter))
        self.assertEqual(valid_mail, mail)

    def test_splits_mails(self):
        def get_suffix(curr_block, block_count):
            return '<p><i>{} of {} ' \
                   'attachment block</i></p>'.format(curr_block, block_count)

        recipients = ['r@g.com']
        msg = 'msg'

        self.maxDiff = None
        with tempfile.TemporaryDirectory() as dir:
            with open(path.join(dir, 'tmpfile'), mode='wb') as f1, open(
                    path.join(dir, 'tmpfile2'), mode='wb') as f2:
                f1.write(b'\0' * (1024 ** 2) * 2)
                f2.write(b'\0' * (1024 ** 2) * 2)
                f1.close()
                f2.close()

                mails = build_emails(test_mail, recipients, 'subj', msg,
                                     [f1.name, f2.name],
                                     max_attach_size=3)
                mails = list(map(lambda e: str(e), mails))

                mail1 = Mail(test_mail, recipients, 'subj', message=msg,
                             attachments=get_attachments_content([f1.name]))
                mail1.attach_text(get_suffix(1, 2), enable_html=True)

                mail2 = Mail(test_mail, recipients, 'subj',
                             attachments=get_attachments_content([f2.name]))
                mail2.attach_text(get_suffix(2, 2), enable_html=True)
                mail1 = str(mail1)
                mail2 = str(mail2)
                boundary1 = BOUNDARY_RE.search(mail1).group(1)
                boundary2 = BOUNDARY_RE.search(mail2).group(1)
                boundary_repl1 = BOUNDARY_RE.search(mails[0]).group(1)
                boundary_repl2 = BOUNDARY_RE.search(mails[1]).group(1)
                mail1 = mail1.replace(boundary1, boundary_repl1)
                mail2 = mail2.replace(boundary2, boundary_repl2)

                valid_mails = [mail1, mail2]
                self.assertListEqual(mails, valid_mails)

    def test_send_mail(self):
        message = 'msg\nline2\n.\n'
        recipients = ['r1@gmail.com', 'r2@gmail.com']

        Tests.responses[
            'MAIL FROM:<{}>\r\n'.format(test_mail).encode()] = b'250 ok'
        Tests.responses[b'.\r\n'] = b'250 ok'
        Tests.responses[b'DATA\r\n'] = b'250 ok'

        valid_requests = ['MAIL FROM:<{}>\r\n'.format(test_mail).encode()]
        for recipient in recipients:
            rcpt_to = 'RCPT TO:<{}>\r\n'.format(recipient).encode()
            Tests.responses[rcpt_to] = b'250 ok'
            valid_requests.append(rcpt_to)

        mail = Mail(test_mail, recipients, 'subject', message=message)
        with SMTPClient(test_mail, test_pwd) as smtp:
            smtp.send_mail(mail)

        valid_requests.extend([
            b'DATA\r\n',
            str(mail).encode() + b'\r\n',
            b'.\r\n'])

        self.assertListEqual(self.requests, self.get_requests(valid_requests))


if __name__ == '__main__':
    unittest.main()
