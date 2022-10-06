#!/usr/bin/env Python3

import sys
import tty
import termios


def move_cursor(y, x):
    print("\033[%d;%dH" % (y, x))


def clear_screen():
    print("\033[2J")

def exit():
    print("Exiting...")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    old[3] = old[3] | termios.ECHO
    termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.exit(0)


def main():
    buffer = [""]
    line_no = 0  # Zero based
    column = 0  # Zero based
    tty.setcbreak(sys.stdin.fileno())
    print("Welcome to vibe a.k.a. vi Barebones Editor")
    while True:
        try:
            x = sys.stdin.read(1)
        except KeyboardInterrupt:
            exit()
        else:
            if x == "\12":
                line_no += 1
                buffer = buffer[:line_no] + [""] + buffer[line_no:]
                clear_screen()
                move_cursor(1, 1)
                print(buffer)
            else:
                buffer[line_no] += x
                clear_screen()
                move_cursor(1, 1)
                for line in buffer:
                    print(line)

if __name__ == "__main__":
    main()
    exit()