from datetime import datetime
import json
import os
import time
import asyncio

from lib.mt5_lib import start_mt5
from lib.auto import Bot as mt_Bot
import MetaTrader5 as mt5


settings_file = "settings.json"

# Get a metaTrader Setting from 
def get_app_setting(filepath: str) -> dict:
  """
    Get the settings for MetaTrader5
    :param filepath the path of the file to get settings
    :return: dict Json object
  """

  # Check if file exist before processing the file
  if os.path.exists(filepath):
    if os.stat(filepath).st_size == 0: raise ImportError("Empty File")

    with open(filepath, "r") as file_content:
      return json.load(file_content)

  else: raise ImportError("The filepath you provided does not exist")


async def listen_for_input(stop_event):
    while True:
        user_input = await asyncio.get_event_loop().run_in_executor(None, input, "SMA running..., Enter 'exit' command to quit execution: ")
        
        if user_input == "exit":
            stop_event.set()  # Set the stop event to signal termination
            break  # Break out of the loop if the user enters "exit"



async def main():
    stop_event = asyncio.Event()

    # Initialize Bot
    bot = mt_Bot()

    # Listen for command from terminal to stop SMA
    task0 = asyncio.create_task(listen_for_input(stop_event))

    # Start SMA CrossOver
    task1 = asyncio.create_task(bot.trade(stop_event))

    # Candles Backtest
    start_dt = datetime(2022, 8, 1)
    # task2 = asyncio.create_task(bot.backtest_candles_3_in_row(start_dt))

    async def run_backtest():
      await bot.backtest_candles_3_in_row(start_dt, show_fig=True, setup=True)
    
    # Start the backtest task
    task2 = asyncio.create_task(run_backtest())

    await asyncio.gather(task1, task2, task0)

if __name__ == "__main__":

  app_settings = get_app_setting(filepath=settings_file)
  
  # establish connection to the MetaTrader 5 terminal
  if not start_mt5(**app_settings):
    print("initialize() failed, error code =",mt5.last_error())
    quit()


  print("MetaTrader Initialized Successfully")

  # strategy parameters
  # SYMBOL = "EURUSD"
  # VOLUME = 1.0
  # TIMEFRAME = mt5.TIMEFRAME_M1
  # SMA_PERIOD = 10
  # DEVIATION = 20

  # Run trade function asynchronously
  asyncio.run(main())
  