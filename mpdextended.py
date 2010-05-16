# -*- coding: utf-8 -*
#---------------------------------------------------------------------------{{{
# Copyright 2010 B. Kroon <bart@tarmack.eu>.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#------------------------------------------------------------------------------
# This module is intended as an extension on the mpdunicode module. It can be
# used to call idle() in a separate thread via idleThread(). idleThread()
# sets an event in a separate thread which sends the idle command to the server
# and waits. It will execute the callback function given in the first argument.
# The callback function is run from the spawned thread so make sure it only
# calls thread safe code, for instance set another event.
# Please note that the threaded idle mode deviates from the protocol by
# allowing any command while in idle mode. If the server is in idle mode any
# command other than noidle will be transparently prepended with the noidle
# command.
#---------------------------------------------------------------------------}}}
from mpdunicode import *
import threading
try:
    import WriteOut
    WriteOut.Quiet()
except ImportError:
    pass

class MPDClient(MPDClient):#{{{1
    '''This proxy class wraps round the mpdunicode module.
    It can be used to call idle() in a separate thread.'''
    def __init__(self):#{{{2
        self._thread = IdleThread(self)
        self._thread.start()
        self._lock = threading.RLock()
        super(MPDClient, self).__init__()

    def _docommand(self, command, args, retval):
        lock = False
        if command not in ('idle', 'noidle') and self._idle:
            self._writecommand('noidle', [])
        with self._lock:
            return super(MPDClient, self)._docommand(command, args, retval)

    def _writecommand(self, command, args=[]):
        if command.startswith('command_list') and self._idle:
            self._writecommand('noidle', [])
            with self._lock:
                super(MPDClient, self)._writecommand(command, args)
        else:
            super(MPDClient, self)._writecommand(command, args)

    def idleThread(self, callback, subsystems=[]):#{{{2
        self._thread.callback = callback
        self._thread.subsystems = subsystems
        if self._commandlist != None:
            raise CommandListError('idle command not allowed in command list.')
        self._thread.goidle.set()

    def connected(self):#{{{2
        if self._sock:
            try:
                self.ping()
                return True
            except:
                self.disconnect()
                return False
        else: return False

class IdleThread(threading.Thread):#{{{1
    def __init__(self, mpdclient):
        threading.Thread.__init__(self)
        self.daemon = True
        self.goidle = threading.Event()
        self.mpdclient = mpdclient

    def run(self):#{{{2
        while True:
            self.goidle.wait()
            with self.mpdclient._lock:
                # acquire lock so we are sure the idle results go to us.
                print 'debug: idling'
                try:
                    change = self.mpdclient.idle(self.subsystems)
                except ConnectionError:
                    print 'debug: idle ConnectionError'
                    change = 'ConnectionError'
                except socket.timeout:
                    print 'debug: idle timedout'
                    change = 'ConnectionError'
                    if self.mpdclient._idle:
                        try:
                            change = self.mpdclient.noidle()
                        except (ConnectionError, socket.timeout):
                            print 'debug: idle-noidle error'
                            change = 'ConnectionError'
                finally:
                    self.callback(change)
                    print 'debug: callback done'
            self.goidle.clear()


# vim: set expandtab shiftwidth=4 softtabstop=4:
