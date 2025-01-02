import sys
import time
from asyncio import Semaphore, Lock

import requests
from playwright.async_api import async_playwright
from pydantic import BaseModel
from loguru import logger


class Profile(BaseModel):
    id: int
    name: str
    ads_id: str
    password: str
    ref_code: str | None

    def __repr__(self):
        return (f"Name: {self.name} | bubble_amount: {self.bubble_amount}, "
                f"tasks_done: {self.tasks_done}, total_win_amount: {self.total_win_amount}")


    def open_profile(self):
        # "--disable-blink-features=AutomationControlled"
        args = ["--disable-popup-blocking", "--window-position=700,0"]
        args = str(args).replace("'", '"')
        open_url = f"http://local.adspower.net:50325/api/v1/browser/start?user_id=" + self.ads_id + f"&launch_args={str(args)}"

        try:
            # Отправка запроса на открытие профиля
            resp = requests.get(open_url).json()
            time.sleep(.5)
        except requests.exceptions.ConnectionError:
            logger.error(f'Adspower is not running.')
            sys.exit(0)
        except requests.exceptions.JSONDecodeError:
            logger.error(f'Проверьте ваше подключение. Отключите VPN/Proxy используемые напрямую.')
            sys.exit(0)
        except KeyError:
            resp = requests.get(open_url).json()

        return resp


    async def process(self, profiles_stats: list, new: bool, no_green_id: bool, semaphore: Semaphore, lock: Lock):
        from utils import write_results_for_profile, move_profile_to_done
        from mint_forest import Mint

        async with semaphore:
            resp = self.open_profile()
            close_url = "http://local.adspower.net:50325/api/v1/browser/stop?user_id=" + self.ads_id

            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(resp["data"]["ws"]["puppeteer"])
                context = browser.contexts[0]
                mint = Mint(context, self)

                await mint.unlock_rabby()

                if new and no_green_id:
                    await mint.register_account(self.ref_code)
                    return

                if no_green_id:
                    # Пока не делаю твиттер таски на новорегах потому что там селектора другие если нет грин айди
                    bubble_amount = await mint.daily_bubble()
                    await mint.spend_mint_energy()

                bubble_amount = await mint.daily_bubble()
                tasks_done = await mint.mint_socials()
                total_win_amount = await mint.lucky_roulette()
                await mint.spend_mint_energy()

            result = Result(name=str(self.name), bubble_amount=int(bubble_amount),
                            tasks_done=int(tasks_done), total_win_amount=int(total_win_amount))

            profiles_stats.append(result)
            async with lock:
                write_results_for_profile('./results.xlsx', self, result)
                move_profile_to_done('./profiles.xlsx', self)

                # todo: add check "Seed Phrase ..."
                #  если вообще где угодно что-то застряло то попробовать клик по слову close

            requests.get(close_url)
            logger.success(f'Name: {self.name} all done')


class Result(BaseModel):
    name: str
    bubble_amount: int
    tasks_done: int
    total_win_amount: int

    def __repr__(self):
        return (f"Name: {self.name} | bubble_amount: {self.bubble_amount}, "
                f"tasks_done: {self.tasks_done}, total_win_amount: {self.total_win_amount}")
