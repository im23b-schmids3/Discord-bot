import datetime


def get_response(user_message):
    sigma = user_message.lower()

    if sigma == "!hello":
        return 'Hey'

    elif sigma == "!time":
        now = datetime.datetime.now()
        return f'The current time is {now.strftime("%d-%m-%Y %H:%M")}'

    else:
        pass
