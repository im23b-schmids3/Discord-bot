import datetime


class Response:
    def __init__(self):
        self.user_input = {
            '!help': self.help,
            '!hello': self.hello,
            '!time': self.time,
            '!date': self.date,
        }

    def get_response(self, user_message):
        func = self.user_input.get(user_message.lower())
        if func:
            return func()
        else:
            return 'Command not recognized. Type !help for a list of commands.'

    def help(self):
        return 'I can respond to the following commands:\n!help\n\n!hello\n!time\n!date'

    def hello(self):
        return 'Hey'

    def time(self):
        now = datetime.datetime.now()
        return f'The current time is {now.strftime("%H:%M:%S")}'

    def date(self):
        now = datetime.datetime.now()
        return f'The current date is {now.strftime("%d-%m-%Y")}'
