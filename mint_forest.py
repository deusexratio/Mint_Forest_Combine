import random
import time
import traceback
from os import close

from playwright.async_api import async_playwright, expect, BrowserContext, Page
from loguru import logger
# from playwright.sync_api import sync_playwright, expect, BrowserContext
from playwright._impl._errors import TimeoutError, Error, TargetClosedError
import asyncio

import settings
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
        for i in range(settings.RETRY_ATTEMPTS):
            try:
                logger.debug(f'Name: {self.profile.name} | Starting to unlock Rabby')
                # 'chrome-extension://acmacodkjbdgmoleebolmdjonilkdbch/index.html#/unlock'
                rabby_page = await self.context.new_page()
                await rabby_page.bring_to_front()
                await rabby_page.goto(self.rabby_ext_url)
                await asyncio.sleep(.5)
                try:
                    # expect(rabby_page.get_by_text('Swap')).not_to_be_visible()
                    await expect(rabby_page.locator('//*[@id="root"]/div[1]/div[2]/div[1]')).not_to_be_visible()
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
                # titles = [p.title() for p in self.context.pages]
                # rabby_page_index= 0
                # for title in titles:
                #     if 'Rabby' in title:
                #         page = self.context.pages[rabby_page_index]
                #         page.close()
                #     rabby_page_index += 1

                break
            except Exception as e:
                logger.error(f'Name: {self.profile.name} | {e}')
                continue


    async def connect_wallet(self, connect_login_button):
        logger.debug(f'Name: {self.profile.name} | Starting connecting wallet to Mint')
        mint_page = await self.get_page('Mint', self.mint_url)
        try:
            await expect(connect_login_button).to_have_text('Connect')
        except:
            logger.debug(f'Name: {self.profile.name} | Already connected wallet to Mint')
            return

        await mint_page.get_by_text('Connect').last.click(timeout=1000)
        await mint_page.get_by_text('Rabby Wallet').click(timeout=1000)
        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url)
        try:
            await rabby_page.get_by_text('Ignore all').click(timeout=1000)
        except:
            pass
        await rabby_page.get_by_text('Connect').click(timeout=1000)
        await rabby_page.get_by_text('Confirm').click(timeout=1000)
        logger.debug(f'Name: {self.profile.name} | Connected wallet to Mint')


    async def login_wallet(self, connect_login_button):
        logger.debug(f'Name: {self.profile.name} | Starting logging in wallet to Mint')
        await connect_login_button.click(timeout=1000)
        rabby_page = await self.switch_to_extension_page(self.rabby_notification_url)
        await rabby_page.get_by_text('Sign and Create').click(timeout=1000)
        await rabby_page.get_by_text('Confirm').click(timeout=1000)
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


    async def get_page(self, page_title: str, page_url):
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
        for i in range(settings.RETRY_ATTEMPTS):
            try:
                await expect(connect_login_button).to_have_text('Connect')
                # expect(mint_page.get_by_text('Login')).not_to_be_visible()
            except:
                break
            try:
                await self.connect_wallet(connect_login_button)
            except:
                continue

        await asyncio.sleep(1)
        # Login wallet
        for i in range(settings.RETRY_ATTEMPTS):
            try:
                await expect(connect_login_button).to_have_text('Login')
            except:
                break
            try:
                await self.login_wallet(connect_login_button)
            except:
                continue


    async def all_preparations(self):
        mint_page = await self.get_page('Mint', self.mint_url)
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


    async def daily_bubble(self):
        mint_page = await self.all_preparations()

        for i in range(settings.RETRY_ATTEMPTS):
            try:
                logger.debug(f'Name: {self.profile.name} | {i} attempt popping bubble')
                # bubble = mint_page.locator('span.font-DINCond.font-medium.relative')

                # Вынес проверку страницы кошелька из-за лабуды со сменой сети
                rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=10000)
                if rabby_page:
                    await rabby_page.get_by_text('Sign and Create').click(timeout=10000)
                    await rabby_page.get_by_text('Confirm').click(timeout=1000)

                # Проверка выполнен ли уже пузырик
                try:
                    await mint_page.reload()
                    await asyncio.sleep(3)
                    pale_bubble = mint_page.locator(
                        '//div[@class="absolute flex items-center justify-center cursor-pointer max-h-[68px] max-w-[68px]'
                        ' z-[9999] select-none scale-100 translate-y-[-3px] bubble-wave text-[#AC9F8F]"]'
                    )
                    if pale_bubble and await pale_bubble.is_visible():
                        bubble_amount = int((await pale_bubble.text_content())[:4])
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

            except Exception as e:
                traceback.print_exc()
                logger.error(f"{str(e)[:200]}")
                continue


    async def mint_socials(self):
        mint_page = await self.all_preparations()

        parent_tasks_locator = mint_page.locator('//*[@id="forest-root"]/div[3]/div[4]/div[1]/div/div[2]/div[2]/div/div[2]/div')

        # try:
        #     expect(parent_tasks_locator).to_have_class("w-full flex-1 flex flex-col gap-8 max-h-[450px] lg:max-h-[unset] overflow-y-auto scroll-bar px-8")
        # except:
        #     parent_tasks_locator = mint_page.locator('//*[@id="forest-root"]/div[3]/div[3]/div[1]/div/div[2]/div[2]/div/div[2]/div')

        tasks_done = 0
        while True:
            try:
                # Повторно получаем первый доступный элемент с кнопкой "Go"
                task_button = parent_tasks_locator.locator('xpath=*').get_by_text('Go').first

                if task_button and await task_button.is_visible():
                    logger.debug(f"Name: {self.profile.name} | Кликаю по первому доступному task")
                    await task_button.click(timeout=1000)
                    # Если быстро кликать, то сайт выдает ошибку Frequent operations
                    await asyncio.sleep(randfloat(3, 7, 0.001))

                    twitter_task_page = self.close_new_page('x.com')

                    # Повторяем для кнопки "Verify"
                    verify_button = parent_tasks_locator.locator('xpath=*').get_by_text('Verify').last
                    if verify_button and verify_button.is_visible():
                        await verify_button.click(timeout=1000)
                        await asyncio.sleep(randfloat(3, 7, 0.001))
                        logger.success(f"Name: {self.profile.name} | Task выполнен")
                        tasks_done += 1
                else:
                    logger.info("Все задания выполнены.")
                    return tasks_done  # Если кнопки "Go" больше нет — выходим из цикла

            except Exception as e:
                print(e)
                continue


    async def lucky_roulette(self):
        mint_page = await self.all_preparations()

        lucky_button = mint_page.locator('//*[@id="forest-root"]/div[3]/div[2]/img[3]')
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
        # for i in range(1, 10):
            try:
                logger.debug(f"Name: {self.profile.name} | Запускаю бурмалду. Текущий счетчик спинов: {spin_count_str}")
                iterator_count += 1

                # почему-то spin_count_str до первого прокрута всегда 0/10 возвращает,
                # хотя там может быть и 1/10 и 10/10 и он будет тупить бесконечно
                # if iterator_count >= 10:
                #     logger.debug(
                #         f"Name: {self.profile.name} | Не получилось ничего прокрутить за 10 попыток, видимо на сегодня все")

                # _300_button.click(timeout=3000)
                # time.sleep(randfloat(3,6, 0.001))

                # rabby_page = self.switch_to_extension_page(self.rabby_notification_url, timeout_=5000)
                rabby_page = None
                while not rabby_page and not done:
                    await _300_button.click(timeout=3000)
                    try:
                        await expect(mint_page.get_by_text("You can't spin anymore today")).to_be_visible(timeout=5000)
                        done = True
                        # Fail to create
                    except:
                        pass
                    # time.sleep(randfloat(3, 6, 0.001))
                    rabby_page = await self.switch_to_extension_page(self.rabby_notification_url, timeout_=5000)

                if done:
                    logger.success(f"Name: {self.profile.name} | На сегодня все спины прокручены")
                    break

                try:
                    sign_button = rabby_page.get_by_text('Sign and Create')
                    await expect(sign_button).to_be_enabled(timeout=20000)
                    await sign_button.click(timeout=15000)
                    await rabby_page.get_by_text('Confirm').click(timeout=1000)
                except Exception as e:
                    logger.error(f"Name: {self.profile.name} | Не удалось подтвердить транзакцию в расширении {e} ")
                    continue

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

        if not amount_percent:
            amount_percent = randfloat(0.5, 0.75, 0.01)

        for i in range(settings.RETRY_ATTEMPTS):
            try:
                mint_energy_count_locator = mint_page.locator('//*[@id="inject-root"]/div[2]/span[1]')
                mint_energy = (await mint_energy_count_locator.text_content()).strip(' ME').replace(",", "")

                amount_to_spend = int(int(mint_energy) * amount_percent)

                await mint_energy_count_locator.click(timeout=3000)
                me_input = mint_page.locator('//*[@id="react-tiny-popover-container"]/div/div/div/div/div[4]/input')
                await me_input.fill(str(amount_to_spend))
                inject_button = mint_page.get_by_text('Inject ME')
                await expect(inject_button).to_be_enabled(timeout=3000)
                await inject_button.click(timeout=3000)

                await asyncio.sleep(1)
                logger.success(f"Name: {self.profile.name} | Injected {amount_to_spend} mint energy")
                break

            except Exception as e:
                logger.error(f"Name: {self.profile.name} | {e[:700]}")
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
        mint_page = await self.get_page('Mint', self.mint_url)
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
            check_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[2]/div[2]/button')
            await check_button.click(timeout=10000)
            # Проверяем галочку после нажатия чека
            await expect(mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[2]/div[2]/svg')).to_be_visible(timeout=10000)
        except Exception as e:
            logger.debug(f"Name: {self.profile.name} | {e}. Акк уже был регнут?")
            return True

        try:
            connect_twitter_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[3]/div[2]/button')
            await connect_twitter_button.click(timeout=10000)
            auth_button = mint_page.get_by_text('Authorize app')
            await auth_button.click(timeout=10000)
        except Exception as e:
            logger.error(f"Name: {self.profile.name} | {e}. Наверное не залогинен твиттер")
            # return False
            # Пока тут поставлю слип, чтобы можно было ручками зайти на подвисших акках
            await asyncio.sleep(1000)


        # Проверяем галочку коннекта твиттера
        await expect(mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[3]/div[2]/svg')).to_be_visible(timeout=10000)

        bind_button = mint_page.locator('//*[@id="forest-root"]/div/div[1]/div/div/div[4]/div[2]/button')
        await bind_button.click(timeout=10000)

        ref_code_input = mint_page.locator('/html/body/div[4]/div/div/div/div[2]/div/div/input')
        await ref_code_input.fill(ref_code)
        await mint_page.get_by_text('Join Now').click(timeout=10000)

        # In case for popups on forest page
        try:
            await expect(mint_page.get_by_text('New')).not_to_be_visible()
        except:
            await mint_page.get_by_text('Close').click(timeout=1000)


        logger.success(f"Name: {self.profile.name} | Регнул акк!")

        # Регаем дискорд
        await self.reg_discord(mint_page)

        return True


    async def reg_discord(self, mint_page: Page):
        logger.debug(f"Name: {self.profile.name} | Начинаю регать дискорд")
        go_discord_button = mint_page.locator('//*[@id="forest-root"]/div[3]/div[3]/div[1]/div/div[2]/div[2]/div/div[2]/div/div[2]/div[3]')
        await go_discord_button.click(timeout=10000)


        auth_button = mint_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div/div/div/div[2]/div/div/button')
        await auth_button.click(timeout=15000)
        await expect(go_discord_button).to_be_visible(timeout=20000)
        logger.debug(f"Name: {self.profile.name} | Авторизовал дискорд")

        await go_discord_button.click(timeout=10000)

        discord_page = await self.get_page('Discord', 'https://discord.com/invite/mint-blockchain')
        accept_invite_button = discord_page.locator('//*[@id="app-mount"]/div[2]/div[1]/div[1]/div/div[2]/div/div/div/section/div[2]/button/div')
        await accept_invite_button.click(timeout=10000)

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


'''
<span class="text-md text-[#00A637] font-normal mb-30">Congratulations on winning 100 ME</span>
<span class="text-[32px] font-extrabold text-white lg:text-tree-text -mt-6">1/10</span>
'''