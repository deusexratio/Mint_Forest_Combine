import time
import traceback

from loguru import logger
import asyncio

from settings import concurrent_tasks
from utils import get_accounts_from_excel, print_stats


async def task(profile, profiles_stats, new_, no_green_id, semaphore, lock):
    while True:
        try:
            await profile.process(profiles_stats, new_, no_green_id, semaphore, lock)
            break # Запилил такую конструкцию для того чтобы если с профилем какие-то траблы он пытался еще раз

        except Exception as ex:
            traceback.print_exc()
            await asyncio.sleep(.3)
            logger.error(f'Name: {profile.name} {ex}')
            # time.sleep(1000)


async def main():
    profiles_stats = []
    excel_path = './profiles.xlsx'
    semaphore = asyncio.Semaphore(concurrent_tasks)
    lock = asyncio.Lock()

    match int(input('Menu: \n'
                '1) Регать новые акки \n'
                '2) Поддерживать новые акки до GreenID \n'
                '3) Обычные аккаунты с GreenID \n'
                '> ')):
        case 1:
            new_acc = True
            no_green_id = True
        case 2:
            new_acc = False
            no_green_id = True
        case _ :
            new_acc = False
            no_green_id = False

    profiles = get_accounts_from_excel(excel_path)
    tasks = [asyncio.create_task(task(profile, profiles_stats, new_acc, no_green_id, semaphore, lock)) for profile in profiles]
    await asyncio.wait(tasks)

    print_stats(profiles_stats)



if __name__ == '__main__':
    asyncio.run(main())
