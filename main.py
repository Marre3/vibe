#!/usr/bin/env python3

import sys
import copy

is_unix = True
try:
    # These modules don't exist
    # under the Windows version of 
    # Python3.
    import tty
    import termios
except ImportError:
    is_unix = False
    import msvcrt

def set_cursor_position(y, x):
    print("\033[%d;%dH" % (y, x))

def clear_screen():
    print("\033[2J")

def exit():
    print("Exiting...")
    if is_unix:
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        old[3] = old[3] | termios.ECHO
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.exit(0)


# Special constants that can be fed to an undoable function.
ACTION_NOOP = 0
ACTION_UNDO = 1
ACTION_REDO = 2

# Generates an undoable function.
# An undoable maintains state changes
# by ensuring all changes made to it are made using
# either a function or a special constant.
def new_undoable(starting_state):
    def fresh_copy():
        return copy.deepcopy(starting_state)

    history = []
    redo_stack = []
    state = fresh_copy()

    def run_action(action):
        # TODO: This could be optimized to create checkpoints for time consuming operations
        action(state)

    def remember_action(action):
        run_action(action)
        history.append(action)

    def remake_state(): 
        nonlocal state
        state = fresh_copy()
        for action in history:
            run_action(action)
        
    def undoable(action):
        nonlocal redo_stack
        if action == ACTION_UNDO:
            if len(history) > 0:
                undoed = history.pop()
                redo_stack.append(undoed)
                remake_state()
        elif action == ACTION_REDO:
            if len(redo_stack) > 0:
                redo = redo_stack.pop()
                remember_action(redo)
        elif action != ACTION_NOOP:
            remember_action(action)
            redo_stack = []
        return state

    return undoable


def print_splash():
    print("Welcome to ViBE a.k.a. Vi Barebones Editor")
    print("Type anything to begin")
    print("Ctrl+Z will undo, Ctrl+R will redo")

def get_key_or_exit():
    if is_unix:
        try:
            x = sys.stdin.read(1)
        except KeyboardInterrupt:
            exit()
    else:
        x = msvcrt.getch()
        if ord(x) == 3:
            exit() 
    return x


def clamp(minimum, maximum, value):
    """ Clamp a value to be within the range [minimum, maximum] """
    if value < minimum:
        return minimum
    elif value > maximum:
        return maximum
    else:
        return value

def no_op():
    pass

def main():
    column = 0  # Zero based
    buffer_action = new_undoable([""])
    line_no = 0  # Zero based
    def generate_generic_key(k):
        def key_action(state):
            nonlocal column
            state[line_no] = state[line_no][:column] + chr(k) + state[line_no][column:]
            column += 1
        def handler():
            buffer_action(key_action)
        return handler
    current_mode = "insert"

    # TODO: The insert keybindings could be generated by a separate function
    modes = {
        "insert": {k: generate_generic_key(k) for k in range(255)},
        "normal": {k: no_op for k in range(255)}
    }

    def action_newline(state):
        nonlocal line_no
        nonlocal column
        line_no = line_no + 1
        state.insert(line_no, "")
        column = 0
    modes["insert"][ord("\n" if is_unix else "\r")] = lambda: buffer_action(action_newline)
    modes["insert"][ord("\r" if is_unix else "\n")] = no_op

    def set_mode(mode):
        nonlocal current_mode
        current_mode = mode

    # Escape
    modes["insert"][27] = lambda: buffer_action(lambda state: set_mode("normal"))
    modes["normal"][ord("i")] = lambda: buffer_action(lambda state: set_mode("insert"))

    def move_cursor(c, l):
        nonlocal line_no
        nonlocal column
        line_no = clamp(0, len(buffer) - 1, line_no + l)
        column = clamp(0, len(buffer[line_no]), column + c)

    modes["normal"][ord("h")] = lambda: buffer_action(lambda state: move_cursor(-1, 0))
    modes["normal"][ord("l")] = lambda: buffer_action(lambda state: move_cursor(1, 0))
    modes["normal"][ord("j")] = lambda: buffer_action(lambda state: move_cursor(0, 1))
    modes["normal"][ord("k")] = lambda: buffer_action(lambda state: move_cursor(0, -1))

    def action_backspace(state):
        nonlocal line_no
        nonlocal column
        if len(state[line_no]):
            state[line_no] = state[line_no][:-1]
            column -= 1
        elif line_no != 0:
            del state[line_no]
            line_no -= 1
            column = len(state[line_no])
    modes["insert"][127 if is_unix else 8] = lambda: buffer_action(action_backspace)

    modes["insert"][26] = lambda: buffer_action(ACTION_UNDO)
    modes["insert"][24] = lambda: buffer_action(ACTION_REDO)
    modes["normal"][26] = lambda: buffer_action(ACTION_UNDO)
    modes["normal"][24] = lambda: buffer_action(ACTION_REDO)

    if is_unix:
        tty.setcbreak(sys.stdin.fileno())
    print_splash()
    while True:
        key = get_key_or_exit()
        modes[current_mode][ord(key)]()

        # Update screen
        clear_screen()
        set_cursor_position(1, 1)
        buffer = buffer_action(ACTION_NOOP)
        print(buffer)
        for line in buffer:
            print(line)
        print(ord(key))
        print(f"mode: {current_mode}")
        print(f"cursor: {line_no},{column}")

if __name__ == "__main__":
    main()
    exit()
