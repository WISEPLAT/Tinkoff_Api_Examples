"""
    This code is an example of applying Trading Strategy for several Tickers.
    The strategy in this code is for demonstration only purposes
    - it outputs OHLCV values.
    Author: Oleg Shpagin, my github: https://github.com/WISEPLAT
"""

import asyncio
import logging
import os
from datetime import timedelta
from typing import List, Optional

from tinkoff.invest import AioRequestError, AsyncClient, CandleInterval, HistoricCandle
from tinkoff.invest.async_services import AsyncServices
from tinkoff.invest.utils import now

TOKEN = os.environ["INVEST_TOKEN"]

logging.basicConfig(format="%(asctime)s %(levelname)s:%(message)s", level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LogOnlyCandlesStrategy:
    """This class is responsible for a strategy. You can put here
    your methods for your strategy."""

    def __init__(
        self,
        figi: str,
        timeframe: CandleInterval,
        days_back: int,
        check_interval: int,
        client: Optional[AsyncServices],
    ):
        self.account_id = None
        self.figi = figi
        self.timeframe = timeframe
        self.days_back = days_back
        self.check_interval = check_interval
        self.client = client
        self.candles: List[HistoricCandle] = []

    async def get_historical_data(self):
        """
        Gets historical data for the instrument. Returns list of candles.
        Requests all the candles of timeframe from days_back to now.

        :return: list of HistoricCandle
        """
        logger.debug(
            "Start getting historical data for %s days back from now. figi=%s",
            self.days_back,
            self.figi,
        )
        async for candle in self.client.get_all_candles(
            figi=self.figi,
            from_=now() - timedelta(days=self.days_back),
            to=now(),
            interval=self.timeframe,
        ):
            if candle not in self.candles:
                if candle.is_complete:
                    self.candles.append(candle)
                    logger.debug("Found %s - figi=%s", candle, self.figi)

    async def ensure_market_open(self):
        """
        Ensure that the market is open. Loop until the instrument is available.
        :return: when instrument is available for trading
        """
        trading_status = await self.client.market_data.get_trading_status(
            figi=self.figi
        )
        while not (
            trading_status.market_order_available_flag
            and trading_status.api_trade_available_flag
        ):
            logger.debug("Waiting for the market to open. figi=%s", self.figi)
            await asyncio.sleep(60)
            trading_status = await self.client.market_data.get_trading_status(
                figi=self.figi
            )

    async def main_cycle(self):
        """Main cycle for live strategy."""
        while True:
            try:
                await self.ensure_market_open()
                await self.get_historical_data()

                # put your strategy code here for live
                # to generate signals for buying or selling tickers
                logger.debug(
                    "- live mode: run some strategy code to buy or sell - figi=%s",
                    self.figi,
                )

            except AioRequestError as are:
                logger.error("Client error %s", are)

            await asyncio.sleep(self.check_interval)

    async def start(self):
        """Strategy starts from this function."""
        if self.account_id is None:
            try:
                self.account_id = (
                    (await self.client.users.get_accounts()).accounts.pop().id
                )
            except AioRequestError as are:
                logger.error("Error taking account id. Stopping strategy. %s", are)
                return
        await self.main_cycle()


async def run_strategy(portfolio, timeframe, days_back, check_interval):
    """From this function we are starting
    strategy for every ticker from portfolio.
    """
    async with AsyncClient(token=TOKEN, app_name="TinkoffApp") as client:
        strategy_tasks = []
        for instrument in portfolio:
            strategy = LogOnlyCandlesStrategy(
                figi=instrument,
                timeframe=timeframe,
                days_back=days_back,
                check_interval=check_interval,
                client=client,
            )
            strategy_tasks.append(asyncio.create_task(strategy.start()))
        await asyncio.gather(*strategy_tasks)


if __name__ == "__main__":

    sber_figi = "BBG004730N88"
    vtbr_figi = "BBG004730ZJ9"
    portfolio = {sber_figi, vtbr_figi}
    timeframe = CandleInterval.CANDLE_INTERVAL_1_MIN
    days_back = 1
    check_interval = 10  # seconds to check interval for new completed candle

    loop = asyncio.get_event_loop()
    task = loop.create_task(
        run_strategy(
            portfolio=portfolio,
            timeframe=timeframe,
            days_back=days_back,
            check_interval=check_interval,
        )
    )
    loop.run_until_complete(task)
