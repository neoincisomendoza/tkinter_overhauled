import tclinter

from tools import execution_timer

def main():
    tclinter.main()

def debug():
    with execution_timer():
        main()

if __name__ == '__main__':
    debug()
