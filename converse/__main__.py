import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import namedtuple

import smalld
from smalld import HttpError

from .names import random_name

logging.basicConfig(level=logging.INFO)


OngoingChat = namedtuple("OngoingChat", ["name", "output_channel"])
PendingChat = namedtuple("PendingChat", ["name", "input_channel"])


def call(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except:
        logging.exception("exception in handler")


class Bot:
    def __init__(self, smalld):
        self.smalld = smalld
        self.bot_id = smalld.get("/users/@me").id

        self.executor = ThreadPoolExecutor()
        # set of PendingChat
        self.pending = set()
        # mapping from input channel to OngoingChat
        self.ongoing = {}

        self.dispatch_table = {
            "++start": self.start,
            "++stop": self.stop,
        }

    def run(self):
        self.smalld.on_message_create(self.on_message)
        self.smalld.run()

    def send(self, channel, message):
        self.smalld.post(f"/channels/{channel}/messages", {"content": message})

    def send_multiple(self, *pairs):
        args = zip(*pairs)
        self.executor.map(self.send, *args)

    def get_dm(self, msg):
        return self.smalld.post(
            "/users/@me/channels", {"recipient_id": msg.author.id}
        ).id

    def start(self, msg):
        input_channel = self.get_dm(msg)
        name = random_name()
        try:
            anon_name, output_channel = self.pending.pop()
        except KeyError:
            self.pending.add(PendingChat(name, input_channel))
            self.send(input_channel, f"[=] Hello {name}. Hang on while we find a user.")
            return

        self.ongoing[output_channel] = OngoingChat(anon_name, input_channel)
        self.ongoing[input_channel] = OngoingChat(name, output_channel)

        message = f"{anon_name} connected."
        self.send_multiple(
            (input_channel, f"[=] Hello {name}. You are connected to {anon_name}."),
            (output_channel, f"[=] {name} connected."),
        )

    def stop(self, msg):
        input_channel = msg.channel_id

        try:
            user = self.ongoing.pop(input_channel)
            self.ongoing.pop(user.output_channel)
        except KeyError:
            self.send(input_channel, "[=] No ongoing chat.")
            return

        self.send_multiple(
            (input_channel, "[=] You have disconnected from chat."),
            (user.output_channel, f"[=] {user.name} have disconnected."),
        )

    def chat(self, msg):
        name, output_channel = self.ongoing[msg.channel_id]
        self.send(output_channel, f"{name}: {msg.content}")

    def on_message(self, msg):
        if self.bot_id == msg.author.id:
            return

        handler = None
        try:
            handler = self.dispatch_table[msg.content]
        except KeyError:
            if msg.channel_id in self.ongoing:
                handler = self.chat

        if handler is not None:
            self.executor.submit(call, handler, msg)


Bot(smalld.SmallD()).run()
