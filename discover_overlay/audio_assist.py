#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""A class to assist with reading pulseaudio changes"""
import os
import logging
import signal
import pulsectl_asyncio
import pulsectl
from contextlib import suppress
import asyncio
from threading import Thread, Event

log = logging.getLogger(__name__)


class DiscoverAudioAssist:
    def __init__(self, discover):

        self.thread = None
        self.enabled = False
        self.source = None  # String containing the name of the PA/PW microphone or other input
        self.sink = None  # String containing the name of the PA/PW output

        self.discover = discover

        # Keep last known state (or None) so that we don't repeatedly send messages for every little PA/PW signal
        self.last_set_mute = None
        self.last_set_deaf = None

    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self.start()

    def set_devices(self, sink, source):
        # Changed devices from client
        self.source = source
        self.sink = sink

    def start(self):
        if not self.enabled:
            return
        if not self.thread:
            self.thread = Thread(target=self.thread_loop)
            self.thread.start()

    def thread_loop(self):
        # Start an asyncio specific thread. Not the prettiest but I'm not rewriting from ground up for one feature
        log.info("Staring Audio subsystem assistance")
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.pulse_loop())
        log.info("Stopped Audio subsystem assistance")

    async def listen(self):
        # Async to connect to pulse and listen for events
        try:
            async with pulsectl_asyncio.PulseAsync('Discover-Monitor') as pulse:
                await self.get_device_details(pulse)
                async for event in pulse.subscribe_events('all'):
                    await self.print_events(pulse, event)
        except (pulsectl.pulsectl.PulseDisconnected):
            log.info("Pulse has gone away")
        except (pulsectl.pulsectl.PulseError):
            log.info("Pulse error")

    async def pulse_loop(self):
        # Prep before connecting to pulse
        loop = asyncio.get_event_loop()
        listen_task = asyncio.create_task(self.listen())
        with suppress(asyncio.CancelledError):
            await listen_task

    async def get_device_details(self, pulse):
        # Decant information about our chosen devices
        # Feed this back to client to change deaf/mute state
        mute = None
        deaf = None
        for sink in await pulse.sink_list():
            if sink.description == self.sink:
                if sink.mute == 1 or sink.volume.values[0] == 0.0:
                    deaf = True
                elif sink.mute == 0:
                    deaf = False

        if deaf != self.last_set_deaf:
            self.last_set_deaf = deaf
            self.discover.set_deaf_async(deaf)
            self.last_set_mute = None
            # At this point mute is undefined state

        for source in await pulse.source_list():
            if source.description == self.source:
                if source.mute == 1 or source.volume.values[0] == 0.0:
                    mute = True
                elif sink.mute == 0:
                    mute = False

        if mute != self.last_set_mute:
            self.last_set_mute = mute
            self.discover.set_mute_async(mute)

    async def print_events(self, pulse, ev):
        if not self.enabled:
            return
        # Sink and Source events are fired for changes to output and ints
        # Server is fired when default sink or source changes.
        match ev.facility:
            case 'sink':
                await self.get_device_details(pulse)

            case 'source':
                await self.get_device_details(pulse)

            case 'server':
                await self.get_device_details(pulse)

            case 'source_output':
                pass

            case 'sink_input':
                pass

            case 'client':
                pass

            case _:
                # If we need to find more events, this here will do it
                # log.info('Pulse event: %s' % ev)
                pass
