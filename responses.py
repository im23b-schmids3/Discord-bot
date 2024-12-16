import datetime


def get_response(user_message):
    user_input = user_message.lower()

    if user_input == "!help" or user_input == "!commands":
        return "I can respond to the following commands:\n!help, !commands\n\n!hello\n!time"

    elif user_input == "!hello":
        return 'Hey'

    elif user_input == "!time":
        now = datetime.datetime.now()
        return f'The current time is {now.strftime("%d-%m-%Y %H:%M")}'

    else:
        pass
