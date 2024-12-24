import datetime
import requests
from dotenv import load_dotenv
import os

load_dotenv()


class Response:
    def __init__(self):
        self.user_input = {
            '!help': self.help,
            '!hello': self.hello,
            '!time': self.time,
            '!date': self.date,
            '!weather': self.weather,
        }

        self.api_key = os.getenv('WEATHER_API_KEY')
        self.base_url = "http://api.openweathermap.org/data/2.5/weather?"

    def get_response(self, user_message):
        func = self.user_input.get(user_message.split()[0].lower())
        if func:
            if user_message.split()[0].lower() == "!weather":
                return func(user_message)
            else:
                return func()
        else:
            return "Command not recognized. Type !help for a list of commands."

    def help(self):
        return 'I can respond to the following commands:\n!help\n!hello\n!time\n!date\n!weather [city]'

    def hello(self):
        return 'Hey'

    def time(self):
        now = datetime.datetime.now()
        return f'The current time is {now.strftime("%H:%M:%S")}'

    def date(self):
        now = datetime.datetime.now()
        return f'The current date is {now.strftime("%d-%m-%Y")}'

    def weather(self, user_message):
        parts = user_message.split(' ', 1)
        if len(parts) == 1:
            return "Please provide a city name for !weather."
        city_name = parts[1]
        complete_url = f"{self.base_url}appid={self.api_key}&q={city_name}&units=metric"
        response = requests.get(complete_url)
        data = response.json()
        if data.get("cod") == 200:
            temp = round(data["main"]["temp"], 1)
            description = data["weather"][0]["description"]
            return f"The weather in {city_name.title()}: {description} with {temp}°C."
        else:
            return f"City {city_name.title()} not found."
