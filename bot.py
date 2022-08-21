from multiprocessing import AuthenticationError
from markov import  Model
import socket
import json
import re
from collections import Counter
import time
from pprint import pprint
from random import choice

COLORS = ["Red", "Blue", "Green", "Firebrick", "Coral", "BlueViolet", "CadetBlue", "Chocolate",
    "DodgerBlue", "GoldenRod", "HotPink", "OrangeRed", "SeaGreen", "SpringGreen", "YellowGreen"]

class Bot:
    def __init__(self, config_file, logger):
        self.logger = logger
        self.model = Model()
        self.config_file = config_file
        self.set_config()
        self.cache = []
        self.set_blacklist()
        self.chat_counter = 0
        self.send_timer = time.time()
        self.reset_timer = time.time()

    def connect(self):
        self.logger.info("Connecting...")
        self.sock = socket.socket()
        self.sock.settimeout(None)
        self.sock.connect((self.host, self.port))
        self._send_raw("CAP REQ :twitch.tv/commands")
        self._send_raw(f"PASS {self.oauth}")
        self._send_raw(f"NICK {self.username}")
        self._send_raw(f"JOIN #{self.channel}")
        self._send_raw(f"JOIN #{self.command_channel}")

    def _send_raw(self, msg):
        self.logger.debug(f"Sending raw signal: {msg}")
        self.sock.send((msg + "\r\n").encode("utf-8"))

    def send(self, msg, channel):
        self._send_raw(f"PRIVMSG #{channel} :{msg}")

    def change_color(self):
        color = choice(COLORS)
        self.send(f"/color {color}", self.command_channel)

    def get_messages(self):
        try:
            data = self.sock.recv(4096).decode("utf-8")
            return data
        except socket.timeout:
            return None

    def run(self):
        while 1:
            try:
                self.connect()
                self._run_forever()
            except socket.timeout:
                self.logger.info("Timed out")
                time.sleep(1)
                continue
            except ConnectionError as e:
                self.logger.info(f"Disconnected by host")
                time.sleep(1)
                continue
            except AuthenticationError:
                self.logger.error("Authentication failed... shutting down")
                break
            except Exception as e:
                self.logger.exception(f"{type(e)}: {str(e)}")
            finally:
                self.sock.close()

    def _run_forever(self):
        while 1:
            message = self.get_messages()
            if message:
                for msg in message.splitlines():
                    self.handle_message(msg)

            if time.time() - self.reset_timer >= self.reset:
                self.reset_model()

    def run_dummy(self):
        while 1:
            if time.time() - self.reset_timer >= self.reset:
                self.reset_model()
            chat = input("> ")
            if chat == "!chain":
                print(self.model.generate_chain())
            elif chat == "!showblacklist":
                with open(self.blacklist_file, "r") as f:
                    pprint(json.load(f))
            elif chat == "!showconfig":
                with open(self.config_file, "r") as f:
                    pprint(json.load(f))
            elif chat == "!showmodel":
                print(repr(self.model))
            else:
                self.process_chat(chat, "buksss", "buksss")



    def handle_message(self, message):
        message_pattern = re.compile(r"^.*@(.*)\.tmi\.twitch\.tv PRIVMSG #(\w*) :(.*)$") # groups: name, channel, message
        clearchat_pattern = re.compile(r":tmi\.twitch\.tv CLEARCHAT #(\w*) :(.*)$") # groups: channel, name
        clearmsg_pattern = re.compile(r":tmi\.twitch\.tv CLEARMSG #(\w*) :(.*)$") # groups: channel, message
        user_banned_pattern = re.compile(r":tmi\.twitch\.tv NOTICE #(\w*) :(.*) is now banned from this channel\.") # groups : channel, name
        user_timed_out_pattern = re.compile(r":tmi\.twitch\.tv NOTICE #(\w*) :(.*) has been timed out for .*\.") # groups : channel, name
        
        if (m := re.match(message_pattern, message)):
            name, channel, msg = m.groups()
            self.logger.debug(f"#{channel} {name}: {msg}")
            self.process_chat(msg, name, channel)

        elif (m := re.match(clearchat_pattern, message)) \
          or (m := re.match(user_banned_pattern, message)) \
          or (m := re.match(user_timed_out_pattern, message)):
            channel, name = m.groups()
            self.logger.debug(f"{name} cleared, timed out, or banned")
            for author, chat in self.cache:
                if name.lower() == author.lower():
                    self.remove_chat(chat)

        elif (m := re.match(clearmsg_pattern, message)):
            channel, msg = m.groups()
            self.logger.debug(f"Message '{msg}' cleared in #{channel}")
            self.remove_chat(msg)
        
        elif message.startswith("PING :tmi.twitch.tv"):
            self.logger.debug("Received PING")
            self._send_raw("PONG :tmi.twitch.tv")
            return
            
        elif message.startswith("RECONNECT"):
            raise ConnectionError("Manually reconnecting")

        elif re.match(r":tmi\.twitch\.tv \d{3} .* :Welcome, GLHF!", message):
            self.logger.info("Connected successfully")

        elif re.match(r":tmi\.twitch\.tv NOTICE \* :Login authentication failed", message):
            raise AuthenticationError

        else:
            self.logger.debug(f"Received miscellaneous signal: {message}")

    def remove_chat(self, chat):
        self.logger.debug(f"Removing chat from model: {chat}")
        chat_words = Counter(chat.split())
        for value, count in chat_words.items():
            self.model.subtract_value(value, count)
        for author, msg in list(self.cache):
            if msg == chat:
                self.cache.remove((author, msg))

    def blacklisted(self, chat):
        chat = chat.lower()
        for phrase in self.blacklist["full_phrases"]:
            if phrase in chat:
                self.logger.debug(f"Chat contained blacklisted phrase '{phrase}': {chat}")
                return True
        
        for regex in self.blacklist["regex"]:
            if re.search(regex, chat):
                self.logger.debug(f"Chat contained blacklisted pattern '{regex}': {chat}")
                return True

        chat_words = chat.split()
        for word in self.blacklist["words"]:
            if word in chat_words:
                self.logger.debug(f"Chat contained blacklisted word '{word}': {chat}")
                return True
        
        return False

    def send_chain(self):
        self.chat_counter = 0
        self.send_timer = time.time()
        chain = self.model.generate_chain(self.minlength, self.maxlength)
        chain = chain[:self.maxchars]
        last_space = chain.rfind(" ") + 1
        chain = chain[:last_space]
        self.logger.info(f"Created chain: {chain}")
        self.send(chain, self.channel)

    def process_chat(self, chat, author, channel):
        command_pattern = r"^!(config|blacklist) (add|remove|set) (.*) (.*)$" # command, action, "field", "value"

        if author in self.ignored_users:
            return

        if (m := re.match(command_pattern, chat)):
            command, action, field, value = m.groups()
            if author.lower() in self.admins:
                result = self.handle_command(command, action, field, value)
            else:
                result = f"Non admin {author} tried to {action} {command} with '{value}' @ '{field}'"
            self.logger.info(f"User {author} tried to use a command with the following fields:\n Command: {command}\n Action: {action}\n Field: {field}\n Value: {value}\
\nResult: {result}")
            self.send(result, self.command_channel)
            return

        elif chat == "!reset":
            if author in self.admins:
                result = f"Admin {author} reset the model"
                self.reset_model()
            else:
                result = f"Non-admin {author} attempted to reset the model"
            self.logger.info(result)
            return

        elif chat.startswith("!markovbot"):
            if (time_since_chain := time.time() - self.send_timer) >= self.cooldown:
                message = f"{author}, Markov Chain Bot is a bot created by Buksss that imitates chat using a system called a Markov Chain. You can activate it by typing !chain, or by waiting for it to say something on its own"
                self.send(message, self.channel)
                self.logger.debug(f"User {author} used !markovbot")
                self.send_timer = time.time()
                self.change_color()
            else:
                self.logger.debug(f"!markovbot command unsuccessfully triggered with {self.cooldown - time_since_chain} seconds remaining")
            return

        elif chat.startswith("!chain"):
            if (time_since_chain := time.time() - self.send_timer) >= self.cooldown:
                self.logger.debug("Chain command successfully triggered")
                self.send_chain()
                self.change_color()
            else:
                self.logger.debug(f"Chain command unsuccessfully triggered with {self.cooldown - time_since_chain} seconds remaining")
            return

        chat_words = chat.split()
        if self.blacklisted(chat):
            return

        self.cache.append((author, chat))
        if len(self.cache) > self.cache_limit:
            del self.cache[0]
        self.chat_counter += 1
        self.model.process_data(chat_words)

        if self.chat_counter == self.autosend:
            self.send_chain()

    def handle_command(self, command, action, field, value):
        ADD_REMOVE_ABLES = ["admins", "ignored_users"]
        MUTABLE = ["autosend", "command_channel", "cache_limit",
                   "cooldown", "admins", "ignored_users", "reset", 
                   "admins", "minlength", "maxlength", "maxchars"]
        NUMERICALS = ["cache_limit", "cooldown", "autosend", "reset", "minlength", "maxlength", "maxchars"]
        if command == "blacklist":
        
            with open(self.blacklist_file, "r") as f:
                working_blacklist = json.load(f)
            if action == "add":
                try:
                    working_blacklist[field].append(value)
                    ret = f"Successfully added '{value}' to '{field}'"
                except KeyError:
                    return f"'{field}' is not a field in blacklist"
            elif action == "remove":
                try:
                    working_blacklist[field].remove(value)
                    ret = f"Successfully removed '{value}' from '{field}'"
                except KeyError:
                    return f"'{field}' is not a field in blacklist"
                except ValueError:
                    return f"'{value}' is not in field '{field}' of blacklist"
            else:
                return f"Cannot {action} in blacklist"
            
            with open(self.blacklist_file, "w+") as f:
                json.dump(working_blacklist, f, indent=2)
            self.set_blacklist()
        
        if command == "config":
            with open(self.config_file, "r") as f:
                working_config = json.load(f)

            if action != "set" and field not in ADD_REMOVE_ABLES:
                return f"Cannot {action} the field '{field}', please set instead"
            
            if action == "set" and field in ADD_REMOVE_ABLES:
                return f"Cannot set the field '{field}', please add or remove"
            
            if field not in MUTABLE:
                return f"Cannot change field '{field}', only {MUTABLE}"

            if field in NUMERICALS:
                try:
                    value = int(value)
                except ValueError:
                    return f"Field '{field}' accepts only numbers, not '{value}'"

            if action == "set":
                working_config[field] = value
                ret = f"Successfully set '{field}' to '{value}'"

            elif action == "add":
                if field in working_config:
                    working_config[field].append(value)
                    ret = f"Successfully added '{value}' to '{field}'"
                else:
                    return f"'{field}' is not in config"
            
            elif action == "remove":
                try:
                    working_config[field].remove(value)
                    ret = f"Successfully removed '{value}' from '{field}'"
                except ValueError:
                    return f"'{value}' is not in '{field}'"
            
            with open(self.config_file, "w+") as f:
                json.dump(working_config, f, indent=2)
            self.set_config()
        
        return ret

    def reset_model(self):
        self.logger.info("Resetting the model")
        self.reset_timer = time.time()
        self.model = Model()

    def set_config(self):
        self.logger.info("Setting config")
        with open(self.config_file, "r") as f:
            config = json.load(f)
        self.channel = config["channel"]
        self.oauth = config["oauth"]
        self.username = config["username"]
        self.clientid = config["clientid"]
        self.port = config["port"]
        self.host = config["host"]
        self.autosend = config["autosend"]
        self.command_channel = config["command_channel"]
        self.cache_limit = config["cache_limit"]
        self.blacklist_file = config["blacklist_file"]
        self.cooldown = config["cooldown"]
        self.admins = config["admins"]
        self.ignored_users = config["ignored_users"]
        self.reset = config["reset"]
        self.minlength = config["minlength"]
        self.maxlength = config["maxlength"]
        self.maxchars = config["maxchars"]

    def set_blacklist(self):
        self.logger.info("Setting blacklist")
        with open(self.blacklist_file, "r") as f:
            self.blacklist = json.load(f)
        for author, msg in self.cache:
            if self.blacklisted(msg):
                self.remove_chat(msg)