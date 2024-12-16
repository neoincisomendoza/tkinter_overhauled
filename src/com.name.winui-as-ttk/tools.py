from contextlib import contextmanager
from time import time as timer

@contextmanager
def execution_timer():
    start_time = timer()

    try: yield
    finally:
        end_time = timer()
        print(f"Execution time: {(end_time - start_time):.10f} seconds")
