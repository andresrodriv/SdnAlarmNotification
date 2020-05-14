"""
Copyright (c) Emanuele Gallone 05-2020.
Author Emanuele Gallone

"""

import mail_sender_service
import telegram_bot_service
from config_manager import ConfigManager


class NotificationManager(object):

    def __init__(self):
        self.config_manager = ConfigManager()

    def notify(self, msg="DEBUG FROM NOTIFICATION MANAGER!"):
        self._send_mail(msg)
        self._broadcast_alarm(msg)

    def _send_mail(self, msg):
        send_email_flag = self.config_manager.get_notification_params()['Send_email']

        if send_email_flag:
            mail_sender_service.send_mail(msg)

    def _broadcast_alarm(self, msg):
        send_message_flag = self.config_manager.get_notification_params()['Send_message']

        if send_message_flag:
            telegram_bot_service.send_to_bot_group(msg)


if __name__ == '__main__':
    notification_m = NotificationManager()
