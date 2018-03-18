import sys

if sys.version_info[:2] < (3, 6):
    print('This code need Python 3.6 or higher')
    sys.exit(10)

import argparse
import logging
from getpass import getpass
from smtp import SMTPException, SMTPDisconnectedException
from mail import EmailValidationException, build_emails, AttachmentException
from os import path
from smtpConnection import SMTPConnection


def get_msg_from_file(msg_path):
    if path.isfile(msg_path):
        with open(msg_path) as file:
            msg_path = file.read()
    else:
        logging.critical('Not found message file: {}'.format(msg_path))
        sys.exit(4)
    return msg_path


def parse_args():
    main_parser = argparse.ArgumentParser(description='SMTP client')
    required_named = main_parser.add_argument_group('required arguments')
    required_named.add_argument('-l', '--login', type=str, required=True)
    required_named.add_argument('-r', '--recipients', type=str, nargs='+',
                                required=True)

    main_parser.add_argument('-m', '--message', type=str,
                             help='path to message file '
                                  '(if not specified read'
                                  ' message from stdin until EOF)')
    main_parser.add_argument('-s', '--subject', type=str, default='')
    main_parser.add_argument('-as', '--maxattachsize', type=int,
                             help='splits attachments into several emails'
                                  ' with the maximum size in MiB')
    main_parser.add_argument('-bcc', type=str, nargs='+',
                             help='hidden recipients')
    main_parser.add_argument('-a', '--attachments', type=str, nargs='+',
                             help='paths to attachments')
    main_parser.add_argument('--server', type=str,
                             help="smtp server in format 'host[:port]'")
    main_parser.add_argument('--sender', type=str,
                             help='return address')
    main_parser.add_argument('--password', type=str)
    main_parser.add_argument('--debug', action='store_true',
                             help='show debug info')
    main_parser.add_argument('--silent', action='store_true',
                             help='disable logging')
    main_parser.add_argument('--nossl', action='store_true',
                             help='disable ssl')
    main_parser.add_argument('-eh', action='store_true',
                             help='enable html support')
    main_parser.add_argument('-rc', type=int, default=2,
                             help='reconnection count')
    return main_parser.parse_args()


def set_logging_level(args):
    log_level = logging.INFO
    if args.silent:
        log_level = logging.WARNING
    if args.debug:
        log_level = logging.DEBUG
    logging.basicConfig(format='%(levelname)s: %(message)s\n',
                        level=log_level)


def get_passwd(args):
    passwd = args.password
    if passwd is None:
        passwd = getpass()
    return passwd


def get_message(args):
    logging.info('Reading message (ctrl+D to stop)')
    if args.message is not None:
        message = get_msg_from_file(args.message)
    else:
        message = sys.stdin.read()
    return message


def check_attachments_paths(args):
    if args.attachments is not None:
        for attach in args.attachments:
            if not path.isfile(attach):
                logging.critical('Not found attachment: {}'.format(attach))
                sys.exit(4)


def get_sender(args):
    args.login = args.login.lower()
    sender = args.login
    if args.sender is not None:
        sender = args.sender.lower()
    return sender


def get_mails(sender, message, args):
    try:
        mails = build_emails(sender, args.recipients, args.subject,
                             message,
                             enable_html=args.eh, attachments=args.attachments,
                             max_attach_size=args.maxattachsize)
    except (EmailValidationException, AttachmentException) as e:
        logging.critical(e)
        sys.exit(1)
    mails.reverse()
    return mails


def get_server(args):
    server = args.server
    if server is not None:
        if args.server.find(':') != -1:
            host, port = args.server.split(':')
        else:
            host = args.server
            port = 25 if args.nossl else 465
        server = host, int(port)
    return server


def main():
    args = parse_args()
    set_logging_level(args)
    passwd = get_passwd(args)
    message = get_message(args)
    check_attachments_paths(args)
    sender = get_sender(args)
    mails = get_mails(sender, message, args)
    server = get_server(args)

    logging.info('Sending message')
    conn = SMTPConnection(args.rc + 1, args.login, passwd, server, args.nossl)
    try:
        smtp = conn.create_connection()
        while mails:
            if smtp is None:
                logging.critical('Server is not available')
                sys.exit(3)
            try:
                with smtp:
                    smtp.send_mail(mails[-1], bcc=args.bcc)
                    mails.pop()
            except SMTPDisconnectedException:
                smtp = conn.create_connection()
    except SMTPException as e:
        logging.critical(e)
        sys.exit(2)
    logging.info('Successfully send mail')


if __name__ == '__main__':
    main()
