# import sys
import time
import os
import datetime

from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler


class AutoTest(PatternMatchingEventHandler):
    patterns = ["*.py"]

    def process(self, event):
        print('auto test', os.getcwd())
        print(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
        # print('='*20, 'flake8', '='*20)
        # os.system('flake8 --max-line-length=120')
        print('=' * 20, 'pytest', '=' * 20)
        os.system('pytest -q')

    def on_modified(self, event):
        self.process(event)


def main():
    path = '.'
    observer = Observer()
    observer.schedule(AutoTest(), path=path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == '__main__':
    main()
