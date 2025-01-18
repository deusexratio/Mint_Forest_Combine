import random
import time
import traceback
from os import close

from playwright.async_api import async_playwright, expect, BrowserContext, Page, Locator
from loguru import logger
from playwright._impl._errors import TimeoutError, Error, TargetClosedError
import asyncio

from settings import RETRY_ATTEMPTS, bridge_min, bridge_max, relay_bridge_inbound_chain
from utils import Profile, randfloat


class Mint:
    def __init__(self, context: BrowserContext, profile: Profile):
        self.context = context
        self.profile = profile
        self.mint_url = 'https://www.mintchain.io/mint-forest'
        self.rabby_ext_id = 'acmacodkjbdgmoleebolmdjonilkdbch'
        self.rabby_ext_url = f'chrome-extension://{self.rabby_ext_id}/index.html'
        self.rabby_notification_url = f'chrome-extension://{self.rabby_ext_id}/notification.html'


    async def unlock_rabby(self):
        for i in range(RETRY_ATTEMPTS):
            try:
                logger.debug(f'Name: {self.profile.name} | Starting to unlock Rabby')
                # 'chrome-extension://acmacodkjbdgmoleebolmdjonilkdbch/index.html#/unlock'
                rabby_page = await self.context.new_page()
                await rabby_page.bring_to_front()
                await rabby_page.goto(self.rabby_ext_url)
                await asyncio.sleep(.5)

                try:
                    if await rabby_page.get_by_text("What's new").is_visible(timeout=3000):
                        await rabby_page.locator('/html/body/div[2]/div/div[2]/div/div[2]/button/span').click(
                            timeout=3000)
                except:
                    logger.error(f'Name: {self.profile.name} | Can"t close whats new')


                try:
                    await expect(rabby_page.get_by_text('No Dapp found')).not_to_be_visible()
                    # if RABBY_VERSION == 'OLD':
                    #     await expect(rabby_page.locator('//*[@id="root"]/div[1]/div[2]/div[1]')).not_to_be_visible()
                    # else:
                    #     await expect(rabby_page.locator('//*[@id="root"]/div/div[1]/div[1]/div[1]/span')).not_to_be_visible()
                except:
                    logger.debug(f'Name: {self.profile.name} | Already unlocked Rabby')
                    await rabby_page.close()
                    return

                password_field = rabby_page.get_by_placeholder('Enter the Password to Unlock')
                await expect(password_field).to_be_visible()
                await password_field.fill(self.profile.password)

                unlock_button = rabby_page.get_by_text('Unlock')
                await expect(unlock_button).to_be_enabled()
                await unlock_button.click()
                logger.success(f'Name: {self.profile.name} | Unlocked Rabby')

                # clean up rabby pages
                await rabby_page.close()

                titles = [await p.title() for p in self.context.pages]
                for rabby_page_index, title in enumerate(titles):
                    if 'Rabby' in title:
                        page = self.context.pages[rabby_page_index]
                        await page.close()

                break

            except Exception as e:
                logger.error(f'Name: {self.profile.name} | {e}')
                continue


    async def connect_wallet_to_mint(self, connect_login_button):
        logger.debug(f'Name: {self.profile.name} | Starting connecting wallet to Mint')
        mint_page = await self.get_page_by_url(self.mint_url)
        try:
            await expect(connect_login_button).to_have_text('Connect')
        except:
            logger.debug(f'Name: {self.profile.name} | Already connected wallet to Mint')
            return

        # await mint_page.get_by_text('Connect').last.click(timeout=1000)
        await connect_login_button.click(timeout=1000)
        await mint_page.get_by_text('Rabby Wallet').click(timeout=1000)
        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url,timeout_=10000)
        try:
            await rabby_page.get_by_text('Ignore all').click(timeout=5000)
        except:
            pass
        connect_button = rabby_page.locator('//*[@id="root"]/div/div/div/div/div[3]/div/div/button[1]')
        await expect(connect_button).to_be_enabled()
        await connect_button.click(timeout=5000)
        # await rabby_page.get_by_text('Confirm').click(timeout=5000)
        logger.debug(f'Name: {self.profile.name} | Connected wallet to Mint')


    async def login_wallet_to_mint(self, connect_login_button):
        logger.debug(f'Name: {self.profile.name} | Starting logging in wallet to Mint')
        await connect_login_button.click(timeout=1000)
        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=10000)

        await asyncio.sleep(3)
        await rabby_page.get_by_role('button', name='Sign').click(timeout=10000)
        await asyncio.sleep(.3)
        await rabby_page.get_by_text('Confirm').click(timeout=1000)
        await asyncio.sleep(1)
        logger.debug(f'Name: {self.profile.name} | Logged in wallet to Mint')


    async def switch_to_extension_page(self, extension, timeout_ = 60000):
        extension_page = next((p for p in self.context.pages if extension in p.url), None)

        if not extension_page:
            try:
                extension_page = await self.context.wait_for_event('page', timeout=timeout_)
            except TimeoutError:
                logger.error(f"Ошибка: вкладка с расширением не открылась в течение {timeout_} мс.")
                return None

        if extension in extension_page.url:
            await extension_page.bring_to_front()
            logger.info("Переключились на вкладку с расширением.")
            return extension_page
        else:
            logger.error("Ошибка: Найденная страница не соответствует расширению.")
            return None


    async def close_new_page(self, url, timeout_ = 60000):
        url_page = next((p for p in self.context.pages if url in p.url), None)

        if not url_page:
            try:
                url_page = await self.context.wait_for_event('page', timeout=timeout_)
            except TimeoutError:
                logger.error(f"Ошибка: вкладка с расширением не открылась в течение {timeout_} мс.")
                return None

        if url in url_page.url:
            await url_page.close()
            logger.info(f"{url_page} closed")
            return url_page
        else:
            logger.error("Ошибка: Найденная страница не соответствует расширению.")
            return None


    async def get_page_by_title(self, page_title: str, page_url):
        titles = [await p.title() for p in self.context.pages]
        page_index = 0

        for title in titles:
            # print(title)
            if page_title in title:
                page = self.context.pages[page_index]
                # page.reload()
                return page
            page_index += 1

        page = await self.context.new_page()
        await page.goto(page_url)
        await page.set_viewport_size({"width": 1500, "height": 1000})
        return page


    async def get_page_by_url(self, page_url: str):
        urls = [p.url for p in self.context.pages]
        page_index = 0

        for url in urls:
            # print(title)
            if page_url in url:
                page = self.context.pages[page_index]
                # page.reload()
                return page
            page_index += 1

        page = await self.context.new_page()
        await page.goto(page_url)
        await page.set_viewport_size({"width": 1500, "height": 1000})
        return page


    async def check_connection_ext_to_mint(self, page):
        connect_login_button = page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div/div[2]/button')

        # for i in range(settings.RETRY_ATTEMPTS):
        #     try:
        #         # Проверяем что есть надпись коннект (ребби при загруженной изначально странице не подхватывается)
        #         connect_wallet_button = mint_page.locator('//*[@id="app-root"]/header/div/div[1]/div/div[1]/p')
        #                                             # '//*[@id="app-root"]/header/div/div[1]/div/div[1]/div'
        #         expect(connect_wallet_button).to_have_text('Connect Wallet')
        #         # Обновляем страницу и если уже приконнектились то выходим из цикла
        #         mint_page.reload()
        #         try:
        #             expect(connect_wallet_button).not_to_be_visible()
        #         except:
        #             break
        #         # expect(mint_page.get_by_text('Login')).not_to_be_visible()
        #     except:
        #         break
        #     try:
        #         connect_wallet_button.click(timeout=3000)
        #         rabby_button = mint_page.locator('/html/body/div[11]/div/div/div[2]/div/div/div/div/div[1]/div[2]/div[2]/div[1]/button/div/div/div[2]/div[1]')
        #         rabby_button.click(timeout=3000)
        #         rabby_page = self.switch_to_extension_page(self.rabby_notification_url)
        #         # self.connect_wallet(connect_login_button)
        #     except:
        #         continue

        # Connect wallet
        for i in range(RETRY_ATTEMPTS):
            try:
                await expect(connect_login_button).to_have_text('Connect')
                # expect(mint_page.get_by_text('Login')).not_to_be_visible()
            except:
                break
            try:
                await self.connect_wallet_to_mint(connect_login_button)
            except:
                continue

        await asyncio.sleep(1)
        # Login wallet
        for i in range(RETRY_ATTEMPTS):
            try:
                await expect(connect_login_button).to_have_text('Login')
            except:
                break
            try:
                await self.login_wallet_to_mint(connect_login_button)
            except:
                continue


    async def all_preparations(self):
        mint_page = await self.get_page_by_url(self.mint_url)
        await mint_page.bring_to_front()
        while True:
            try:
                await mint_page.reload()
                break
            except:
                continue
        await asyncio.sleep(1)

        await self.check_connection_ext_to_mint(mint_page)

        # In case for popups on forest page
        try:
            await expect(mint_page.get_by_text('New')).not_to_be_visible()
        except:
            await mint_page.get_by_text('Close').click(timeout=1000)

        try:
            await expect(mint_page.get_by_text('Close')).not_to_be_visible()
        except:
            await mint_page.get_by_text('Close').click(timeout=1000)

        return mint_page


    async def sign_transaction(self, rabby_page):
        try:
            sign_button = rabby_page.get_by_role('button', name='Sign')
            await expect(sign_button).to_be_enabled(timeout=20000)
            await sign_button.click(timeout=10000)
            await rabby_page.get_by_text('Confirm').click(timeout=1000)
        except Exception as e:
            if await rabby_page.get_by_text('not enough').is_visible(timeout=1000):
                await rabby_page.close()
                logger.info(f'Name: {self.profile.name} | Нет эфира в минте на газ')
                await self.relay()
                return False
            else:
                logger.error(f'Name: {self.profile.name} | Не удалось подтвердить транзакцию {e}')

        return True


    async def daily_bubble(self):
        mint_page = await self.all_preparations()

        for i in range(RETRY_ATTEMPTS):
            try:
                logger.debug(f'Name: {self.profile.name} | {i} attempt popping bubble')

                # Перепроверяем логин, иногда почему-то подвисает
                connect_login_button = mint_page.get_by_role(role='button', name='Login')
                if await connect_login_button.is_visible(timeout=500):
                    await self.login_wallet_to_mint(connect_login_button)

                # Вынес проверку страницы кошелька из-за лабуды со сменой сети
                rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=10000)
                if rabby_page:
                    if not await self.sign_transaction(rabby_page):
                        continue

                # Проверка выполнен ли уже пузырик
                try:
                    await mint_page.reload()
                    await asyncio.sleep(3)
                    pale_bubble = mint_page.locator(
                        '//div[@class="absolute flex items-center justify-center cursor-pointer max-h-[68px] max-w-[68px]'
                        ' z-[9999] select-none scale-100 translate-y-[-3px] bubble-wave text-[#AC9F8F]"]'
                    )
                    if pale_bubble and await pale_bubble.is_visible():
                        # today_activity_list = mint_page.locator('//*[@id="forest-root"]/div[3]/div[4]/div[2]/div/div[2]/div').locator('xpath=*')
                        # for index in range(await today_activity_list.count()):
                        #     activity = today_activity_list.locator('')

                        bubble_amount = int((await pale_bubble.text_content())[:-8])
                        logger.success(f'Name: {self.profile.name} | Daily bubble completed. Points: {bubble_amount}')
                        return bubble_amount
                    else:
                        logger.debug(f'Name: {self.profile.name} | Daily bubble NOT yet completed')

                except Exception as e:
                    logger.error(f'{e}')

                # отключаем анимацию
                await mint_page.evaluate("""
                    const style = document.createElement('style');
                    style.innerHTML = `
                        * {
                            animation: none !important;
                            transition: none !important;
                        }
                    `;
                    document.head.appendChild(style);
                """)

                # Клик по пузырику
                try:
                    bubble = mint_page.locator(
                        '//div[@class="absolute flex items-center justify-center cursor-pointer max-h-[68px] max-w-[68px]'
                        ' z-[9999] select-none scale-100 translate-y-[-3px] bubble-wave text-[#BD751F]"]'
                    )
                    # bubble_amount = int(bubble.text_content())
                    await bubble.hover()
                    await bubble.click(timeout=1000)
                except Exception as e:
                    logger.error(f"{str(e)[:700]}")

                # второй клик обходится просто циклом с ретраями
                # rabby_page = self.switch_to_extension_page(self.rabby_notification_url, timeout_=5000)
                # rabby_page.get_by_text('Sign and Create').click(timeout=1000)
                # rabby_page.get_by_text('Confirm').click(timeout=1000)

            except TargetClosedError as e:
                logger.error(f"{str(e)[:200]}")
                mint_page = await self.all_preparations()
                continue

            except Exception as e:
                traceback.print_exc()
                logger.error(f"{str(e)[:200]}")
                continue


    async def mint_socials(self, no_green_id: bool = False):
        async def handle_task(task_: Locator):
            if task_ and await task_.is_visible():
                # Кликаем по "Go"
                task_button = task_.get_by_text('Go')
                if task_button and await task_button.is_visible():
                    # Проверяем текст в дочернем элементе (например, span с описанием задания)
                    task_text_ = await task_.locator('xpath=div[2]/span[1]').inner_text(timeout=1000)
                    if "Join Mint Discord" == task_text_:
                        logger.info(f"Пропускаем задание: {task_text_}")
                        await asyncio.sleep(5)
                        task_ = parent_tasks_locator.locator('xpath=*').nth(1)
                        if task_ and await task_.is_visible():
                            task_text_ = await task_.locator('xpath=div[2]/span[1]').inner_text(timeout=1000)
                            if task_text_ == 'Share "MintID Staking" on Twitter':
                                logger.info(f"Пропускаем задание: {task_text_}")
                                task_ = parent_tasks_locator.locator('xpath=*').nth(2)

                                try:
                                    task_text_ = await task_.locator('xpath=div[2]/span[1]').inner_text(timeout=1000)
                                except:
                                    # logger.info(f'Таски закончились')
                                    return 0

                            task_button = task_.get_by_text('Go')

                        else:
                            # logger.info(f'Локаторов с тасками не осталось')
                            return 0

                else:
                    # logger.info(f"Пропускаем задание: {task_}, нет кнопки Go")
                    # await asyncio.sleep(5)
                    task_ = parent_tasks_locator.locator('xpath=*').nth(1)
                    if task_ and await task_.is_visible():
                        task_text_ = await task_.locator('xpath=div[2]/span[1]').inner_text(timeout=1000)
                        task_button = task_.get_by_text('Go')
                    else:
                        # logger.info(f'Локаторов с тасками не осталось')
                        return 0

                if task_button and await task_button.is_visible():
                    logger.debug(f"Name: {self.profile.name} | Кликаю по task: {task_text_}")
                    await task_button.click(timeout=1000)
                    await asyncio.sleep(randfloat(1, 3, 0.001))

                    if (task_text_ == 'Share "Mint Your Tree" on Twitter' or
                            task_text_ == 'Share "Activate Your GreenID" on Twitter'):
                        twitter_task_page = await self.switch_to_extension_page('x.com', timeout_=5000)
                        await twitter_task_page.bring_to_front()
                        # await twitter_task_page.wait_for_load_state('domcontentloaded')

                        await asyncio.sleep(10)
                        tweet_button = twitter_task_page.get_by_test_id("tweetButton")
                        await tweet_button.click(timeout=3000)

                        post = twitter_task_page.get_by_test_id('toast').get_by_text('View')
                        await post.click(timeout=3000, force=True)

                        # await twitter_task_page.wait_for_load_state('domcontentloaded')
                        # if 'Share "Activate Your GreenID" on Twitter' == task_text_:
                        #     post = twitter_task_page.get_by_text('Hey frens, activate the GreenID NFT from')
                        # elif 'Share "Mint Your Tree" on Twitter' == task_text_:
                        #     post = twitter_task_page.get_by_text('Mint is the L2 for NFT industry, powered by')

                        # await post.click(timeout=3000)
                        tweet_link = twitter_task_page.url
                        await mint_page.bring_to_front()
                        tweet_input = task_.get_by_placeholder("Input the tweet url")
                        await tweet_input.fill(tweet_link)

                    twitter_task_page = await self.close_new_page('x.com', timeout_=5000)

                    # Кликаем по "Verify"
                    verify_button = task_.get_by_text('Verify')
                    if verify_button and await verify_button.is_visible():
                        await verify_button.click(timeout=1000)
                        await asyncio.sleep(randfloat(1, 3, 0.001))
                        logger.success(f"Name: {self.profile.name} | Task выполнен: {task_text_}")
                        return 1

                else:
                    task_text_ = await task_.locator('xpath=div[2]/span[1]').inner_text(timeout=1000)
                    logger.error(f'{task_text_} после всех проверок не найдена кнопка Go')
                    # return 0

        mint_page = await self.all_preparations()

        if no_green_id:
            parent_tasks_locator = mint_page.locator('//*[@id="forest-root"]/div[3]/div[3]/div[1]/div/div[2]/div[2]/div/div[2]/div')
        else:
            parent_tasks_locator = mint_page.locator('//*[@id="forest-root"]/div[3]/div[4]/div[1]/div/div[2]/div[2]/div/div[2]/div')

        tasks_done = 0
        while True:
            try:
                # Получаем первый доступный task
                task = parent_tasks_locator.locator('xpath=*').first
                await task.scroll_into_view_if_needed(timeout=10000)

                task_result = await handle_task(task)
                if task_result == 1:
                    tasks_done += 1
                else:
                    logger.info(f"Name: {self.profile.name} | Все задания выполнены.")
                    return tasks_done

            except Exception as e:
                logger.error(f"Name: {self.profile.name} | {e}")
                continue


    async def lucky_roulette(self, no_green_id: bool = False):
        mint_page = await self.all_preparations()

        if no_green_id:
            lucky_button = mint_page.locator('//*[@id="forest-root"]/div[3]/div[1]/img[3]')
        else:
            # lucky_button = mint_page.locator('//*[@id="forest-root"]/div[3]/div[2]/img[3]')
            lucky_button = mint_page.get_by_alt_text('lucky', exact=True)

        await lucky_button.scroll_into_view_if_needed()
        await lucky_button.click(timeout=3000)

        _300_button = mint_page.locator('//*[@id="spin-root"]/div[3]/div/div[1]/span')
        spin_count_str = await mint_page.locator('//*[@id="spin-root"]/div[1]/span').text_content()
        if spin_count_str == '10/10':
            logger.debug(f"Name: {self.profile.name} | Все рулетки на сегодня уже прокручены")
            return True

        spin_count_int = int(spin_count_str.split('/')[0].strip('"'))

        total_win_amount = 0
        iterator_count = 0
        done = False
        while spin_count_int < 10:
            try:
                logger.debug(f"Name: {self.profile.name} | Запускаю бурмалду. Текущий счетчик спинов: {spin_count_str}")
                iterator_count += 1

                # почему-то spin_count_str до первого прокрута всегда 0/10 возвращает,
                # хотя там может быть и 1/10 и 10/10 и он будет тупить бесконечно

                rabby_page = None
                while not rabby_page and not done:
                    try:
                        await _300_button.click(timeout=3000)
                    except:
                        await mint_page.get_by_text('close').click(timeout=3000)
                    try:
                        await expect(mint_page.get_by_text("You can't spin anymore today")).to_be_visible(timeout=5000)
                        done = True
                    except:
                        pass
                    # time.sleep(randfloat(3, 6, 0.001))

                    rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=10000)
                    if rabby_page:
                        if not await self.sign_transaction(rabby_page):
                            continue

                if done:
                    logger.success(f"Name: {self.profile.name} | На сегодня все спины прокручены")
                    break

                await asyncio.sleep(randfloat(2,3, 0.001))

                try:
                    await expect(rabby_page.get_by_text('Fail to create')).to_be_visible()
                    logger.error(f"Name: {self.profile.name} | Кончился эфир в сети Минт")
                    return total_win_amount
                except:
                    pass

                win = (await mint_page.get_by_text('Congratulations on winning').text_content()).split(' ')[-2]
                win_amount = int(win.strip('"').replace(',', ''))

                await asyncio.sleep(randfloat(3, 4, 0.001))
                while True:
                    try:
                        close_button = mint_page.get_by_text('close')
                        await close_button.click(timeout=3000)
                        break
                    except Exception as e:
                        logger.error(f"{e[:700]} ")
                        continue

                if win_amount > 1000:
                    logger.success(f"Name: {self.profile.name} | ОГО, ВОТ ЭТО ЗАНОС!!!!, Win: {win_amount}")
                elif win_amount < 500:
                    logger.success(f"Name: {self.profile.name} | Не фартануло браток, Win: {win_amount}")
                else:
                    logger.success(f"Name: {self.profile.name} | Торпеда залетела, Win: {win_amount}")
                total_win_amount += win_amount


                spin_count_str = await mint_page.locator('//*[@id="spin-root"]/div[1]/span').text_content()
                spin_count_int = int(spin_count_str.split('/')[0].strip('"'))

            except Exception as e:
                logger.error(f"{e}")
                continue

        logger.success(f"Name: {self.profile.name} | Все торпеды знищены, Итоговый выигрыш: {total_win_amount} "
                       f"за {iterator_count} попыток. Потрачено {iterator_count*300} энергии")
        return total_win_amount


    async def spend_mint_energy(self, amount_percent: float | None = None):
        mint_page = await self.all_preparations()
        await mint_page.set_viewport_size({"width": 1500, "height": 1500})

        if not amount_percent:
            amount_percent = randfloat(0.5, 0.75, 0.01)

        for i in range(RETRY_ATTEMPTS):
            try:
                mint_energy_count_locator = mint_page.locator('//*[@id="inject-root"]/div[2]/span[1]')
                mint_energy = (await mint_energy_count_locator.text_content()).strip(' ME').replace(",", "")

                amount_to_spend = int(int(mint_energy) * amount_percent)

                await mint_energy_count_locator.click(timeout=3000)
                me_input = mint_page.locator('//*[@id="react-tiny-popover-container"]/div/div/div/div/div[4]/input')
                await me_input.fill(str(amount_to_spend))

                await asyncio.sleep(2)
                inject_button = mint_page.get_by_text('Inject ME')
                await expect(inject_button).to_be_enabled(timeout=3000)
                await inject_button.click(timeout=3000)

                await asyncio.sleep(1)
                logger.success(f"Name: {self.profile.name} | Injected {amount_to_spend} mint energy")
                break

            except Exception as e:
                logger.error(f"Name: {self.profile.name} | error")
                if 'element is not stable' in e:
                    # отключаем анимацию
                    await mint_page.evaluate("""
                        const style = document.createElement('style');
                        style.innerHTML = `
                            * {
                                animation: none !important;
                                transition: none !important;
                            }
                        `;
                        document.head.appendChild(style);
                    """)
                    await inject_button.click(timeout=3000)

                    await asyncio.sleep(1)
                    logger.success(f"Name: {self.profile.name} | Injected {amount_to_spend} mint energy")
                    break


    async def register_account(self, ref_code: str) -> bool:
        mint_page = await self.get_page_by_url(self.mint_url)
        await mint_page.bring_to_front()
        while True:
            try:
                await mint_page.reload()
                break
            except:
                continue
        await asyncio.sleep(1)

        await self.check_connection_ext_to_mint(mint_page)

        try:
            bubble = mint_page.locator(
                '//div[@class="absolute flex items-center justify-center cursor-pointer max-h-[68px] max-w-[68px]'
                ' z-[9999] select-none scale-100 translate-y-[-3px] bubble-wave text-[#BD751F]"]'
            )
            await expect(bubble).to_be_visible(timeout=10000)
            logger.debug(f"Name: {self.profile.name} | Акк уже был регнут! Main page")
            return True
        except:
            pass


        try:
            check_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[2]/div[2]/button')
            await check_button.click(timeout=10000)
            await asyncio.sleep(5)
            # Проверяем галочку после нажатия чека
            # await expect(mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[2]/div[2]/svg')).to_be_visible(timeout=10000)
        except Exception as e:
            logger.debug(f"Name: {self.profile.name} | {e}. Акк уже был регнут?")
            pass
            # return True

        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=5000)
        if rabby_page:
            await rabby_page.close()

        try:
            connect_twitter_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[3]/div[2]/button')
            await connect_twitter_button.click(timeout=10000)
        except Exception as e:
            logger.info(f"Name: {self.profile.name} | {e}. Твиттер уже подвязан?")
            # return False
            # Пока тут поставлю слип, чтобы можно было ручками зайти на подвисших акках
            # await asyncio.sleep(1000)
            pass

        try:
            auth_button = mint_page.get_by_text('Authorize app')
            await auth_button.click(timeout=10000)
        except Exception as e:
            logger.error(f"Name: {self.profile.name} | {e}. Твиттер не залогинен!")

        # Проверяем галочку коннекта твиттера
        # await expect(mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[3]/div[2]/svg')).to_be_visible(timeout=10000)
        await asyncio.sleep(5)
        try:
            bind_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[4]/div[2]/button')
            await bind_button.click(timeout=10000)
        except:
            logger.error(f"Name: {self.profile.name} | Бинд уже нажат")
            pass

        try:
            ref_code_input = mint_page.locator('body > div.ReactModalPortal > div > div > div > '
                                               'div.w-full.mt-14.lg\:mt-28.flex.justify-center > div > div > input')
            await ref_code_input.fill(ref_code)
            await asyncio.sleep(3)
            await mint_page.get_by_text('Join Now').click(timeout=10000)

            # отключить кош и обновить страницу

        except Exception as e:
            logger.error(f"Name: {self.profile.name} | {e} Реф код уже забит")
            pass

        # In case for popups on forest page
        try:
            await expect(mint_page.get_by_text('New')).not_to_be_visible()
        except:
            await mint_page.get_by_text('Close').click(timeout=1000)

        logger.success(f"Name: {self.profile.name} | Регнул акк!")

        try:
            if await mint_page.get_by_text('Eligibility Verification').is_visible(timeout=10000):
                wallet_button = mint_page.locator('//*[@id="app-root"]/header/div/div[3]/div/div')
                await wallet_button.click(timeout=10000)
                await mint_page.get_by_text('Log Out').click(timeout=5000)
                await mint_page.reload()
        except Exception as e:
            bubble = mint_page.locator(
                '//div[@class="absolute flex items-center justify-center cursor-pointer max-h-[68px] max-w-[68px]'
                ' z-[9999] select-none scale-100 translate-y-[-3px] bubble-wave text-[#BD751F]"]'
            )
            if await bubble.is_visible(timeout=5000):
                return True
            logger.error(f"Name: {self.profile.name} | Что-то пошло не так после регистрации {e}")

        # Регаем дискорд
        # await self.reg_discord(mint_page)

        return True


    async def reg_discord(self, mint_page: Page):
        logger.debug(f"Name: {self.profile.name} | Начинаю регать дискорд")
        go_discord_button = mint_page.locator('//*[@id="forest-root"]/div[3]/div[3]/div[1]/div/div[2]/div[2]/div/div[2]/div/div[2]/div[3]')
        await go_discord_button.click(timeout=10000)

        try:
            auth_button = mint_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div/div/div/div[2]/div/div/button')
            await auth_button.click(timeout=7000)
            await expect(go_discord_button).to_be_visible(timeout=20000)
            logger.debug(f"Name: {self.profile.name} | Авторизовал дискорд")
        except:
            logger.debug(f"Name: {self.profile.name} | Дискорд уже был авторизован")

        await asyncio.sleep(5)

        await go_discord_button.click(timeout=10000)

        discord_page = await self.get_page_by_url('https://discord.com/invite/mint-blockchain')
        accept_invite_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div[2]/div/div/div/section/div[2]/button/div')
        await accept_invite_button.click(timeout=10000)

        # Если вылезла капча решаем руками и потом ничего не делаем
        try:
            await expect(discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[5]/div[2]/div/div/div/div[1]/div[2]')).to_be_visible(timeout=10000)
            logger.critical(f"Name: {self.profile.name} | Нужно решить капчу!")
            await asyncio.sleep(180)
        except:
            pass

        # Этот блок для тех у кого на компе стоит приложение дискорда
        try:
            go_to_site_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div/div/section/div[2]/button/div')
            await go_to_site_button.click(timeout=10000)
        except:
            pass

        try:
            close_news_button = discord_page.locator('//*[@id=":r1:"]/button')
            await close_news_button.click(timeout=10000)
            logger.debug(f"Name: {self.profile.name} | Закрыл новости")
        except:
            logger.debug(f"Name: {self.profile.name} | Новостей в дискорде не бьло")

        community_button = discord_page.locator("You'll be a part of a bunch of channels in Mint community")
        await community_button.click(timeout=10000)
        finish_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div[2]/div/div/div/div/div/div[4]/div/div/div[2]/div[2]/button')
        await finish_button.click(timeout=10000)

        await discord_page.get_by_text('verify-here').nth(1).click(timeout=10000)
        do_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div[2]/div/div/div/div/div[2]/div[2]/main/form/div/div[2]/button')
        await do_button.click(timeout=10000)

        send_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[4]/div[2]/div/div/div[2]/div[2]/button')
        await send_button.click(timeout=10000)

        react_button = discord_page.locator('//*[@id="message-reactions-1181968186879516744"]/div[2]/div/div')
        await react_button.click(timeout=10000)

        logger.success(f"Name: {self.profile.name} | Прошел вериф на сервере полностью")

        await discord_page.close()
        await mint_page.bring_to_front()

        await expect(go_discord_button).to_contain_text('Verify')
        await go_discord_button.click(timeout=10000)
        await expect(mint_page.get_by_text('Completed task')).to_be_visible(timeout=10000)
        logger.success(f"Name: {self.profile.name} | Завершил таск с дискордом")

        return True


    async def relay(self):
        while True:
            try:
                relay_page =  await self.get_page_by_url('https://relay.link/bridge/mint')

                connect_button = relay_page.locator('//*[@id="__next"]/div[2]/div/main/div/div/div/div/button')
                try:
                    await expect(connect_button).not_to_have_text('Connect', timeout=10000)
                except:
                    try:
                        await connect_button.click(timeout=3000)
                        await expect(connect_button).not_to_have_text('Connect', timeout=10000)
                    except:
                        # await connect_button.click(timeout=3000)
                        rabby_button = relay_page.get_by_text('Rabby')
                        await rabby_button.click(timeout=1000)
                        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=10000)
                        if rabby_page:
                            try:
                                await rabby_page.get_by_text('Ignore all').click(timeout=1000)
                            except:
                                pass
                            await rabby_page.get_by_role("button", name="Connect").click(timeout=1000)
                            # await rabby_page.get_by_text('Confirm').click(timeout=1000)
                        logger.debug(f'Name: {self.profile.name} | Connected wallet to Relay')

                select_inbound_chain_button = relay_page.locator('//*[@id="from-token-section"]/button')
                await select_inbound_chain_button.click(timeout=3000)
                inbound_chain = relay_page.get_by_text(relay_bridge_inbound_chain)
                await inbound_chain.scroll_into_view_if_needed(timeout=5000)
                await inbound_chain.click(timeout=5000)

                input_amount = relay_page.locator('//*[@id="from-token-section"]/div[2]/div[1]/input')
                amount_to_bridge = randfloat(bridge_min, bridge_max, 0.0001)
                await input_amount.fill(str(amount_to_bridge))
                await relay_page.get_by_text('Trade').click(timeout=10000)
                await relay_page.get_by_text('Confirm').click(timeout=10000)

                rabby_page = await self.switch_to_extension_page(self.rabby_notification_url)
                await rabby_page.get_by_text('Sign and Create').click(timeout=10000)
                await rabby_page.get_by_text('Confirm').click(timeout=5000)

                success = relay_page.get_by_text('Successfully swapped')
                await expect(success).to_be_visible(timeout=30000)
                logger.success(f"Name: {self.profile.name} | Забриджил {amount_to_bridge} ETH from {relay_bridge_inbound_chain}")

                await relay_page.close()

                return amount_to_bridge

            except Exception as e:
                logger.critical(f"Name: {self.profile.name} | Что-то пошло не так в бридже, жду помощи руками {e}")
                await asyncio.sleep(100)


    async def test_twitter(self):
        twitter_task_page = await self.switch_to_extension_page('x.com')
        # post_input = twitter_task_page.get_by_text('What is happening?!')
        post_input = twitter_task_page.get_by_test_id('tweetTextarea_0RichTextInputContainer')
        await post_input.click()
        await asyncio.sleep(randfloat(1, 3))
        post_input = twitter_task_page.get_by_test_id('tweetTextarea_0')
        await post_input.fill('zdravstvuite')
        await asyncio.sleep(randfloat(1, 3))
        await twitter_task_page.get_by_test_id('tweetButtonInline').click()
        # post = twitter_task_page.get_by_role('link', name='View')
        post = twitter_task_page.get_by_test_id('toast').get_by_text('View')
        # post_link_html = twitter_task_page.get_by_test_id('toast').get_by_role('link')
        # print(await post_link_html.evaluate("el => el.outerHTML"))
        await post.click(timeout=3000, force=True)
