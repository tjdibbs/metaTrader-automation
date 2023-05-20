import asyncio
import sys
import MetaTrader5 as mt5
import time
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from IPython.display import display



class Bot:
    fig = None
    df = None

    def __init__(self,
                 symbol="EURUSD",
                 volume=1.0,
                 timeframe=mt5.TIMEFRAME_D1,
                 sma_period=10,
                 deviation=20):
        self.start = False
        self.SYMBOL = symbol
        self.TIMEFRAME = timeframe
        self.SMA_PERIOD = sma_period
        self.VOLUME = volume
        self.DEVIATION = deviation

    async def market_order(self, symbol, volume, order_type, **kwargs):
        tick = mt5.symbol_info_tick(symbol)

        order_dict = {'buy': 0, 'sell': 1}
        price_dict = {'buy': tick.ask, 'sell': tick.bid}

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_dict[order_type],
            "price": price_dict[order_type],
            "deviation": self.DEVIATION,
            "magic": 100,
            "comment": "python market order",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        order_result = mt5.order_send(request)

        return order_result

    async def close_order(self, ticket, deviation: int):
        positions = mt5.positions_get()

        for pos in positions:
            tick = mt5.symbol_info_tick(pos.symbol)
            type_dict = {
                0: 1,
                1: 0
            }  # 0 represents buy, 1 represents sell - inverting order_type to close the position
            price_dict = {0: tick.ask, 1: tick.bid}

            if pos.ticket == ticket:
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "position": pos.ticket,
                    "symbol": pos.symbol,
                    "volume": pos.volume,
                    "type": type_dict[pos.type],
                    "price": price_dict[pos.type],
                    "deviation": deviation,
                    "magic": 100,
                    "comment": "python close order",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }

                order_result = mt5.order_send(request)
                return order_result

        return 'Ticket does not exist'

    def get_exposure(self, symbol):
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            pos_df = pd.DataFrame(positions,
                                  columns=positions[0]._asdict().keys())
            exposure = pos_df['volume'].sum()
            return exposure

    def signal(self, symbol, timeframe, sma_period):
        bars = mt5.copy_rates_from_pos(symbol, timeframe, 1, sma_period)
        bars_df = pd.DataFrame(bars)

        last_close = bars_df.iloc[-1].close
        sma = bars_df.close.mean()

        direction = 'flat'
        if last_close > sma:
            direction = 'buy'
        elif last_close < sma:
            direction = 'sell'

        return last_close, sma, direction

    async def trade(self, stop_event=None):

        if not stop_event: return

        while not stop_event.is_set():
            # calculating account exposure
            exposure = self.get_exposure(self.SYMBOL)

            # calculating last candle close, simple moving average, and checking for trading signals
            last_close, sma, direction = self.signal(self.SYMBOL,
                                                     self.TIMEFRAME,
                                                     self.SMA_PERIOD)

            # trading logic
            if direction == 'buy':
                # if we have a BUY signal, close all short positions
                for pos in mt5.positions_get():
                    if pos.type == 1:  # pos.type == 1 represents a sell order
                        await self.close_order(pos.ticket, self.DEVIATION)

                # if there are no open positions, open a new long position
                if not mt5.positions_total():
                    await self.market_order(self.SYMBOL, self.VOLUME,
                                            direction)

            elif direction == 'sell':
                # if we have a SELL signal, close all long positions
                for pos in mt5.positions_get():
                    if pos.type == 0:  # pos.type == 0 represents a buy order
                        await self.close_order(pos.ticket, self.DEVIATION)

                # if there are no open positions, open a new short position
                if not mt5.positions_total():
                    await self.market_order(self.SYMBOL, self.VOLUME,
                                            direction)

            # Open the file in write mode
            file_path = "output.txt"

            with open(file_path, "a") as file:
                # Redirect the standard output to the file
                sys.stdout = file

                # Print to the file
                print('time: ', datetime.now(),flush=True)
                print('exposure: ', exposure,flush=True)
                print('last_close: ', last_close,flush=True)
                print('sma: ', sma, flush=True)
                print('signal: ', direction, flush=True)
                print('-------\n', flush=True)

                # Restore the standard output
                sys.stdout = sys.__stdout__

            await asyncio.sleep(1)  # Wait for 1 second

        # Restore the standard output
        sys.stdout = sys.__stdout__

    async def backtest_candles_3_in_row(self, start_dt, end_dt=datetime.now(), show_fig=False, setup=False):
        try:

            if not start_dt: return "Start date not provided"

            # request ohlc data a save them in a pandas DataFrame
            bars = mt5.copy_rates_range(self.SYMBOL, self.TIMEFRAME, start_dt,
                                        end_dt)

            df = pd.DataFrame(bars)[['time', 'open', 'high', 'low', 'close']]
            df['time'] = pd.to_datetime(df['time'], unit='s')

            df['candle_type'] = np.vectorize(self.specify_candle_type)(
                df['open'], df['close'])

            # find 3 bullish candles in a row
            df['candle_1'] = df['candle_type'].shift(1)
            df['candle_2'] = df['candle_type'].shift(2)
            df['candle_3'] = df['candle_type'].shift(3)
            df['prev_close'] = df['close'].shift(1)

            self.df = df

            display(df)

            if(show_fig): await self.show_fig(setup=setup)


        except asyncio.CancelledError:
            raise "Error Backtesting Candles"

        return self

    async def show_bar(self):

        if not df: return "No DataFrame"

        # Define a custom color mapping dictionary
        color_map = {'bullish': 'green', 'bearish': 'red', 'neutral': 'gray'}
        # evaluating by result
        df3 = df2.groupby('candle_type').agg({
            'count_values': 'count',
            'points': 'mean'
        }).reset_index()

        df3['points_total'] = df3['count_values'] * df3['points']
        display(px.bar(df3,
                       x='candle_type',
                       y='count_values',
                       color="candle_type",
                       color_discrete_map=color_map),
                title='count values')

        display(px.bar(df3,
                       x='candle_type',
                       y='points',
                       color="candle_type",
                       color_discrete_map=color_map),
                title='points')

        return self

    async def show_fig(self, setup=False):

        if self.df is None: raise "No DataFrame"

        df = self.df

        # filtering out 3-in-a-row setups
        df2 = df[(df['candle_1'] == 'bullish')
                      & (df['candle_2'] == 'bullish') &
                      (df['candle_3'] == 'bullish')].copy()

        df2['points'] = df2['close'] - df['prev_close']

        display(df2)

        # visualize the data
        fig = go.Figure(data=go.Ohlc(x=df2['time'],
                                     open=df2['open'],
                                     high=df2['high'],
                                     low=df2['low'],
                                     close=df2['close']))


        if setup:
            # plot the setups
            for i, row in df2.iterrows():
                fig.add_vline(x=row.time,
                              line_width=1,
                              line_dash="dash",
                              line_color="green")

        fig.update(layout_xaxis_rangeslider_visible=False)
        fig.show()

        return self

    async def show_points(self):

        # filtering out 3-in-a-row setups
        df2 = self.df[(self.df['candle_1'] == 'bullish')
                      & (self.df['candle_2'] == 'bullish') &
                      (self.df['candle_3'] == 'bullish')].copy()
        df2['points'] = df2['close'] - self.df['prev_close']

        # evaluating the results
        df2['count_values'] = 1

        
        # if you bought everytime the 3-in-a-row setup finished and held it for 1 candle period
        df2['cumulative_points'] = df2['points'].cumsum()

        # evaluating by result
        df3 = df2.groupby('candle_type').agg({
            'count_values': 'count',
            'points': 'mean'
        }).reset_index()


        df3['points_total'] = df3['count_values'] * df3['points']

        display(df3)
        return self

    def specify_candle_type(self, open_price, close_price):
        if close_price > open_price:
            return 'bullish'
        elif close_price < open_price:
            return 'bearish'
        else:
            return 'doji'