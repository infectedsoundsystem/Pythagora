# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------{{{
# Copyright 2009 E. A. Graham Jr. <txcrackers@gmail.com>.
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
#-------------------------------------------------------------------------------}}}
from PyQt4.QtCore import SIGNAL, Qt
from time import time
import operator

import songwidgets
import auxilia

#===============================================================================
class LibraryForm(auxilia.Actions):#{{{1
    '''List and controls for the full "library" of music known to the server.
       Note that this does not actually manage the filesystem or tags or covers.
       There are many other programs that do that exceedingly well already.
    '''
    def __init__(self, view, app, mpdclient, config):#{{{2
        self.app = app
        self.view = view
        self.mpdclient = mpdclient
        self.config = config
        self.view.connect(self.view,SIGNAL('reloadLibrary()'),self.reload)

        # Create 'MDP' menu.
        self.reloadLibrary = self.actionLibReload(self.view.menuMPD, self.reload)
        self.updateLibrary = self.actionLibUpdate(self.view.menuMPD, self.update)
        self.rescanLibrary = self.actionLibRescan(self.view.menuMPD, self.rescan)

        # search and filter functions
        view.connect(view.artistView,SIGNAL('itemSelectionChanged()'),self.artistFilter)
        view.connect(view.albumView,SIGNAL('itemSelectionChanged()'),self.albumFilter)

        view.connect(view.artistSearch,SIGNAL('textEdited(QString)'),self.artistSearch)
        view.connect(view.albumSearch,SIGNAL('textEdited(QString)'),self.albumSearch)
        view.connect(view.trackSearch,SIGNAL('textEdited(QString)'),self.trackSearch)

        # Double click actions.
        view.connect(view.artistView,SIGNAL('itemDoubleClicked(QListWidgetItem*)'),self.addArtist)
        view.connect(view.albumView,SIGNAL('itemDoubleClicked(QListWidgetItem*)'),self.addAlbum)
        view.connect(view.trackView,SIGNAL('itemDoubleClicked(QTreeWidgetItem*,int)'),self.addTrack)

# Create context menu's. {{{2
#==============================================================================

        # Create the actions for each window.
        self.artistPlayAdd = self.actionPlayAdd(self.view.artistView, self.__addPlayArtist)
        self.artistPlayReplace = self.actionPlayReplace(self.view.artistView, self.__clearPlayArtist)
        self.artistAdd = self.actionAddSongs(self.view.artistView, self.addArtist)

        self.albumPlayAdd = self.actionPlayAdd(self.view.albumView, self.__addPlayAlbum)
        self.albumPlayReplace = self.actionPlayReplace(self.view.albumView, self.__clearPlayAlbum)
        self.albumAdd = self.actionAddSongs(self.view.albumView, self.addAlbum)

        self.trackPlayAdd = self.actionPlayAdd(self.view.trackView, self.__addPlayTrack)
        self.trackPlayReplace = self.actionPlayReplace(self.view.trackView, self.__clearPlayTrack)
        self.trackAdd = self.actionAddSongs(self.view.trackView, self.addTrack)

#===========================================================================}}}

    def reload(self):#{{{2
        if not self.config.server or not self.mpdclient.connected():
            return
        try:
            # Emit signal to also reload playlists from server.
            self.view.emit(SIGNAL('reloadPlaylists()'))
            self.view.setCursor(Qt.WaitCursor)
            p = time()
            self.mainSongList = []
            self.artistdict = {}
            self.albumdict = {}
            self.albumlist = {}
            filesystemlist = {}
            # parse the list and prepare it for loading in the library browser and the file system view.
            mainlist = self.mpdclient.listallinfo()
            print 'library download took %.3f seconds' % (time() - p); t = time()
            for song in (x for x in mainlist if 'file' in x):
                self.mainSongList.append(song)
                album = song.get('album','?')
                artist = auxilia.songArtist(song)
                self.artistdict[artist] = self.artistdict.get(artist, [])+[song]
                self.albumdict[album] = self.albumdict.get(album, [])+[song]
                if not artist in self.albumlist.get(album, []):
                    self.albumlist[album] = self.albumlist.get(album, [])+[artist]

                # Build the file system tree.
                fslist = filesystemlist
                for part in song['file'].split('/'):
                    fslist[part] = fslist.get(part, {})
                    fslist = fslist[part]

            print 'library parsing took %.3f seconds' % (time() - t); t = time()
            self.__loadArtistView()
            print 'load Artist took %.3f seconds' % (time() - t); t = time()
            self.__loadAlbumView(self.albumlist)
            print 'load Album took %.3f seconds' % (time() - t); t = time()
            self.__loadTracksView(self.mainSongList)
            print 'load Tracks took %.3f seconds' % (time() - t); t = time()
            self.__loadFileSystemView(filesystemlist)
            print 'load FS took %.3f seconds' % (time() - t)
            print 'library load took %.3f seconds' % (time() - p)
        finally:
            self.view.setCursor(Qt.ArrowCursor)

    def __loadArtistView(self):#{{{2
        self.view.artistView.clear()
        self.view.artistView.setUpdatesEnabled(False)
        artists = self.artistdict.keys()
        artists.sort(auxilia.cmpUnicode)
        self.view.artistView.addItems(artists)
        self.view.artistView.insertItem(0, '--all--')
        self.artistSearch(self.view.artistSearch.text())
        self.view.artistView.setUpdatesEnabled(True)

    def __loadAlbumView(self, albumlist):#{{{2
        '''Reloads the list with the list presented'''
        self.view.albumView.clear()
        self.view.albumView.setUpdatesEnabled(False)
        for (album, artists) in sorted(albumlist.iteritems(), auxilia.cmpUnicode, operator.itemgetter(0)):
            albumWidget = songwidgets.simpleWidget(album, artists)
            self.view.albumView.addItem(albumWidget)
        self.view.albumView.insertItem(0, '--all--')
        self.albumSearch(self.view.albumSearch.text())
        self.view.albumView.setUpdatesEnabled(True)

    def __loadTracksView(self, tracks):#{{{2
        self.view.trackView.clear()
        self.view.trackView.setUpdatesEnabled(False)
        for track in tracks:
            trackWidget = songwidgets.TrackWidget(track)
            self.view.trackView.addTopLevelItem(trackWidget)
        if self.view.trackSearch.text() != '':
            self.trackSearch(self.view.trackSearch.text())
        self.view.trackView.setUpdatesEnabled(True)

    def __loadFileSystemView(self, filelist, parent=None):#{{{2
        update = True
        if not parent:
            self.view.filesystemTree.clear()
            parent = self.view.filesystemTree.invisibleRootItem()
            update = False
            self.view.filesystemTree.setUpdatesEnabled(False)
        for name in filelist.keys():
            item = songwidgets.fileWidget(name)
            parent.addChild(item)
            self.__loadFileSystemView(filelist[name], item)
        parent.sortChildren(0, 0)
        if not update:
            self.view.filesystemTree.setUpdatesEnabled(True)


    def artistFilter(self):#{{{2
        songlist = []
        albumlist = {}
        artists = self.view.artistView.selectedItems()
        if len(artists) < 1:
            self.__loadAlbumView(self.albumlist)
            self.__loadTracksView(self.mainSongList)
            return
        for artist in artists:
            artist = unicode(artist.text())
            if artist == '--all--':
                if '--all--' in (unicode(x.text()) for x in self.view.albumView.selectedItems()):
                    self.__loadTracksView(self.mainSongList)
                self.__loadAlbumView(self.albumlist)
                return
            artistsongs = self.artistdict[artist]
            songlist.extend(artistsongs)
            for song in artistsongs:
                #tup = (song.get('album', '?'), auxilia.songArtist(song))
                #if not tup in albumlist:
                #    albumlist.insert(0, tup)
                album = song.get('album', '?')
                if not artist in albumlist.get(album, []):
                    albumlist[album] = albumlist.get(album, [])+[artist]
        self.__loadAlbumView(albumlist)
        self.__loadTracksView(songlist)

    def albumFilter(self):#{{{2
        songlist = []
        albums = self.view.albumView.selectedItems()
        artists = [unicode(artist.text()) for artist in self.view.artistView.selectedItems()]
        if len(albums) < 1:
            self.__loadTracksView(self.mainSongList)
            return
        for album in albums:
            album = unicode(album.text())
            if album == '--all--':
                self.artistFilter()
                return
            if album.lower() == 'greatest hits' and artists: # If album is a greatest hits assume only one artist is on there.
                songlist.extend([song for song in self.albumdict[album] if auxilia.songArtist(song) in artists])
            else:
                songlist.extend(self.albumdict[album])
        self.__loadTracksView(songlist)

    def artistSearch(self, key):#{{{2
        self.__search(key, self.view.artistView)

    def albumSearch(self, key):#{{{2
        self.__search(key, self.view.albumView)

    def trackSearch(self, key):#{{{2
        hits = self.view.trackView.findItems(str(key), (Qt.MatchContains|Qt.MatchWrap), 1)[:]
        for x in xrange(self.view.trackView.topLevelItemCount()):
            self.view.trackView.topLevelItem(x).setHidden(True)
        for hit in hits:
            hit.setHidden(False)

    def __search(self, key, widget):#{{{2
        hits = widget.findItems(str(key), (Qt.MatchContains|Qt.MatchWrap))[:]
        for x in xrange(widget.count()):
            widget.item(x).setHidden(True)
        for hit in hits:
            hit.setHidden(False)

    def rescan(self):#{{{2
        '''rescan the library'''
        self.__scan(self.mpdclient.rescan())

    def update(self):#{{{2
        '''update the library'''
        self.__scan(self.mpdclient.update())

    def __scan(self, jobId):#{{{2
        '''Wait for the scan to finish, while waiting keep processing events.'''
        self.view.setCursor(Qt.BusyCursor)
        try:
            while True:
                self.app.processEvents()
                status = self.mpdclient.status()
                if status.get('updating_db',None) != jobId:
                    break
        finally:
            self.reload()

    def addArtist(self):#{{{2
        '''Add all songs from the currently selected artist into the current playlist'''
        return self.__addSongSet('artist', self.view.artistView.selectedItems())

    def addAlbum(self):#{{{2
        '''Add all songs from the currently selected album into the current playlist'''
        return self.__addSongSet('album', self.view.albumView.selectedItems())

    def __addSongSet(self, key, selection):#{{{2
        first = None
        for item in selection:
            for song in self.mpdclient.find(key,unicode(item.text())):
                self.mpdclient.add(song['file'])
                if not first:
                    first = self.mpdclient.playlistid()[-1]['id']
        self.view.emit(SIGNAL('playlistChanged()'))
        return first

    def addTrack(self):#{{{2
        '''Add all selected songs into the current playlist'''
        first = None
        for item in self.view.trackView.selectedItems():
            self.mpdclient.add(item.song['file'])
            if not first:
                first = self.mpdclient.playlistid()[-1]['id']
        self.view.emit(SIGNAL('playlistChanged()'))
        return first


    def __addPlayArtist(self):#{{{2
        try:
            self.mpdclient.playid(self.addArtist())
        except:
            pass

    def __clearPlayArtist(self):#{{{2
        self.mpdclient.clear()
        self.__addPlayArtist()

    def __addPlayAlbum(self):#{{{2
        try:
            self.mpdclient.playid(self.addAlbum())
        except:
            pass

    def __clearPlayAlbum(self):#{{{2
        self.mpdclient.clear()
        self.__addPlayAlbum()


    def __addPlayTrack(self):#{{{2
        try:
            self.mpdclient.playid(self.addTrack())
        except:
            pass

    def __clearPlayTrack(self):#{{{2
        self.mpdclient.clear()
        self.__addPlayTrack()


# vim: set expandtab shiftwidth=4 softtabstop=4:
