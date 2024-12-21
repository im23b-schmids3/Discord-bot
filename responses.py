import datetime


def get_response(user_message):
    user_input = {
        '!help': help,
        '!hello': hello,
        '!time': time,
        '!date': date,
        "!test": test,
    }
    func = user_input.get(user_message.lower())
    if func:
        return func()
    return "Command not recognized. Type !help for a list of commands."


def help():
    return 'I can respond to the following commands:\n!help\n\n!hello\n!time\n!date'


def hello():
    return 'Hey'


def time():
    now = datetime.datetime.now()
    return f'The current time is {now.strftime("%H:%M:%S")}'


def date():
    now = datetime.datetime.now()
    return f'The current date is {now.strftime("%d-%m-%Y")}'


def test():
    return 'Testing file'
