#! /usr/bin/env python
import discord
import re
import os
import sys
import time
import uuid

from collections import namedtuple
from deluge_client import DelugeRPCClient as DelugeClient
from tinydb import TinyDB, Query

active_servers = ["Discord Bot Testing", "Musty's Paradise"]
active_channels = ["deluge", "torrent-requests"]

authentication_channel = 617246314547118091
authentication_user = 162358113322663937

plex_channels = {
    'tv': 'TV',
    'weeb tv': 'Weeb TV',
    'movies': 'Movies',
}

Request = namedtuple('Request', ['magnet', 'channel', 'name', 'requester_name', 'requester_channel'])
queued_requests = {}

class DelugeBot(discord.Client):
    async def send_request(self, request):
        conn = DelugeClient('master.seedhost.eu', 21110, os.environ['DELUGE_USER'], os.environ['DELUGE_PASS'])
        conn.connect()
        torrent_id = conn.call('core.add_torrent_magnet', request.magnet, {'download_location': f'/home13/fufu/downloads/Watchtower/{request.channel}/{request.name}/'})

        with TinyDB('db') as db:
            db.insert({'requester_name': request.requester_name,
                       'torrent_id': torrent_id.decode(),
                       'torrent_name': request.name,
                       'time': int(time.time())})

    async def on_ready(self):
        print("Logged on as ", self.user)

    async def on_message(self, message):

        if message.author == self.user:
            return

        text = message.content.strip()

        if message.channel.id == authentication_channel and message.author.id == authentication_user:
            if text == "!stop":
                await sys.exit(1)
            if text == "!clear":
                global queued_requests
                queued_requests = {}
            if text in queued_requests:
                request = queued_requests[text]
                await self.send_request(request)
                await message.channel.send(f"Request approved: {text}")
                await request.requester_channel.send(f"The request for '{request.name}' has been approved!")
                del queued_requests[text]
            else:
                await message.channel.send("That uuid doesn't exist...")

        if not message.guild.name in active_servers:
            return

        if not message.channel.name in active_channels:
            return

        if text.lower().startswith("!add"):
            add_regex = "!add\nmagnet: *(magnet:\?[^ ]*)\nchannel: *([\w\d ]*)\nname: *([\w\d ]*)"
            regex = re.compile(add_regex, re.I | re.M)
            groups = regex.match(text)

            if groups is None:
                await message.channel.send("Not a valid '!add' command! Use '!help' if you are confused.")
                return 
            magnet = groups.group(1).strip()
            channel = groups.group(2).strip()
            name = groups.group(3).strip()
            requester_name = message.author.name + message.author.discriminator

            if channel.lower() in plex_channels:
                channel = plex_channels[channel.lower()]
            else:
                await message.channel.send(f"That's not a valid channel on plex! Please choose one of {plex_channels.values()}")
                return

            request = Request(magnet, channel, name, requester_name, message.channel)
            request_uuid = str(uuid.uuid4())
            queued_requests[request_uuid] = request

            auth_channel = self.get_channel(authentication_channel)
            await auth_channel.send(f"Request submitted:  {request}\n\n ID: {request_uuid}")
            await message.channel.send(f"Your request has been submitted, and is pending approval")

        elif text.lower().startswith("!status"):
            requester_name = message.author.name + message.author.discriminator
            now = time.time() 
            then = now - 24*60*60

            with TinyDB('db') as db:
                request = Query()
                torrents = db.search((request.requester_name == requester_name) & (request.time > then))

            status_string = f"Here's the status for all the approved torrents requested by {requester_name} in the last 24 hours:\n"
            conn = DelugeClient('master.seedhost.eu', 21110, os.environ['DELUGE_USER'], os.environ['DELUGE_PASS'])
            conn.connect()

            for torrent in torrents:
                torrent_name = torrent['torrent_name']
                torrent_id = torrent['torrent_id']

                status = conn.call('core.get_torrent_status', torrent_id, ['state', 'total_done', 'total_wanted'])
                if not b'state' in status:
                    continue
                state = status[b'state'].decode()
                total_done = status[b'total_done']
                total_wanted = status[b'total_wanted']
                status_string += "{:<35} {:>15}% completed\n".format(torrent_name, int(total_done/total_wanted*100))


            await message.channel.send(status_string)

        elif text.lower().startswith("!"):
            help_text_1 = \
            "This is a simple bot that will let you download torrents onto the Plex server, without having harass me " \
            "a ton. Right now, there are only 3 commands:\n" \
            "!add : Allows you to add torrents to the server. Usage is detailed below.\n" \
            "!status : Shows you the download status of all of the approved torrents you requested in the  " \
            "last 24 hours\n" \
            "!help : Shows this message!\n" \
            "\n" \
            "To use !add, you need to provide a information in a specific format. The three pieces of information " \
            "that you will need to provide are: 1) the magnet link to the desired torrent, 2) the plex channel that " \
            "you want the torrent to show up on (so, one of: TV, Movies, Weeb TV), and 3) the name of the media you're " \
            "downloading. This must be provided in a message the follows the given format: \n" \
            "\n" \
            "!add\n" \
            "magnet: <magnet link>\n" \
            "channel: <plex channel>\n" \
            "name: <name of thing>\n" \
            "\n" \
            "So, an example of a valid request would be:\n" \
            "\n" \
            "!add\n" \
            "magnet: magnet:?xt=urn:btih:52FD58172C296021F2E351B8A12BBC8BE7C88F8D&dn=Batman+Begins+%282005%29+1080p+BluRay+x264+-+1.6GB+-+YIFY&tr=udp%3A%2F%2Ftracker.yify-torrents.com%2Fannounce&tr=http%3A%2F%2Finferno.demonoid.me%3A3414%2Fannounce&tr=http%3A%2F%2Ftracker.yify-torrents.com%2Fannounce&tr=udp%3A%2F%2Ftracker.1337x.org%3A80%2Fannounce&tr=http%3A%2F%2Fexodus.desync.com%2Fannounce&tr=http%3A%2F%2Ft1.pow7.com%2Fannounce&tr=http%3A%2F%2Fexodus.desync.com%2Fannounce&tr=http%3A%2F%2Feztv.tracker.prq.to%2Fannounce&tr=http%3A%2F%2Fpow7.com%2Fannounce&tr=http%3A%2F%2Ftracker.torrent.to%3A2710%2Fannounce&tr=udp%3A%2F%2Ftracker.zer0day.to%3A1337%2Fannounce&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969%2Fannounce&tr=udp%3A%2F%2Fcoppersurfer.tk%3A6969%2Fannounce\n" \
            "channel: Movies\n" \
            "name: Batman Begins\n"
            
            help_text_2 = \
            "\nNote that this command will not immediately download the torrent. Instead, it will send me a message, " \
            "asking me if I think it's a responsible request. If I approve it, this bot will update this channel to " \
            "let you know its been approved. Only approved torrents will show up in !status.\n" \
            "\n" \
            "Last thing-- I literally wrote this in a couple of hours, and its not meant tp be super robust (yet!). " \
            "I will be continually improving and updating this bot, and I know that there are a few potential bugs, " \
            "as well as a bunch of features I wanna add, so if you hit any issues, just lemme know." 

            await message.channel.send(help_text_1)
            await message.channel.send(help_text_2)

token = os.environ['DISCORD_TOKEN']
if token:
    client = DelugeBot()
    client.run(token)
