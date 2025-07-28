from dotenv import load_dotenv
load_dotenv()

import threading
from bot import run_bot1
from bot2 import run_bot2

if __name__ == "__main__":
    t1 = threading.Thread(target=run_bot1)
    t2 = threading.Thread(target=run_bot2)

    t1.start()
    t2.start()

    t1.join()
    t2.join()
