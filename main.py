"""
SMMA Bot System — Main Entry Point
Triggers the entire system flow: init → Discord bot.
"""

from init import initialize, shutdown
from bot import DiscordBot


def main():
    if not initialize():
        shutdown(1)

    bot_inst = DiscordBot()
    bot_inst.run()


if __name__ == "__main__":
    main()
