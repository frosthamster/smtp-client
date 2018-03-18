import base64
import mimetypes
import re
import string
import textwrap
from os import path
from random import choices


class EmailValidationException(ValueError):
    pass


class AttachmentException(ValueError):
    pass


def get_size(content):
    return len(content) / (1024 ** 2)


def get_attachments_content(attachments, decode=True):
    if attachments is None:
        return
    result = []
    for attachment in attachments:
        with open(attachment, 'rb') as file:
            content = file.read()
        content = base64.b64encode(content)
        if decode:
            content = content.decode()
        result.append((attachment, content))

    return result


def build_emails(sender, recipients, subject, message, attachments=None,
                 enable_html=False, max_attach_size=None):
    if max_attach_size is None:
        return [Mail(sender, recipients, subject, message=message,
                     attachments=get_attachments_content(attachments),
                     enable_html=enable_html)]
    result = []
    attach_blocks = []
    attachments_sizes = []

    attachments_content = get_attachments_content(attachments, decode=False)
    for attachment, content in attachments_content:
        size = get_size(content)
        if size > max_attach_size:
            raise AttachmentException(f'Attachment too big: {attachment}')

        attachments_sizes.append((size, (attachment, content.decode())))
    attachments_sizes = sorted(attachments_sizes)

    current_block = []
    current_size = 0
    for size, attachment_info in attachments_sizes:
        if current_size + size > max_attach_size:
            attach_blocks.append(current_block)
            current_block = []
            current_size = 0

        current_size += size
        current_block.append(attachment_info)
    if len(current_block) > 0:
        attach_blocks.append(current_block)

    for i, block in enumerate(attach_blocks):
        suffix = f'<p><i>{i+1} of {len(attach_blocks)} ' \
                 'attachment block</i></p>'
        if i == 0:
            mail = Mail(sender, recipients, subject, message=message,
                        attachments=block, enable_html=enable_html)
        else:
            mail = Mail(sender, recipients, subject, attachments=block)

        mail.attach_text(suffix, enable_html=True)
        result.append(mail)

    return result


class Mail:
    DELIMITER = ', '
    EMAIL_REGEX = re.compile(
        r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")

    def __init__(self, sender, recipients, subject, message=None,
                 attachments=None, enable_html=False,
                 boundary=None):
        self._mail = ''
        self._sender = sender
        self._recipients = recipients
        self.validate_emails([sender, *recipients])

        self._boundary = boundary
        if boundary is None:
            self._boundary = self._generate_boundary()

        additional_fields = textwrap.dedent(f'''\
                                Subject: {subject}
                                From: {self._sender}
                                To: {self.DELIMITER.join(recipients)}
                                ''')
        self._attach_block(f'multipart/mixed; boundary="{self._boundary}"',
                           additional_fields=additional_fields,
                           add_boundary=False)

        if message is not None:
            self.attach_text(message, enable_html=enable_html)

        if attachments is not None:
            for filename, content in attachments:
                ctype, encoding = mimetypes.guess_type(filename)
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"

                filename = path.basename(filename)
                additional_fields = textwrap.dedent(f'''\
                    Content-Transfer-Encoding: base64
                    Content-Disposition: attachment; filename="{filename}"
                    ''')

                self._attach_block(ctype, body=content,
                                   additional_fields=additional_fields)

    @staticmethod
    def _generate_boundary():
        random_numbers = ''.join(choices(string.digits, k=19))
        return f'==============={random_numbers}=='

    def _attach_block(self, content_type,
                      mime_version='1.0', additional_fields=None,
                      body=None, add_boundary=True):
        if add_boundary:
            self._mail += textwrap.dedent(f'''\
                                    
                                    --{self._boundary}
                                    ''')

        self._mail += textwrap.dedent(f'''\
                        Content-Type: {content_type}
                        MIME-Version: {mime_version}
                        ''')
        if additional_fields is not None:
            self._mail += additional_fields
        if body is not None:
            self._mail += textwrap.dedent(f'''\
                            
                            {body}
                            ''')

    def attach_text(self, text, enable_html=False):
        text_type = 'html' if enable_html else 'plain'
        text = base64.b64encode(text.encode()).decode()
        transfer_enc = textwrap.dedent('''\
                        Content-Transfer-Encoding: base64
                        ''')

        self._attach_block(f'text/{text_type}; charset="utf-8"', body=text,
                           additional_fields=transfer_enc)

    @staticmethod
    def validate_emails(emails):
        for mail in emails:
            if not Mail.EMAIL_REGEX.match(mail):
                raise EmailValidationException(f'Incorrect email: {mail}')

    @property
    def recipients(self):
        return self._recipients

    @property
    def sender(self):
        return self._sender

    def __str__(self):
        return self._mail + f'\n--{self._boundary}--\n'
