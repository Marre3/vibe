#!/usr/bin/env python3

import os
import re
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
    print(f"\033[{y};{x}H", end="")
    sys.stdout.flush()

def clear_screen():
    print("\033[2J")

def exit():
    print("\nExiting...")
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
# Carried state is generated for each action.
def new_undoable(starting_state, carried_state_gen):
    def fresh_copy():
        return copy.deepcopy(starting_state)

    history = []
    redo_stack = []
    state = fresh_copy()

    def run_action(action_with_carried_state):
        # TODO: This could be optimized to create checkpoints for time consuming operations

        (action, carried_state) = action_with_carried_state
        action(state, carried_state)

    def remember_action(action_with_carried_state):
        run_action(action_with_carried_state)
        history.append(action_with_carried_state)

    def remake_state():
        nonlocal state
        state = fresh_copy()
        for action_with_carried_state in history:
            run_action(action_with_carried_state)

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
            remember_action((action, carried_state_gen()))
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

def main(argv):
    is_debug_mode = False
    column = 0  # Zero based
    line_no = 0  # Zero based
    command_buffer = ""

    def make_carried_state():
        return (column, line_no)

    def generate_generic_key(k):
        if 32 <= k < 127 or 128 <= k < 256:
            def key_action(state, carried):
                (c_column, c_line_no) = carried
                state[c_line_no] = state[c_line_no][:c_column] + chr(k) + state[c_line_no][c_column:]

                nonlocal column
                nonlocal line_no
                column = c_column + 1
                line_no = c_line_no
            def handler():
                buffer_action(key_action)
            return handler
        else:
            return no_op
    current_mode = "insert"

    def generate_command_keypress_function(k):
        if 32 <= k < 127 or 128 <= k < 256:
            def keypress_function():
                nonlocal command_buffer
                command_buffer += chr(k)
            return keypress_function
        else:
            return no_op

    # TODO: The insert keybindings could be generated by a separate function
    modes = {
        "insert": {k: generate_generic_key(k) for k in range(255)},
        "normal": {k: no_op for k in range(255)},
        "command": {k: generate_command_keypress_function(k) for k in range(255)},
    }

    def action_newline(state, carried):
        (c_column, c_line_no) = carried
        state.insert(c_line_no + 1, state[c_line_no][c_column:])
        state[c_line_no] = state[c_line_no][:c_column]

        nonlocal line_no
        nonlocal column
        line_no = c_line_no + 1
        column = 0
    modes["insert"][ord("\n" if is_unix else "\r")] = lambda: buffer_action(action_newline)
    modes["insert"][ord("\r" if is_unix else "\n")] = no_op

    def set_mode(mode):
        nonlocal current_mode
        current_mode = mode

    # Escape
    modes["insert"][27] = lambda: set_mode("normal")
    modes["command"][27] = lambda: set_mode("normal")
    modes["normal"][ord("i")] = lambda: set_mode("insert")
    modes["normal"][ord(":")] = lambda: set_mode("command")

    def move_cursor(c, l):
        state = buffer_action(ACTION_NOOP)
        nonlocal line_no
        nonlocal column
        line_no = clamp(0, len(state) - 1, line_no + l)
        column = clamp(0, len(state[line_no]), column + c)

    modes["normal"][ord("h")] = lambda: move_cursor(-1, 0)
    modes["normal"][ord("l")] = lambda: move_cursor(1, 0)
    modes["normal"][ord("j")] = lambda: move_cursor(0, 1)
    modes["normal"][ord("k")] = lambda: move_cursor(0, -1)

    def command_w(args):
        """ Write to file """
        nonlocal buffer_action
        buffer = buffer_action(ACTION_NOOP)
        if len(args) == 0:
            input("\nNo filename given... Press enter to continue.")
        elif not args.startswith(" "):
            input("\nMalformed write command... Press enter to continue.")
        else:
            filename = args[1:]
            try:
                with open(filename, "w") as f:
                    f.write("\n".join(buffer))
            except IOError:
                input(f"\nUnable to write to file {filename}... Press enter to continue.")

    def command_file(args):
        """ Open file """
        nonlocal buffer_action
        nonlocal line_no
        nonlocal column
        if len(args) == 0:
            input("\nNo filename given... Press enter to continue.")
        elif not args.startswith(" "):
            input("\nMalformed file command... Press enter to continue.")
        else:
            filename = args[1:]
            if os.path.exists(filename):
                try:
                    with open(filename, "r") as f:
                        contents = f.read()
                except IOError:
                    input(f"\nUnable to read file {filename}... Press enter to continue.")
                else:
                    buffer_action = new_undoable(contents.split("\n"), make_carried_state)
                    line_no = 0
                    column = 0
            else:
                input(f"\nFile {filename} not found... Press enter to continue.")

    def command_debug(args):
        """ Toggles debug mode """
        nonlocal is_debug_mode
        is_debug_mode = not is_debug_mode

    def command_search(args):
        nonlocal buffer_action
        nonlocal line_no
        nonlocal column
        buffer = buffer_action(ACTION_NOOP)
        for index, line in enumerate(buffer):
            match = re.search(args, line)
            if match:
                line_no = index
                column = match.span()[0]
                return

        input(f'\nNo match found for "{args}"... Press enter to continue.')


    def search_and_replace(buffer, search, replace):
        for index, line in enumerate(buffer):
            buffer[index] = re.sub(search, replace, line)


    def command_search_replace(args):
        nonlocal buffer_action
        if args.startswith("/"):
            search, replace = args[1:].split("/")
            def search_and_replace_action(state, carried):
                nonlocal column
                nonlocal line_no
                nonlocal search
                nonlocal replace
                search_and_replace(state, search, replace)
                (c_column, c_line_no) = carried
                column = clamp(0, len(state[c_line_no]), c_column)
                line_no = c_line_no
            buffer_action(search_and_replace_action)
        else:
            input("\nMalformed search-replace command... Press enter to continue.")


    commands = {
        "q": lambda args: exit(), # TODO: Check for unsaved changes?
        "w": command_w,
        "f": command_file,
        "file": command_file,
        "debug": command_debug,
        "/": command_search,
        "s": command_search_replace,
    }

    def run_command():
        nonlocal buffer_action
        nonlocal command_buffer
        cmd = command_buffer
        command_buffer = ""
        i = 0
        while i <= len(cmd):
            if cmd[:i] in commands:
                commands[cmd[:i]](cmd[i:])
                set_mode("normal")
                return
            i += 1

    def command_mode_backspace():
        nonlocal command_buffer
        if command_buffer:
            command_buffer = command_buffer[:-1]

    modes["command"][ord("\n" if is_unix else "\r")] = run_command
    modes["command"][ord("\r" if is_unix else "\n")] = no_op

    modes["command"][127 if is_unix else 8] = command_mode_backspace

    def action_backspace(state, carried):
        (c_column, c_line_no) = carried
        nonlocal line_no
        nonlocal column
        if len(state[c_line_no]) and c_column > 0:
            l = state[c_line_no][:c_column-1]
            h = state[c_line_no][c_column:]
            state[c_line_no] = l+h
            column = c_column - 1
            lind_no = c_line_no
        elif c_line_no != 0:
            del state[c_line_no]
            new_line_no = c_line_no - 1
            line_no = new_line_no
            column = len(state[new_line_no])
    modes["insert"][127 if is_unix else 8] = lambda: buffer_action(action_backspace)

    modes["insert"][26] = lambda: buffer_action(ACTION_UNDO)
    modes["insert"][24] = lambda: buffer_action(ACTION_REDO)
    modes["normal"][26] = lambda: buffer_action(ACTION_UNDO)
    modes["normal"][24] = lambda: buffer_action(ACTION_REDO)


    if is_unix:
        tty.setcbreak(sys.stdin.fileno())

    if len(argv) > 1:
        filename = argv[1]
        if os.path.exists(filename):
            with open(filename) as f:
                contents = f.read()
            lines = contents.split()
            if len(lines) == 0:
                lines.append("")
            buffer_action = new_undoable(lines, make_carried_state)
        else:
            input(f"File {filename} not found. Press enter to continue.")

        buffer = buffer_action(ACTION_NOOP)
        #for line in buffer:
        #    print(line)
    else:
        buffer_action = new_undoable([""], make_carried_state)
    if len(argv) == 1:
        # Only show splash screen if no file was specified
        clear_screen()
        set_cursor_position(1, 1)
        print_splash()
        get_key_or_exit()
    scroll = 0
    while True:
        # Update screen
        clear_screen()
        set_cursor_position(1, 1)
        buffer = buffer_action(ACTION_NOOP)
        terminal_size = os.get_terminal_size()
        height = terminal_size.lines - (7 if is_debug_mode else 3) # Leave some space at the bottom of screen
        if line_no >= scroll + height:
            scroll = line_no - height + 1
        if line_no < scroll:
            scroll = line_no
        for line in buffer[scroll:scroll + height]:
            print(line)
        if is_debug_mode:
            print(ord(key))
            print(buffer)
        print(f"mode: {current_mode}, cursor: {line_no},{column}")
        if current_mode == "command":
            print(f":{command_buffer}", end="")
            sys.stdout.flush()
        else:
            set_cursor_position(line_no + 1 - scroll, column + 1)

        key = get_key_or_exit()
        modes[current_mode][ord(key)]()


if __name__ == "__main__":
    main(sys.argv)
    exit()
