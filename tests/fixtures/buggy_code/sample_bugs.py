"""Sample buggy code for D-BUG testing — contains intentional bugs."""

import os
import sqlite3


def get_user(user_id):
    """Fetch user from database — SQL INJECTION vulnerability."""
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM users WHERE id = {user_id}"  # BUG: SQL injection
    result = conn.execute(query).fetchone()
    # BUG: connection never closed (resource leak)
    return result


def divide_numbers(a, b):
    """Divide two numbers — DIVISION BY ZERO bug."""
    return a / b  # BUG: no zero check


def process_list(items):
    """Process a list — OFF BY ONE error."""
    results = []
    for i in range(len(items) + 1):  # BUG: off-by-one, will crash
        results.append(items[i] * 2)
    return results


def read_config(filename):
    """Read config file — PATH TRAVERSAL vulnerability."""
    path = f"/etc/config/{filename}"  # BUG: no sanitization
    with open(path) as f:
        return f.read()


def run_command(user_input):
    """Execute a command — COMMAND INJECTION vulnerability."""
    os.system(f"echo {user_input}")  # BUG: command injection


def parse_age(value):
    """Parse age from string — bare except."""
    try:
        age = int(value)
        return age
    except:  # BUG: bare except hides real errors
        return 0


class UserCache:
    """Simple cache — RACE CONDITION bug."""

    def __init__(self):
        self.cache = {}
        self.count = 0

    def get_or_set(self, key, value):
        if key not in self.cache:
            # BUG: race condition — check-then-act without lock
            self.count += 1
            self.cache[key] = value
        return self.cache[key]
