import datetime
import requests
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()


class Response:
    """
    A class to handle user commands and generate appropriate responses.

    Commands:
    - !help: Lists all available commands.
    - !hello: Sends a greeting.
    - !time: Returns the current time.
    - !date: Returns the current date.
    - !weather [city]: Provides weather information for the specified city.
    """

    def __init__(self):
        # Map commands to their corresponding methods
        self.user_input = {
            '!help': self.help,
            '!hello': self.hello,
            '!time': self.time,
            '!date': self.date,
            '!weather': self.weather,
        }

        # Retrieve the weather API key from environment variables
        self.api_key = os.getenv('WEATHER_API_KEY')
        # Base URL for the OpenWeather API
        self.base_url = "https://api.openweathermap.org/data/2.5/weather?"

    def get_response(self, user_message):
        """
        Determines the appropriate response based on the user's message.

        Parameters:
        - user_message (str): The user's input message.

        Returns:
        - str: The response to the user's command.
        """
        func = self.user_input.get(user_message.split()[0].lower())
        if func:
            # If the command is !weather, pass the full message
            if user_message.split()[0].lower() == "!weather":
                return func(user_message)
            else:
                return func()  # Execute the function for other commands
        else:
            return "Command not recognized. Type !help for a list of commands."

    def help(self):
        """
        Provides a list of available commands.

        Returns:
        - str: Help message listing commands.
        """
        return 'I can respond to the following commands:\n!help\n!hello\n!time\n!date\n!weather [city]'

    def hello(self):
        """
        Responds with a greeting.

        Returns:
        - str: Greeting message.
        """
        return 'Hey'

    def time(self):
        """
        Provides the current time.

        Returns:
        - str: Current time in HH:MM:SS format.
        """
        now = datetime.datetime.now()
        return f'The current time is {now.strftime("%H:%M:%S")}'

    def date(self):
        """
        Provides the current date.

        Returns:
        - str: Current date in DD-MM-YYYY format.
        """
        now = datetime.datetime.now()
        return f'The current date is {now.strftime("%d-%m-%Y")}'

    def weather(self, user_message):
        """
        Provides weather information for a specified city.

        Parameters:
        - user_message (str): The user's message containing the city name.

        Returns:
        - str: Weather information for the specified city or an error message.
        """
        # Extract the city name from the user's message
        parts = user_message.split(' ', 1)
        if len(parts) == 1:
            return "Please provide a city name for !weather."
        city_name = parts[1]

        # Build the API request URL
        complete_url = f"{self.base_url}appid={self.api_key}&q={city_name}&units=metric"
        response = requests.get(complete_url)
        data = response.json()

        # Check if the city is found and respond accordingly
        if data.get("cod") == 200:
            temp = round(data["main"]["temp"], 1)
            description = data["weather"][0]["description"]
            return f"The weather in {city_name.title()}: {description} with {temp}°C."
        else:
            return f"City {city_name.title()} not found."
