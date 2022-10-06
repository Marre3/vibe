#!/usr/bin/env Python3

import sys
import tty
import termios


def exit():
    print("Exiting...")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    old[3] = old[3] | termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.exit(0)

def main():
    tty.setcbreak(sys.stdin.fileno())

    print("Welcome to vibe a.k.a. vi Barebones Editor")
    while True:
        try:
            x = sys.stdin.read(1)
        except KeyboardInterrupt:
            exit()
        else:
            print(x, end="")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
    exit()