# -*- coding: utf-8 -*-
import datetime
import logging

import database.queries
import database.emby_db
import helper.wrapper
import helper.api
from . import obj_ops
from . import queries_music
from . import artwork
from . import common

class Music():
    def __init__(self, server, embydb, musicdb, direct_path, Utils):
        self.LOG = logging.getLogger("EMBY.core.music.Music")
        self.Utils = Utils
        self.server = server
        self.emby = embydb
        self.music = musicdb
        self.emby_db = database.emby_db.EmbyDatabase(self.emby.cursor)
        self.objects = obj_ops.Objects(self.Utils)
        self.item_ids = []
        self.DBVersion = int(self.Utils.window('kodidbverion.music'))
        self.Common = common.Common(self.emby_db, self.objects, self.Utils, direct_path, self.server)
        self.MusicDBIO = MusicDBIO(self.music.cursor, int(self.Utils.window('kodidbverion.music')))
        self.ArtworkDBIO = artwork.Artwork(musicdb.cursor, self.Utils)

        if not self.Utils.settings('MusicRescan.bool'):
            self.MusicDBIO.disable_rescan()
            self.Utils.settings('MusicRescan.bool', True)

    def __getitem__(self, key):
        if key in ('MusicArtist', 'AlbumArtist'):
            return self.artist
        elif key == 'MusicAlbum':
            return self.album
        elif key == 'Audio':
            return self.song

    #If item does not exist, entry will be added.
    #If item exists, entry will be updated
    @helper.wrapper.stop
    def artist(self, item, library=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Artist')
        update = True

        try:
            obj['ArtistId'] = e_item[0]
        except TypeError:
            update = False
            obj['ArtistId'] = None
            self.LOG.debug("ArtistId %s not found", obj['Id'])
        else:
            if self.MusicDBIO.validate_artist(*self.Utils.values(obj, queries_music.get_artist_by_id_obj)) is None:
                update = False
                self.LOG.info("ArtistId %s missing from kodi. repairing the entry.", obj['ArtistId'])

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['ArtistType'] = "MusicArtist"
        obj['Genre'] = " / ".join(obj['Genres'] or [])
        obj['Bio'] = API.get_overview(obj['Bio'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['Backdrops'] = obj['Artwork']['Backdrop'] or ""

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if obj['Backdrops']:
            obj['Backdrops'] = "<fanart>%s</fanart>" % obj['Backdrops'][0]

        if obj['DateAdded']:
            obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if update:
            self.artist_update(obj)
        else:
            self.artist_add(obj)

        if self.DBVersion >= 82:
            self.MusicDBIO.update(obj['Genre'], obj['Bio'], obj['Thumb'], obj['LastScraped'], obj['SortName'], obj['DateAdded'], obj['ArtistId'])
        else:
            self.MusicDBIO.update(obj['Genre'], obj['Bio'], obj['Thumb'], obj['Backdrops'], obj['LastScraped'], obj['SortName'], obj['ArtistId'])

        self.ArtworkDBIO.add(obj['Artwork'], obj['ArtistId'], "artist")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    #safety checks: It looks like Emby supports the same artist multiple times.
    #Kodi doesn't allow that. In case that happens we just merge the artist entries
    def artist_add(self, obj):
        obj['ArtistId'] = self.MusicDBIO.get(*self.Utils.values(obj, queries_music.get_artist_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_artist_obj))
        self.LOG.info("ADD artist [%s] %s: %s", obj['ArtistId'], obj['Name'], obj['Id'])

    #Update object to kodi
    def artist_update(self, obj):
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE artist [%s] %s: %s", obj['ArtistId'], obj['Name'], obj['Id'])

    #Update object to kodi
    @helper.wrapper.stop
    def album(self, item, library=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Album')
        update = True

        try:
            obj['AlbumId'] = e_item[0]
        except TypeError:
            update = False
            obj['AlbumId'] = None
            self.LOG.debug("AlbumId %s not found", obj['Id'])
        else:
            if self.MusicDBIO.validate_album(*self.Utils.values(obj, queries_music.get_album_by_id_obj)) is None:
                update = False

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Rating'] = 0
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['Genres'] = obj['Genres'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Bio'] = API.get_overview(obj['Bio'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']

        if obj['DateAdded']:
            obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if update:
            self.album_update(obj)
        else:
            self.album_add(obj)

        self.artist_link(obj)
        self.artist_discography(obj)

        if self.DBVersion >= 82:
            self.MusicDBIO.update_album(*self.Utils.values(obj, queries_music.update_album_obj82))
        else:
            self.MusicDBIO.update_album(*self.Utils.values(obj, queries_music.update_album_obj))

        self.ArtworkDBIO.add(obj['Artwork'], obj['AlbumId'], "album")
        self.item_ids.append(obj['Id'])
        return not update

    #Add object to kodi
    def album_add(self, obj):
        obj['AlbumId'] = self.MusicDBIO.get_album(*self.Utils.values(obj, queries_music.get_album_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_album_obj))
        self.LOG.info("ADD album [%s] %s: %s", obj['AlbumId'], obj['Title'], obj['Id'])

    #Update object to kodi
    def album_update(self, obj):
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE album [%s] %s: %s", obj['AlbumId'], obj['Title'], obj['Id'])

    #Update the artist's discography
    def artist_discography(self, obj):
        for artist in (obj['ArtistItems'] or []):
            temp_obj = dict(obj)
            temp_obj['Id'] = artist['Id']
            temp_obj['AlbumId'] = obj['Id']

            try:
                temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
            except TypeError:
                continue

            self.MusicDBIO.add_discography(*self.Utils.values(temp_obj, queries_music.update_discography_obj))
            self.emby_db.update_parent_id(*self.Utils.values(temp_obj, database.queries.update_parent_album_obj))

    #Assign main artists to album.
    #Artist does not exist in emby database, create the reference
    def artist_link(self, obj):
        for artist in (obj['AlbumArtists'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']

            try:
                temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
            except TypeError:
                try:
                    self.artist(self.server['api'].get_item(temp_obj['Id']), library=None)
                    temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
                except Exception as error:
                    self.LOG.error(error)
                    continue

            self.MusicDBIO.update_artist_name(*self.Utils.values(temp_obj, queries_music.update_artist_name_obj))
            self.MusicDBIO.link(*self.Utils.values(temp_obj, queries_music.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

    #Update object to kodi
    @helper.wrapper.stop
    def song(self, item, library=None):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        library = self.Common.library_check(e_item, item, library)

        if not library:
            return False

        API = helper.api.API(item, self.Utils, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Song')
        update = True

        try:
            obj['SongId'] = e_item[0]
            obj['PathId'] = e_item[2]
            obj['AlbumId'] = e_item[3]
        except TypeError:
            update = False
            obj['SongId'] = self.MusicDBIO.create_entry_song()
            self.LOG.debug("SongId %s not found", obj['Id'])
        else:
            if self.MusicDBIO.validate_song(*self.Utils.values(obj, queries_music.get_song_by_id_obj)) is None:
                update = False

        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Path'] = API.get_file_path(obj['Path'])
        obj = self.Common.get_path_filename(obj, "audio")
        obj['Rating'] = 0
        obj['Genres'] = obj['Genres'] or []
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Runtime'] = (obj['Runtime'] or 0) / 10000000.0
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['AlbumArtists'] = obj['AlbumArtists'] or []
        obj['Index'] = obj['Index'] or 0
        obj['Disc'] = obj['Disc'] or 1
        obj['EmbedCover'] = False
        obj['Comment'] = API.get_overview(obj['Comment'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']

        if obj['DateAdded']:
            obj['DateAdded'] = self.Utils.convert_to_local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['DatePlayed']:
            obj['DatePlayed'] = self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        if obj['Disc'] != 1:
            obj['Index'] = obj['Disc'] * 2 ** 16 + obj['Index']

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if update:
            self.song_update(obj)
        else:
            self.song_add(obj)

        self.MusicDBIO.add_role(*self.Utils.values(obj, queries_music.update_role_obj)) # defaultt role
        self.song_artist_link(obj)
        self.song_artist_discography(obj)
        obj['strAlbumArtists'] = " / ".join(obj['AlbumArtists'])
        self.MusicDBIO.get_album_artist(*self.Utils.values(obj, queries_music.get_album_artist_obj))
        self.MusicDBIO.add_genres(*self.Utils.values(obj, queries_music.update_genre_song_obj))
        self.ArtworkDBIO.add(obj['Artwork'], obj['SongId'], "song")
        self.item_ids.append(obj['Id'])

        if obj['SongAlbumId'] is None:
            self.ArtworkDBIO.add(obj['Artwork'], obj['AlbumId'], "album")

        return not update

    #Add object to kodi.
    #Verify if there's an album associated.
    #If no album found, create a single's album
    def song_add(self, obj):
        obj['PathId'] = self.MusicDBIO.add_path(obj['Path'])

        try:
            obj['AlbumId'] = self.emby_db.get_item_by_id(*self.Utils.values(obj, database.queries.get_item_song_obj))[0]
        except TypeError:
            try:
                if obj['SongAlbumId'] is None:
                    raise TypeError("No album id found associated?")

                self.album(self.server['api'].get_item(obj['SongAlbumId']))
                obj['AlbumId'] = self.emby_db.get_item_by_id(*self.Utils.values(obj, database.queries.get_item_song_obj))[0]
            except TypeError:
                self.single(obj)

        self.MusicDBIO.add_song(*self.Utils.values(obj, queries_music.add_song_obj))
        self.emby_db.add_reference(*self.Utils.values(obj, database.queries.add_reference_song_obj))
        self.LOG.info("ADD song [%s/%s/%s] %s: %s", obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title'])

    #Update object to kodi
    def song_update(self, obj):
        self.MusicDBIO.update_path(*self.Utils.values(obj, queries_music.update_path_obj))
        self.MusicDBIO.update_song(*self.Utils.values(obj, queries_music.update_song_obj))
        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("UPDATE song [%s/%s/%s] %s: %s", obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title'])

    #Update the artist's discography
    def song_artist_discography(self, obj):
        artists = []

        for artist in (obj['AlbumArtists'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            artists.append(temp_obj['Name'])

            try:
                temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
            except TypeError:
                try:
                    self.artist(self.server['api'].get_item(temp_obj['Id']), library=None)
                    temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
                except Exception as error:
                    self.LOG.error(error)
                    continue

            self.MusicDBIO.link(*self.Utils.values(temp_obj, queries_music.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

            if obj['Album']:
                temp_obj['Title'] = obj['Album']
                temp_obj['Year'] = 0
                self.MusicDBIO.add_discography(*self.Utils.values(temp_obj, queries_music.update_discography_obj))

        obj['AlbumArtists'] = artists

    #Assign main artists to song.
    #Artist does not exist in emby database, create the reference
    def song_artist_link(self, obj):
        for index, artist in enumerate(obj['ArtistItems'] or []):
            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            temp_obj['Index'] = index

            try:
                temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
            except TypeError:
                try:
                    self.artist(self.server['api'].get_item(temp_obj['Id']), library=None)
                    temp_obj['ArtistId'] = self.emby_db.get_item_by_id(*self.Utils.values(temp_obj, database.queries.get_item_obj))[0]
                except Exception as error:
                    self.LOG.error(error)
                    continue

            self.MusicDBIO.link_song_artist(*self.Utils.values(temp_obj, queries_music.update_song_artist_obj))
            self.item_ids.append(temp_obj['Id'])

    def single(self, obj):
        obj['AlbumId'] = self.MusicDBIO.create_entry_album()
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if self.DBVersion >= 82:
            self.MusicDBIO.add_single(*self.Utils.values(obj, queries_music.add_single_obj82))
        else:
            self.MusicDBIO.add_single(*self.Utils.values(obj, queries_music.add_single_obj))

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    @helper.wrapper.stop
    def userdata(self, item):
        e_item = self.emby_db.get_item_by_id(item['Id'])
        obj = self.objects.map(item, 'SongUserData')

        try:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        obj['Rating'] = 0

        if obj['Media'] == 'song':
            if obj['DatePlayed']:
                obj['DatePlayed'] = self.Utils.convert_to_local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            self.MusicDBIO.rate_song(*self.Utils.values(obj, queries_music.update_song_rating_obj))

        self.emby_db.update_reference(*self.Utils.values(obj, database.queries.update_reference_obj))
        self.LOG.info("USERDATA %s [%s] %s: %s", obj['Media'], obj['KodiId'], obj['Id'], obj['Title'])

    #This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
    #Poster with progress bar
    #This should address single song scenario, where server doesn't actually create an album for the song
    @helper.wrapper.stop
    def remove(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        if obj['Media'] == 'song':
            self.remove_song(obj['KodiId'], obj['Id'])
            self.emby_db.remove_wild_item(obj['Id'])

            for item in self.emby_db.get_item_by_wild_id(*self.Utils.values(obj, database.queries.get_item_by_wild_obj)):
                if item[1] == 'album':
                    temp_obj = dict(obj)
                    temp_obj['ParentId'] = item[0]

                    if not self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                        self.remove_album(temp_obj['ParentId'], obj['Id'])

        elif obj['Media'] == 'album':
            obj['ParentId'] = obj['KodiId']

            for song in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_song_obj)):
                self.remove_song(song[1], obj['Id'])

            self.emby_db.remove_items_by_parent_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_song_obj))
            self.remove_album(obj['KodiId'], obj['Id'])
        elif obj['Media'] == 'artist':
            obj['ParentId'] = obj['KodiId']

            for album in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_album_obj)):
                temp_obj = dict(obj)
                temp_obj['ParentId'] = album[1]

                for song in self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                    self.remove_song(song[1], obj['Id'])

                self.emby_db.remove_items_by_parent_id(*self.Utils.values(temp_obj, database.queries.delete_item_by_parent_song_obj))
                self.emby_db.remove_items_by_parent_id(*self.Utils.values(temp_obj, database.queries.delete_item_by_parent_artist_obj))
                self.remove_album(temp_obj['ParentId'], obj['Id'])

            self.emby_db.remove_items_by_parent_id(*self.Utils.values(obj, database.queries.delete_item_by_parent_album_obj))
            self.remove_artist(obj['KodiId'], obj['Id'])

        self.emby_db.remove_item(*self.Utils.values(obj, database.queries.delete_item_obj))

    def remove_artist(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "artist")
        self.MusicDBIO.delete(kodi_id)
        self.LOG.info("DELETE artist [%s] %s", kodi_id, item_id)

    def remove_album(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "album")
        self.MusicDBIO.delete_album(kodi_id)
        self.LOG.info("DELETE album [%s] %s", kodi_id, item_id)

    def remove_song(self, kodi_id, item_id):
        self.ArtworkDBIO.delete(kodi_id, "song")
        self.MusicDBIO.delete_song(kodi_id)
        self.LOG.info("DELETE song [%s] %s", kodi_id, item_id)

    #Get all child elements from tv show emby id
    def get_child(self, item_id):
        e_item = self.emby_db.get_item_by_id(item_id)
        obj = {'Id': item_id}
        child = []

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        except TypeError:
            return child

        obj['ParentId'] = obj['KodiId']

        for album in self.emby_db.get_item_by_parent_id(*self.Utils.values(obj, database.queries.get_item_by_parent_album_obj)):
            temp_obj = dict(obj)
            temp_obj['ParentId'] = album[1]
            child.append((album[0],))

            for song in self.emby_db.get_item_by_parent_id(*self.Utils.values(temp_obj, database.queries.get_item_by_parent_song_obj)):
                child.append((song[0],))

        return child

class MusicDBIO():
    def __init__(self, cursor, MusicDBVersion):
        self.LOG = logging.getLogger("EMBY.core.music.Music")
        self.cursor = cursor
        self.DBVersion = MusicDBVersion

    #Make sure rescan and kodi db set
    def disable_rescan(self):
        self.cursor.execute(queries_music.delete_rescan)
        Data = [str(self.DBVersion), "0"]
        self.cursor.execute(queries_music.disable_rescan, Data)

    #Leia has a dummy first entry
    #idArtist: 1  strArtist: [Missing Tag]  strMusicBrainzArtistID: Artist Tag Missing
    def create_entry(self):
        self.cursor.execute(queries_music.create_artist)
        return self.cursor.fetchone()[0] + 1

    def create_entry_album(self):
        self.cursor.execute(queries_music.create_album)
        return self.cursor.fetchone()[0] + 1

    def create_entry_song(self):
        self.cursor.execute(queries_music.create_song)
        return self.cursor.fetchone()[0] + 1

    def create_entry_genre(self):
        self.cursor.execute(queries_music.create_genre)
        return self.cursor.fetchone()[0] + 1

    def update_path(self, *args):
        self.cursor.execute(queries_music.update_path, args)

    def add_role(self, *args):
        self.cursor.execute(queries_music.update_role, args)

    #Get artist or create the entry
    def get(self, artist_id, name, musicbrainz):
        try:
            self.cursor.execute(queries_music.get_artist, (musicbrainz,))
            result = self.cursor.fetchone()
            artist_id = result[0]
            artist_name = result[1]
        except TypeError:
            artist_id = self.add_artist(artist_id, name, musicbrainz)
        else:
            if artist_name != name:
                self.update_artist_name(artist_id, name)

        return artist_id

    #Safety check, when musicbrainz does not exist
    def add_artist(self, artist_id, name, *args):
        try:
            self.cursor.execute(queries_music.get_artist_by_name, (name,))
            artist_id = self.cursor.fetchone()[0]
        except TypeError:
            artist_id = artist_id or self.create_entry()
            self.cursor.execute(queries_music.add_artist, (artist_id, name,) + args)

        return artist_id

    def update_artist_name(self, *args):
        self.cursor.execute(queries_music.update_artist_name, args)

    def update(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.update_artist82, args)
        else:
            self.cursor.execute(queries_music.update_artist, args)

    def link(self, *args):
        self.cursor.execute(queries_music.update_link, args)

    def add_discography(self, *args):
        self.cursor.execute(queries_music.update_discography, args)

    def validate_artist(self, *args):
        try:
            self.cursor.execute(queries_music.get_artist_by_id, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def validate_album(self, *args):
        try:
            self.cursor.execute(queries_music.get_album_by_id, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def validate_song(self, *args):
        try:
            self.cursor.execute(queries_music.get_song_by_id, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_album(self, album_id, name, musicbrainz, artists=None, *args):
        try:
            if musicbrainz is not None:
                self.cursor.execute(queries_music.get_album, (musicbrainz,))
                album = None
            else:
                self.cursor.execute(queries_music.get_album_by_name, (name,))
                album = self.cursor.fetchone()

            album_id = (album or self.cursor.fetchone())[0]
        except TypeError:
            album_id = self.add_album(*(album_id, name, musicbrainz,) + args)

        return album_id

    def add_album(self, album_id, *args):
        album_id = album_id or self.create_entry_album()
        self.cursor.execute(queries_music.add_album, (album_id,) + args)
        return album_id

    def update_album(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.update_album82, args)
        else:
            self.cursor.execute(queries_music.update_album, args)

    def get_album_artist(self, album_id, artists):
        try:
            self.cursor.execute(queries_music.get_album_artist, (album_id,))
            curr_artists = self.cursor.fetchone()[0]
        except TypeError:
            return

        if curr_artists != artists:
            self.update_album_artist(artists, album_id)

    def update_album_artist(self, *args):
        self.cursor.execute(queries_music.update_album_artist, args)

    def add_single(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.add_single82, args)
        else:
            self.cursor.execute(queries_music.add_single, args)

    def add_song(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.add_song82, args)
        else:
            self.cursor.execute(queries_music.add_song, args)

    def update_song(self, *args):
        if self.DBVersion >= 82:
            self.cursor.execute(queries_music.update_song82, args)
        else:
            self.cursor.execute(queries_music.update_song, args)

    def link_song_artist(self, *args):
        self.cursor.execute(queries_music.update_song_artist, args)

#    def link_song_album(self, *args):
#        self.cursor.execute(queries_music.update_song_album, args)

    def rate_song(self, *args):
        self.cursor.execute(queries_music.update_song_rating, args)

    #Add genres, but delete current genres first
    def add_genres(self, kodi_id, genres, media):
        if media == 'album':
            self.cursor.execute(queries_music.delete_genres_album, (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute(queries_music.update_genre_album, (genre_id, kodi_id))

        elif media == 'song':
            self.cursor.execute(queries_music.delete_genres_song, (kodi_id,))

            for genre in genres:
                genre_id = self.get_genre(genre)
                self.cursor.execute(queries_music.update_genre_song, (genre_id, kodi_id))

    def get_genre(self, *args):
        try:
            self.cursor.execute(queries_music.get_genre, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return self.add_genre(*args)

    def add_genre(self, *args):
        genre_id = self.create_entry_genre()
        self.cursor.execute(queries_music.add_genre, (genre_id,) + args)
        return genre_id

    def delete(self, *args):
        self.cursor.execute(queries_music.delete_artist, args)

    def delete_album(self, *args):
        self.cursor.execute(queries_music.delete_album, args)

    def delete_song(self, *args):
        self.cursor.execute(queries_music.delete_song, args)

    def get_path(self, *args):
        try:
            self.cursor.execute(queries_music.get_path, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add_path(self, *args):
        path_id = self.get_path(*args)

        if path_id is None:
            path_id = self.create_entry_path()
            self.cursor.execute(queries_music.add_path, (path_id,) + args)

        return path_id

    def create_entry_path(self):
        self.cursor.execute(queries_music.create_path)
        return self.cursor.fetchone()[0] + 1
