# -*- coding: utf-8 -*-
import json
import xbmc
import xbmcgui
import core.movies
import core.musicvideos
import core.tvshows
import core.music
import helper.loghandler
import helper.utils as Utils
from . import db_open

XbmcMonitor = xbmc.Monitor()
MediaEmbyMappedSubContent = {"movies": "Movie", "boxsets": "BoxSet", "musicvideos": "MusicVideo", "tvshows": "Series", "music": "Music", "homevideos": "Video", "audiobooks": "Audio"}
LOG = helper.loghandler.LOG('EMBY.database.library')


class Library:
    def __init__(self, EmbyServer):
        LOG.info("--->[ library ]")
        self.EmbyServer = EmbyServer
        self.Whitelist = {}
        self.LastStartSync = ""
        self.LastRealtimeSync = ""
        self.EmbyDBWritePriority = False
        self.ContentObject = None

    def open_EmbyDB(self):
        Utils.WorkerInProgress = True
        return db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

    def close_EmbyDB(self, Commit):
        db_open.DBClose(self.EmbyServer.server_id, Commit)
        Utils.WorkerInProgress = False

    def open_EmbyDBPriority(self):
        if self.EmbyDBWritePriority:
            LOG.info("-->[ Wait for priority workers finished ]")

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            LOG.info("--<[ Wait for priority workers finished ]")

        self.EmbyDBWritePriority = True

        if Utils.WorkerInProgress:
            LOG.info("-->[ Wait for workers paused ]")

            while not Utils.WorkerPaused:
                xbmc.sleep(500)

            LOG.info("--<[ Wait for workers paused ]")

        return db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)

    def close_EmbyDBPriority(self):
        db_open.DBClose(self.EmbyServer.server_id, True)
        self.EmbyDBWritePriority = False

    def set_syncdate(self, TimestampUTC):
        # Update sync update timestamp
        embydb = self.open_EmbyDBPriority()
        embydb.update_LastIncrementalSync(TimestampUTC, "realtime")
        embydb.update_LastIncrementalSync(TimestampUTC, "start")
        self.LastRealtimeSync = TimestampUTC
        self.LastStartSync = TimestampUTC
        LastRealtimeSyncLocalTime = Utils.convert_to_local(self.LastRealtimeSync)
        Utils.set_syncdate(LastRealtimeSyncLocalTime)
        self.close_EmbyDBPriority()

    def load_settings(self):
        # Load previous sync information
        embydb = self.open_EmbyDBPriority()
        embydb.init_EmbyDB()
        self.Whitelist = embydb.get_Whitelist()
        self.LastRealtimeSync = embydb.get_LastIncrementalSync("realtime")
        self.LastStartSync = embydb.get_LastIncrementalSync("start")
        self.close_EmbyDBPriority()

    def InitSync(self, Firstrun):  # Threaded by caller -> emby.py
        if Firstrun:
            self.select_libraries("AddLibrarySelection")

        self.RunJobs()
        KodiCompanion = False
        RemovedItems = []
        UpdateData = []

        for plugin in self.EmbyServer.API.get_plugins():
            if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                KodiCompanion = True
                break

        LOG.info("[ Kodi companion: %s ]" % KodiCompanion)

        if self.LastRealtimeSync:
            Items = {}
            LOG.info("-->[ retrieve changes ] %s / %s" % (self.LastRealtimeSync, self.LastStartSync))

            for UserSync in (False, True):
                for LibraryId, Value in list(self.Whitelist.items()):
                    if LibraryId not in self.EmbyServer.Views.ViewItems:
                        LOG.info("[ InitSync remove library %s ]" % LibraryId)
                        continue

                    if Value[0] == "musicvideos":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicVideo", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "movies":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Movie,BoxSet", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "homevideos":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Video", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "tvshows":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "Series,Season,Episode", self.LastRealtimeSync, UserSync)
                    elif Value[0] in ("music", "audiobooks"):
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastRealtimeSync, UserSync)
                    elif Value[0] == "podcasts":
                        Items = self.EmbyServer.API.get_itemsFastSync(LibraryId, "MusicArtist,MusicAlbum,Audio", self.LastStartSync, UserSync)

                    if 'Items' in Items:
                        ItemCounter = 0
                        ItemTemp = len(Items['Items']) * [(None, None, None, None)]  # allocate memory for array (much faster than append each item)

                        for item in Items['Items']:
                            ItemData = (item['Id'], LibraryId, Value[1], item['Type'])

                            if ItemData not in UpdateData:
                                ItemTemp[ItemCounter] = ItemData
                                ItemCounter += 1

                        UpdateData += ItemTemp

            UpdateData = list([_f for _f in UpdateData if _f])

            if KodiCompanion:
                result = self.EmbyServer.API.get_sync_queue(self.LastRealtimeSync, None)  # Kodi companion

                if 'ItemsRemoved' in result:
                    RemovedItems = result['ItemsRemoved']

        # Update sync update timestamp
        self.set_syncdate(Utils.currenttime())

        # Run jobs
        self.removed(RemovedItems)
        self.updated(UpdateData)
        LOG.info("--<[ retrieve changes ]")

    # Get items from emby and place them in the appropriate queues
    # No progress bar needed, it's all internal an damn fast
    def worker_userdata(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker userdata in progress ]")
            return False

        embydb = self.open_EmbyDB()
        UserDataItems = embydb.get_Userdata()

        if not UserDataItems:
            LOG.info("[ worker userdata exit ] queue size: 0")
            self.close_EmbyDB(False)
            return True

        LOG.info("-->[ worker userdata started ] queue size: %d" % len(UserDataItems))
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", "remove")
        isMusic = False
        isVideo = False
        MusicItems = []
        VideoItems = []
        index = 0

        # Group items
        for UserDataItem in UserDataItems:
            UserDataItem = StringToDict(UserDataItem[0])
            e_item = embydb.get_item_by_id(UserDataItem['ItemId'])

            if not e_item: #not synced item
                LOG.info("worker userdata, item not found in local database %s" % UserDataItem['ItemId'])
                embydb.delete_Userdata(str(UserDataItem))
                continue

            if e_item[5] in ('Music', 'MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                MusicItems.append((UserDataItem, e_item, e_item[5]))
            elif e_item[5] == "SpecialFeature":
                LOG.info("worker userdata, skip special feature %s" % UserDataItem['ItemId'])
                embydb.delete_Userdata(str(UserDataItem))
                continue
            else:
                VideoItems.append((UserDataItem, e_item, e_item[5]))

        if MusicItems:
            kodidb = db_open.DBOpen(Utils.DatabaseFiles, "music")
            isMusic = True
            self.ContentObject = None
            TotalRecords = len(MusicItems)

            for MusicItem in MusicItems:
                index += 1
                embydb.delete_Userdata(str(MusicItem[0]))
                Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, MusicItem[1], MusicItem[0], embydb, kodidb, MusicItem[2], "music", "userdata")

                if not Continue:
                    return False

            db_open.DBClose("music", True)

        if VideoItems:
            kodidb = db_open.DBOpen(Utils.DatabaseFiles, "video")
            isVideo = True
            self.ContentObject = None
            TotalRecords = len(VideoItems)

            for VideoItem in VideoItems:
                index += 1
                embydb.delete_Userdata(str(VideoItem[0]))
                Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, VideoItem[1], VideoItem[0], embydb, kodidb, VideoItem[2], "video", "userdata")

                if not Continue:
                    return False

            db_open.DBClose("video", True)

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        progress_updates.close()
        self.close_EmbyDB(True)
        LOG.info("--<[ worker userdata completed ]")
        self.RunJobs()
        return True

    def worker_update(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker update in progress ]")
            return False

        embydb = self.open_EmbyDB()
        UpdateItems = embydb.get_UpdateItem()

        if not UpdateItems:
            LOG.info("[ worker update exit ] queue size: 0")
            self.close_EmbyDB(False)
            return True

        TotalRecords = len(UpdateItems)
        LOG.info("-->[ worker update started ] queue size: %d" % TotalRecords)
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", Utils.Translate(33178))
        QueryUpdateItems = {}
        isMusic = False
        isVideo = False
        index = 0

        for UpdateItem in UpdateItems:
            Id = UpdateItem[0]

            if UpdateItem[1]:  # Fastsync update
                QueryUpdateItems[str(Id)] = {"Id": UpdateItem[1], "Name": UpdateItem[2]}
            else:  # Realtime update
                QueryUpdateItems[str(Id)] = None

        # Load data from Emby server and cache them to minimize Kodi db open time
        while QueryUpdateItems:
            TempQueryUpdateItems = list(QueryUpdateItems.keys())[:int(Utils.limitIndex)]
            Items = self.EmbyServer.API.get_item_library(",".join(TempQueryUpdateItems))

            if 'Items' in Items:
                Items = Items['Items']
                ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason = ItemsSort(Items, QueryUpdateItems)
                ItemsTVShows = ItemsSeries + ItemsSeason + ItemsEpisode
                ItemsMovies = ItemsMovie + ItemsBoxSet
                ItemsAudio = ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio

                if ItemsTVShows or ItemsMovies or ItemsMusicVideo:
                    kodidb = db_open.DBOpen(Utils.DatabaseFiles, "video")

                    for Items in (ItemsTVShows, ItemsMovies, ItemsMusicVideo):
                        self.ContentObject = None

                        for Item, LibraryData, ContentType in Items:
                            index += 1
                            embydb.delete_UpdateItem(Item['Id'])
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, ContentType, "video", "add/update")

                            if not Continue:
                                return False

                            del QueryUpdateItems[Item['Id']]

                    db_open.DBClose("video", True)
                    isVideo = True

                if ItemsAudio:
                    kodidb = db_open.DBOpen(Utils.DatabaseFiles, "music")
                    self.ContentObject = None

                    for Item, LibraryData, ContentType in ItemsAudio:
                        index += 1
                        embydb.delete_UpdateItem(Item['Id'])
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, ContentType, "music", "add/update")

                        if not Continue:
                            return False

                        del QueryUpdateItems[Item['Id']]

                    kodidb.clean_music()
                    db_open.DBClose("music", True)
                    isMusic = True

            for QueryUpdateItemId in TempQueryUpdateItems:
                if QueryUpdateItemId in QueryUpdateItems:
                    del QueryUpdateItems[QueryUpdateItemId]
                    index += 1
                    embydb.delete_UpdateItem(QueryUpdateItemId)

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")
        progress_updates.close()

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        self.close_EmbyDB(True)
        LOG.info("--<[ worker update completed ]")
        self.RunJobs()
        return True

    def worker_remove(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker remove in progress ]")
            return False

        embydb = self.open_EmbyDB()
        RemoveItems = embydb.get_RemoveItem()

        if not RemoveItems:
            LOG.info("[ worker remove exit ] queue size: 0")
            self.close_EmbyDB(False)
            return True

        TotalRecords = len(RemoveItems)
        LOG.info("-->[ worker remove started ] queue size: %d" % TotalRecords)
        isMusic = False
        isVideo = False
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", Utils.Translate(33261))

        #Sort Items
        AllRemoveItems = []
        QueryUpdateItems = {}
        index = 0

        for RemoveItem in RemoveItems:
            Id = RemoveItem[0]
            LibraryId = RemoveItem[2]
            index += 1
            ProgressValue = int(index / TotalRecords * 100)
            progress_updates.update(ProgressValue, heading=Utils.Translate(33261), message=str(Id))
            FoundRemoveItems = embydb.get_media_by_id(Id)

            if not FoundRemoveItems:
                LOG.info("Detect media by folder id %s" % Id)
                FoundRemoveItems = embydb.get_media_by_parent_id(Id)
                embydb.delete_RemoveItem(Id)

            if FoundRemoveItems:
                for FoundRemoveItem in FoundRemoveItems:
                    QueryUpdateItems[FoundRemoveItem[0]] = {"Id": FoundRemoveItem[4], "ForceRemoval": bool(LibraryId)}
                    AllRemoveItems.append({'Id': FoundRemoveItem[0], 'Type': FoundRemoveItem[1], 'IsSeries': 'unknown'})
            else:
                LOG.info("worker remove, item not found in local database %s" % Id)
                continue

        ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason = ItemsSort(AllRemoveItems, QueryUpdateItems)
        index = 0
        ItemsTVShows = ItemsSeries + ItemsSeason + ItemsEpisode
        ItemsMovies = ItemsMovie + ItemsBoxSet
        ItemsAudio = ItemsMusicArtist + ItemsAlbumArtist + ItemsMusicAlbum + ItemsAudio

        if ItemsTVShows or ItemsMovies or ItemsMusicVideo:
            kodidb = db_open.DBOpen(Utils.DatabaseFiles, "video")

            for Items in (ItemsTVShows, ItemsMovies, ItemsMusicVideo):
                self.ContentObject = None

                for Item, _, ContentType in Items:
                    index += 1
                    embydb.delete_RemoveItem(Item['Id'])
                    Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item['Id'], QueryUpdateItems[Item['Id']]["ForceRemoval"], embydb, kodidb, ContentType, "video", "remove")

                    if not Continue:
                        return False

                    del QueryUpdateItems[Item['Id']]

            db_open.DBClose("video", True)
            isVideo = True

        if ItemsAudio:
            kodidb = db_open.DBOpen(Utils.DatabaseFiles, "music")
            self.ContentObject = None

            for Item, _, ContentType in ItemsAudio:
                index += 1
                LibraryIds = QueryUpdateItems[Item['Id']]["Id"].split(";")

                for LibraryId in LibraryIds:
                    Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item['Id'], LibraryId, embydb, kodidb, ContentType, "music", "remove")
                    embydb.delete_RemoveItem(Item['Id'])

                    if not Continue:
                        return False

                del QueryUpdateItems[Item['Id']]

            kodidb.clean_music()
            db_open.DBClose("music", True)
            isMusic = True

        # remove not found items
        for QueryUpdateItem in QueryUpdateItems:
            embydb.delete_RemoveItem(QueryUpdateItem)

        embydb.update_LastIncrementalSync(Utils.currenttime(), "realtime")

        progress_updates.close()

        if isMusic and not Utils.useDirectPaths:
            xbmc.executebuiltin('UpdateLibrary(music)')

        if isVideo:
            xbmc.executebuiltin('UpdateLibrary(video)')

        self.close_EmbyDB(True)
        LOG.info("--<[ worker remove completed ]")
        self.RunJobs()
        return True

    def worker_library(self):
        if Utils.SyncPause or Utils.WorkerInProgress:
            LOG.info("[ worker library in progress ]")
            return False

        embydb = self.open_EmbyDB()
        SyncItems = embydb.get_PendingSync()

        if not SyncItems:
            LOG.info("[ worker library exit ] queue size: 0")
            self.close_EmbyDB(False)
            return True

        LOG.info("-->[ worker library started ] queue size: %d" % len(SyncItems))
        isMusic = False
        isVideo = False
        progress_updates = xbmcgui.DialogProgressBG()
        progress_updates.create("Emby", "%s %s" % (Utils.Translate(33021), Utils.Translate(33238)))

        for SyncItem in SyncItems:
            if Utils.SyncPause:
                LOG.info("[ worker library paused ]")
                progress_updates.close()
                self.close_EmbyDB(True)
                return False

            library_id = SyncItem[0]
            library_type = SyncItem[1]
            library_name = SyncItem[2]
            LibraryData = {"Id": library_id, "Name": library_name}
            embydb.add_Whitelist(library_id, library_type, library_name)
            self.Whitelist[library_id] = (library_type, library_name)

            if SyncItem[3]:
                RestorePoint = StringToDict(SyncItem[3])
            else:
                RestorePoint = {}

            if library_type in ('movies', 'musicvideos', 'boxsets', 'homevideos'):
                isVideo = True
                SubContent = MediaEmbyMappedSubContent[library_type]
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, SubContent))
                index = int(RestorePoint.get('StartIndex', 0))
                kodidb = db_open.DBOpen(Utils.DatabaseFiles, "video")
                self.ContentObject = None

                for items in self.EmbyServer.API.get_itemsSync(library_id, SubContent, False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for Item in items['Items']:
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, MediaEmbyMappedSubContent[library_type], "video", "add/update")

                        if not Continue:
                            return False

                db_open.DBClose("video", True)
            elif library_type == 'tvshows':  # stacked sync: tv-shows -> season/episode
                isVideo = True
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "Series"))
                index = int(RestorePoint.get('StartIndex', 0))
                kodidb = db_open.DBOpen(Utils.DatabaseFiles, "video")
                self.ContentObject = None

                for items in self.EmbyServer.API.get_itemsSync(library_id, 'Series', False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for tvshow in items['Items']:
                        Seasons = []
                        Episodes = []
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, tvshow, LibraryData, embydb, kodidb, "Series", "video", "add/update")

                        if not Continue:
                            return False

                        for itemsContent in self.EmbyServer.API.get_itemsSync(tvshow['Id'], "Season,Episode", False, {}):
                            # Sort
                            for item in itemsContent['Items']:
                                if item["Type"] == "Season":
                                    Seasons.append(item)
                                else:
                                    Episodes.append(item)

                        for Season in Seasons:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Season, LibraryData, embydb, kodidb, "Season", "video", "add/update")

                            if not Continue:
                                return False

                        for Episode in Episodes:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Episode, LibraryData, embydb, kodidb, "Episode", "video", "add/update")

                            if not Continue:
                                return False

                db_open.DBClose("video", True)
            elif library_type == 'music':  #  Sync only if artist is valid - staggered sync (performance)
                isMusic = True
                TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, "MusicArtist"))
                kodidb = db_open.DBOpen(Utils.DatabaseFiles, "music")
                self.ContentObject = None
                index = int(RestorePoint.get('StartIndex', 0))

                for items in self.EmbyServer.API.get_artists(library_id, False, RestorePoint):
                    RestorePoint = items['RestorePoint']['params']
                    embydb.update_Restorepoint(library_id, library_type, library_name, str(RestorePoint))

                    for artist in items['Items']:
                        Albums = []
                        Audios = []
                        index += 1
                        Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, artist, LibraryData, embydb, kodidb, "MusicArtist", "music", "add/update")

                        if not Continue:
                            return False

                        for itemsContent in self.EmbyServer.API.get_itemsSyncMusic(library_id, "MusicAlbum,Audio", {"ArtistIds": artist['Id']}):
                            # Sort
                            for item in itemsContent['Items']:
                                if item["Type"] == "MusicAlbum":
                                    Albums.append(item)
                                else:
                                    Audios.append(item)

                        for album in Albums:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, album, LibraryData, embydb, kodidb, "MusicAlbum", "music", "add/update")

                            if not Continue:
                                return False

                        for song in Audios:
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, song, LibraryData, embydb, kodidb, "Audio", "music", "add/update")

                            if not Continue:
                                return False

                db_open.DBClose("music", True)
            elif library_type in ('audiobooks', 'podcasts'):  # Sync even if artist is empty
                isMusic = True
                kodidb = db_open.DBOpen(Utils.DatabaseFiles, "music")
                self.ContentObject = None
                MusicTypes = ("MusicArtist", "MusicAlbum", "Audio")

                for MusicType in MusicTypes:
                    TotalRecords = int(self.EmbyServer.API.get_TotalRecordsRegular(library_id, MusicTypes))
                    index = 0

                    for items in self.EmbyServer.API.get_itemsSyncMusic(library_id, MusicType, {}):
                        for Item in items['Items']:
                            index += 1
                            Continue, embydb, kodidb = self.ItemOps(progress_updates, index, TotalRecords, Item, LibraryData, embydb, kodidb, MusicType, "music", "add/update")

                            if not Continue:
                                return False

                db_open.DBClose("music", True)

            embydb.remove_PendingSync(library_id, library_type, library_name)

            if isMusic and not Utils.useDirectPaths:
                xbmc.executebuiltin('UpdateLibrary(music)')

            if isVideo:
                xbmc.executebuiltin('UpdateLibrary(video)')

        progress_updates.close()
        self.EmbyServer.Views.update_nodes()
        LOG.info("[ reload skin ]")
        xbmc.executebuiltin('ReloadSkin()')
        self.close_EmbyDB(True)
        LOG.info("--<[ worker library completed ]")
        self.RunJobs()
        return True

    def ItemOps(self, progress_updates, index, TotalRecords, Item, Parameter, embydb, kodidb, ContentType, ContentCategory, Task):
        Ret = False

        if not self.ContentObject:
            self.load_libraryObject(ContentType, embydb, kodidb)

        ProgressValue = int(index / TotalRecords * 100)

        if Task == "add/update":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=Item['Name'])

            if ContentType == "Audio":
                Ret = self.ContentObject.song(Item, Parameter)
            elif ContentType == "MusicAlbum":
                Ret = self.ContentObject.album(Item, Parameter)
            elif ContentType in ("MusicArtist", "AlbumArtist"):
                Ret = self.ContentObject.artist(Item, Parameter)
            elif ContentType in ("Movie", "Video"):
                Ret = self.ContentObject.movie(Item, Parameter)
            elif ContentType == "BoxSet":
                Ret = self.ContentObject.boxset(Item, Parameter)
            elif ContentType == "MusicVideo":
                Ret = self.ContentObject.musicvideo(Item, Parameter)
            elif ContentType == "Episode":
                Ret = self.ContentObject.episode(Item, Parameter)
            elif ContentType == "Season":
                Ret = self.ContentObject.season(Item, Parameter)
            elif ContentType == "Series":
                Ret = self.ContentObject.tvshow(Item, Parameter)

            if Ret and Utils.newContent:
                if ContentCategory == "music":
                    MsgTime = int(Utils.newmusictime) * 1000
                else:
                    MsgTime = int(Utils.newvideotime) * 1000

                Utils.dialog("notification", heading="%s %s" % (Utils.Translate(33049), ContentType), message=Item['Name'], icon="special://home/addons/plugin.video.emby-next-gen/resources/icon.png", time=MsgTime, sound=False)
        elif Task == "remove":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=str(Item))
            self.ContentObject.remove(Item, Parameter)
        elif Task == "userdata":
            progress_updates.update(ProgressValue, heading="Emby: %s" % ContentType, message=str(Parameter['ItemId']))
            self.ContentObject.userdata(Item, Parameter)

        # Check priority tasks
        if self.EmbyDBWritePriority:
            db_open.DBClose(self.EmbyServer.server_id, True)
            Utils.WorkerPaused = True
            LOG.info("-->[ Priority Emby DB I/O in progress ]")

            while self.EmbyDBWritePriority:
                xbmc.sleep(500)

            Utils.WorkerPaused = False
            LOG.info("--<[ Priority Emby DB I/O in progress ]")
            embydb = db_open.DBOpen(Utils.DatabaseFiles, self.EmbyServer.server_id)
            self.load_libraryObject(ContentType, embydb, kodidb)

        # Check if Kodi db is open -> close db, wait, reopen db
        if Utils.KodiDBLock[ContentCategory]:
            LOG.info("[ worker delay due to kodi %s db io ]" % ContentCategory)
            db_open.DBClose(ContentCategory, True)

            while Utils.KodiDBLock[ContentCategory]:
                xbmc.sleep(500)

            kodidb = db_open.DBOpen(Utils.DatabaseFiles, ContentCategory)
            self.load_libraryObject(ContentType, embydb, kodidb)

        # Check sync pause
        Continue = True

        if Utils.SyncPause:
            LOG.info("[ worker paused ]")

            if progress_updates:
                progress_updates.close()

            db_open.DBClose(ContentCategory, True)
            self.close_EmbyDB(True)
            Continue = False

        return Continue, embydb, kodidb

    def load_libraryObject(self, ContentType, embydb, kodidb):
        if ContentType in ("Movie", "BoxSet", "Video"):
            self.ContentObject = core.movies.Movies(self.EmbyServer, embydb, kodidb)
        elif ContentType == "MusicVideo":
            self.ContentObject = core.musicvideos.MusicVideos(self.EmbyServer, embydb, kodidb)
        elif ContentType in ('Audio', "MusicArtist", "MusicAlbum", "AlbumArtist"):
            self.ContentObject = core.music.Music(self.EmbyServer, embydb, kodidb)
        elif ContentType in ("Episode", "Season", 'Series'):
            self.ContentObject = core.tvshows.TVShows(self.EmbyServer, embydb, kodidb)

    # Run workers in specific order
    def RunJobs(self):
        if self.worker_remove():
            if self.worker_update():
                if self.worker_userdata():
                    self.worker_library()

    # Select from libraries synced. Either update or repair libraries.
    # Send event back to service.py
    def select_libraries(self, mode):  # threaded by caller
        libraries = []

        if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection', 'UpdateLibrarySelection'):
            for LibraryId, Value in list(self.Whitelist.items()):
                AddData = {'Id': LibraryId, 'Name': Value[1]}

                if AddData not in libraries:
                    libraries.append(AddData)
        else:  # AddLibrarySelection
            AvailableLibs = self.EmbyServer.Views.ViewItems.copy()

            for LibraryId in self.Whitelist:
                del AvailableLibs[LibraryId]

            for AvailableLibId, AvailableLib in list(AvailableLibs.items()):
                if AvailableLib[1] in ["movies", "musicvideos", "tvshows", "music", "audiobooks", "podcasts", "mixed", "homevideos"]:
                    libraries.append({'Id': AvailableLibId, 'Name': AvailableLib[0]})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, Utils.Translate(33121))
        selection = Utils.dialog("multi", Utils.Translate(33120), choices)

        if selection is None:
            return

        # "All" selected
        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')
        remove_librarys = []
        add_librarys = []

        if mode in ('AddLibrarySelection', 'UpdateLibrarySelection'):
            for x in selection:
                add_librarys.append(libraries[x - 1]['Id'])
        elif mode == 'RepairLibrarySelection':
            for x in selection:
                remove_librarys.append(libraries[x - 1]['Id'])
                add_librarys.append(libraries[x - 1]['Id'])
        elif mode == 'RemoveLibrarySelection':
            for x in selection:
                remove_librarys.append(libraries[x - 1]['Id'])

        if remove_librarys:
            self.remove_library(remove_librarys)

        if add_librarys:
            self.add_library(add_librarys)

    def refresh_boxsets(self):  # threaded by caller
        embydb = self.open_EmbyDBPriority()
        xbmc.executebuiltin('Dialog.Close(addonsettings)')
        xbmc.executebuiltin('Dialog.Close(addoninformation)')
        xbmc.executebuiltin('activatewindow(home)')

        for LibraryId, Value in list(self.Whitelist.items()):
            if Value[0] == "movies":
                embydb.add_PendingSync(LibraryId, "boxsets", Value[1], None)

        self.close_EmbyDBPriority()
        self.worker_library()

    def add_library(self, library_ids):  # threaded by caller
        if library_ids:
            embydb = self.open_EmbyDBPriority()

            for library_id in library_ids:
                ViewData = self.EmbyServer.Views.ViewItems[library_id]
                library_type = ViewData[1]
                library_name = ViewData[0]

                if library_type == 'mixed':
                    embydb.add_PendingSync(library_id, "movies", library_name, None)
                    embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                    embydb.add_PendingSync(library_id, "tvshows", library_name, None)
                    embydb.add_PendingSync(library_id, "music", library_name, None)
                elif library_type == 'movies':
                    embydb.add_PendingSync(library_id, "movies", library_name, None)
                    embydb.add_PendingSync(library_id, "boxsets", library_name, None)
                else:
                    embydb.add_PendingSync(library_id, library_type, library_name, None)

                LOG.info("---[ added library: %s ]" % library_id)

            self.close_EmbyDBPriority()
            self.worker_library()

    # Remove library by their id from the Kodi database
    def remove_library(self, LibraryIds):  # threaded by caller
        if LibraryIds:
            embydb = self.open_EmbyDBPriority()
            RemoveItems = []

            for LibraryId in LibraryIds:
                items = embydb.get_item_by_emby_folder_wild(LibraryId)

                for item in items:
                    RemoveItems.append(item + (LibraryId,))

                embydb.remove_Whitelist_wild(LibraryId)
                del self.Whitelist[LibraryId]
                self.EmbyServer.Views.delete_playlist_by_id(LibraryId)
                self.EmbyServer.Views.delete_node_by_id(LibraryId)
                LOG.info("---[ removed library: %s ]" % LibraryId)

            self.close_EmbyDBPriority()
            self.EmbyServer.Views.update_nodes()
            self.removed(RemoveItems)

    # Add item_id to userdata queue
    def userdata(self, Data):  # threaded by caller -> websocket via monitor
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                embydb.add_Userdata(str(item))

            self.close_EmbyDBPriority()
            self.worker_userdata()

    # Add item_id to updated queue
    def updated(self, Data):  # threaded by caller
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    LibraryId = item[1]
                    LibraryName = item[2]
                    LibraryType = item[3]
                else:  # update via Websocket
                    item = str(item)

                    if not Utils.Python3:
                        item = unicode(item, 'utf-8')

                    if item.isnumeric():
                        EmbyId = item
                        LibraryId = None
                        LibraryName = None
                        LibraryType = None
                    else:
                        LOG.info("Skip invalid update item: %s" % item)
                        continue

                embydb.add_UpdateItem(EmbyId, LibraryId, LibraryName, LibraryType)

            self.close_EmbyDBPriority()
            self.worker_update()

    # Add item_id to removed queue
    def removed(self, Data):  # threaded by caller
        if Data:
            embydb = self.open_EmbyDBPriority()

            for item in Data:
                if isinstance(item, tuple):
                    EmbyId = item[0]
                    EmbyType = item[1]
                    LibraryId = item[2]
                else:  # update via Websocket
                    item = str(item)

                    if not Utils.Python3:
                        item = unicode(item, 'utf-8')

                    if item.isnumeric():
                        EmbyId = item
                        EmbyType = None
                        LibraryId = None
                    else:
                        LOG.info("Skip invalid remove item: %s" % item)
                        continue

                embydb.add_RemoveItem(EmbyId, EmbyType, LibraryId)

            self.close_EmbyDBPriority()
            self.worker_remove()

def ItemsSort(Items, LibraryData):
    ItemsAudio = []
    ItemsMovie = []
    ItemsBoxSet = []
    ItemsMusicVideo = []
    ItemsSeries = []
    ItemsEpisode = []
    ItemsMusicAlbum = []
    ItemsMusicArtist = []
    ItemsAlbumArtist = []
    ItemsSeason = []

    for Item in Items:
        ItemType = 'Unknown'

        if 'Type' in Item:
            ItemType = Item['Type']

            if ItemType == "Recording":
                if 'MediaType' in Item:
                    if Item['IsSeries']:
                        ItemType = 'Episode'
                    else:
                        ItemType = 'Movie'

        if ItemType in ('Movie', 'Video'):
            ItemsMovie.append((Item, LibraryData[Item["Id"]], 'Movie'))
        elif ItemType == 'BoxSet':
            ItemsBoxSet.append((Item, LibraryData[Item["Id"]], 'BoxSet'))
        elif ItemType == 'MusicVideo':
            ItemsMusicVideo.append((Item, LibraryData[Item["Id"]], 'MusicVideo'))
        elif ItemType == 'Series':
            ItemsSeries.append((Item, LibraryData[Item["Id"]], 'Series'))
        elif ItemType == 'Episode':
            ItemsEpisode.append((Item, LibraryData[Item["Id"]], 'Episode'))
        elif ItemType == 'MusicAlbum':
            ItemsMusicAlbum.append((Item, LibraryData[Item["Id"]], 'MusicAlbum'))
        elif ItemType == 'MusicArtist':
            ItemsMusicArtist.append((Item, LibraryData[Item["Id"]], 'MusicArtist'))
        elif ItemType == 'Audio':
            ItemsAudio.append((Item, LibraryData[Item["Id"]], 'Audio'))
        elif ItemType == 'AlbumArtist':
            ItemsAlbumArtist.append((Item, LibraryData[Item["Id"]], 'AlbumArtist'))
        elif ItemType == 'Season':
            ItemsSeason.append((Item, LibraryData[Item["Id"]], 'Season'))
        else:
            LOG.info("ItemType unknown: %s" % ItemType)
            continue

    return ItemsAudio, ItemsMovie, ItemsBoxSet, ItemsMusicVideo, ItemsSeries, ItemsEpisode, ItemsMusicAlbum, ItemsMusicArtist, ItemsAlbumArtist, ItemsSeason

def StringToDict(Data):
    Data = Data.replace("'", '"')
    Data = Data.replace("False", "false")
    Data = Data.replace("True", "true")
    Data = Data.replace('u"', '"')  # Python 2.X workaround
    Data = Data.replace('L, "', ', "')  # Python 2.X workaround
    Data = Data.replace('l, "', ', "')  # Python 2.X workaround
    return json.loads(Data)
