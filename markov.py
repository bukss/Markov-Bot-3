from collections import defaultdict
import random
from pprint import pformat

class Chunk:
    def __init__(self, value):
        self.value = value
        self.followers = defaultdict(int)
        self.cache = []
    
    def add_follower(self, follower):
        self.followers[follower] += 1

    def delete_follower(self, follower):
        if follower in self.followers:
            del self.followers[follower]

    def subtract_follower(self, follower, n=1):
        if follower in self.followers:
            if self.followers[follower] <= n:
                del self.followers[follower]
                return 0
            else:
                self.followers[follower] -= n
                return self.followers[follower]
        
        return 0

    def select_follower(self):
        total_followers = sum(self.followers.values())
        follower_ranges = []
        counter = 0
        for follower, count in self.followers.items():
            probability = count / total_followers
            follower_ranges.append((counter, counter + probability, follower))
            counter += probability
        selector = random.random()
        for lower_bound, upper_bound, follower in follower_ranges:
            if lower_bound <= selector < upper_bound:
                return follower
        try:
            return follower_ranges[-1][2]
        except IndexError as e:
            print(follower_ranges)
            print(repr(self))
            return None

    def __repr__(self):
        str_dict = {str(c): v for c, v in self.followers.items()}
        return f"({self.value}){pformat(str_dict)}"
    
    def __str__(self):
        return str(self.value)
    
    def __eq__(self, other):
        return self.value == other.value

    def __hash__(self):
        return hash(self.value)

class Model:
    def __init__(self):
        self.values = {} # value : chunk object
        self.starting_chunk = self.get_chunk(Exception("START"))
        self.stopping_chunk = self.get_chunk(Exception("STOP"))
    
    def _add_chunk(self, value):
        self.values[value] = Chunk(value)

    def get_chunk(self, value):
        if value not in self.values:
            self._add_chunk(value)
        return self.values[value]
    
    def remove_value(self, value):
        if value in self.values:
            bad_chunk = self.get_chunk(value)
            for chunk in self.values.values():
                chunk.delete_follower(bad_chunk)
            del self.values[value]

    def subtract_value(self, value, n=1):
        counter = 0
        if value in self.values:
            bad_chunk = self.get_chunk(value)
            for chunk in self.values.values():
                counter += chunk.subtract_follower(bad_chunk, n)
        
            if counter <= 0:
                del self.values[value]

    def process_data(self, data):
        chunks = [self.starting_chunk, *[self.get_chunk(d) for d in data], self.stopping_chunk]
        for i, chunk in enumerate(chunks[:-1]):
            next_chunk = chunks[i + 1]
            chunk.add_follower(next_chunk)

    def sanitize_model(self):
        for value, chunk in list(self.values.items()):
            if sum(chunk.followers.values()) == 0 \
               and chunk not in (self.starting_chunk, self.stopping_chunk):
                self.remove_value(value)

    def generate_chain(self, min_length=10, max_length=50, separator=" "):
        if not self.starting_chunk.followers:
            return "Unable to generate a chain at this time"

        self.sanitize_model()
        chain = []
        chunk = self.starting_chunk
        while len(chain) < max_length:
            chunk = chunk.select_follower()
            if not chunk:
                chunk = self.stopping_chunk
            if chunk == self.stopping_chunk:
                if len(chain) < min_length:
                    chunk = self.starting_chunk.select_follower()
                else:
                    break
            
            chain.append(chunk)

        return separator.join(str(c) for c in chain)

    def __repr__(self):
        return pformat(self.values.values()).replace("},", "},\n")