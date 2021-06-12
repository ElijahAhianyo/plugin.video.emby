# -*- coding: utf-8 -*-
import json
import threading
import uuid

import xbmc

import database.database
import database.emby_db
import core.queries_videos
import helper.jsonrpc
import helper.loghandler

class ProgressUpdates(threading.Thread):
    def __init__(self, Player):
        self.Player = Player
        self.Exit = False
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True

    def run(self):
        while True:
            if xbmc.Monitor().waitForAbort(5):
                return

            if not self.Exit:
                self.Player.report_playback(True)
            else:
                return

class PlayerEvents(xbmc.Player):
    def __init__(self):
        self.CurrentlyPlaying = {}
        self.LOG = helper.loghandler.LOG('EMBY.hooks.player.Player')
        self.Trailer = False
        self.PlayerReloadIndex = "-1"
        self.PlayerLastItem = ""
        self.PlayerLastItemID = "-1"
        self.ItemSkipUpdate = []
        self.SyncPause = False
        self.ProgressThread = None
        self.PlaySessionId = ""
        self.MediasourceID = ""
        self.Transcoding = False
        self.CurrentItem = {}
        self.SkipUpdate = False
        self.PlaySessionIdLast = ""
        self.DynamicItem = {}

    #Threaded by Monitor
    def OnStop(self, EmbyServer):
        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        if self.Transcoding:
            EmbyServer.API.close_transcode()

        self.SyncPause = False

    #Threaded by Monitor
    def OnPlay(self, data, EmbyServer, library):
        self.LOG.info("[ OnPlay ] %s " % data)

        if data['item']['type'] in ('picture', 'unknown'):
            return

        if self.ProgressThread:
            self.ProgressThread.Stop()
            self.ProgressThread = None

        if not self.Trailer:
            if not "id" in data['item']:
                DynamicID = EmbyServer.Utils.ReplaceSpecialCharecters(data['item']['title'])

                if DynamicID in self.DynamicItem:
                    self.CurrentItem['Id'] = self.DynamicItem[DynamicID]
                else:
                    self.CurrentItem['Tracking'] = False
                    return
            else:
                kodi_id = data['item']['id']
                media_type = data['item']['type']
                item = database.database.get_item_complete(EmbyServer.Utils, kodi_id, media_type)

                if item:
                    self.CurrentItem['Id'] = item[0]
                else:
                    self.CurrentItem['Tracking'] = False
                    return #Kodi internal Source

            if EmbyServer.Utils.direct_path: #native mode
                PresentationKey = item[10].split("-")
                self.ItemSkipUpdate.append(PresentationKey[0])
                self.ItemSkipUpdate.append(self.CurrentItem['Id'])
                self.PlaySessionId = str(uuid.uuid4()).replace("-", "")

            self.CurrentItem['Tracking'] = True
            self.CurrentItem['Type'] = data['item']['type']
            self.CurrentItem['MediaSourceId'] = self.MediasourceID
            self.CurrentItem['RunTime'] = 0
            self.CurrentItem['CurrentPosition'] = 0
            self.CurrentItem['Paused'] = False
            self.CurrentItem['EmbyServer'] = EmbyServer
            self.CurrentItem['library'] = library
            self.CurrentItem['Volume'], self.CurrentItem['Muted'] = self.get_volume()

    def onAVChange(self):
        self.LOG.info("[ onAVChange ]")

    def onQueueNextItem(self):
        self.LOG.info("[ onQueueNextItem ]")

    def onPlayBackStarted(self):
        self.LOG.info("[ onPlayBackStarted ]")
        self.SyncPause = True

        if self.ReloadStream():#Media reload (3D Movie)
            return

    def onPlayBackPaused(self):
        self.LOG.info("[ onPlayBackPaused ]")

        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Paused'] = True
        self.report_playback()
        self.LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        self.LOG.info("[ onPlayBackResumed ]")

        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Paused'] = False
        self.report_playback(False)
        self.LOG.debug("--<[ paused ]")

    def onPlayBackStopped(self):
        self.LOG.info("[ onPlayBackStopped ]")

        if self.ReloadStream():#Media reload (3D Movie)
            return

        self.PlayerLastItemID = "-1"
        self.PlayerLastItem = ""
        self.Trailer = False
        self.stop_playback(False)
        self.LOG.info("--<[ playback ]")

    def onPlayBackSeek(self, time, seekOffset):
        self.LOG.info("[ onPlayBackSeek ]")

        if not self.CurrentlyPlaying:
            return

        SeekPosition = int(time * 10000)

        if self.CurrentlyPlaying['RunTime']:
            if SeekPosition > self.CurrentlyPlaying['RunTime']:
                SeekPosition = self.CurrentlyPlaying['RunTime']

        self.CurrentlyPlaying['CurrentPosition'] = SeekPosition
        self.report_playback(False)
        self.SkipUpdate = True #Pause progress updates for one cycle -> new seek position

    def onPlayBackEnded(self):
        self.LOG.info("[ onPlayBackEnded ]")

        if self.Trailer or self.ReloadStream():
            return

        self.PlayerLastItemID = "-1"
        self.PlayerLastItem = ""
        self.stop_playback(False)
        self.LOG.info("--<<[ playback ]")

    #Threaded to ThreadAVStarted
    def onAVStarted(self):
        self.LOG.info("[ onAVStarted ]")
        self.SyncPause = True
        new_thread = PlayerWorker(self, "ThreadAVStarted")
        new_thread.start()

    def ThreadAVStarted(self):
        self.LOG.info("[ ThreadAVStarted ]")
        self.stop_playback(True)

        while not self.CurrentItem: #wait for OnPlay
            if xbmc.Monitor().waitForAbort(1):
                return

        if not self.CurrentItem['Tracking']:
            self.CurrentItem = {}
            return

        if not self.set_CurrentPosition(): #Stopped directly after started playing
            self.LOG.info("[ fast stop detected ]")
            return

        self.CurrentItem['PlaySessionId'] = self.PlaySessionId
        self.CurrentlyPlaying = self.CurrentItem
        self.CurrentItem = {}
        self.LOG.info("-->[ play/%s ] %s" % (self.CurrentlyPlaying['Id'], self.CurrentlyPlaying))
        data = {
            'ItemId': self.CurrentlyPlaying['Id'],
            'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
            'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
        }

        #Init session
        self.CurrentlyPlaying['EmbyServer'].API.session_playing(data)
        self.SkipUpdate = False
        self.report_playback(False)

        if not self.ProgressThread:
            self.ProgressThread = ProgressUpdates(self)
            self.ProgressThread.start()

    def SETVolume(self, Volume, Mute):
        if not self.CurrentlyPlaying:
            return

        self.CurrentlyPlaying['Volume'] = Volume
        self.CurrentlyPlaying['Muted'] = Mute
        self.report_playback(False)

    def set_CurrentPosition(self):
        try:
            CurrentPosition = int(self.getTime() * 10000000)

            if CurrentPosition < 0:
                CurrentPosition = 0

            self.CurrentlyPlaying['CurrentPosition'] = CurrentPosition
            return True
        except:
            return False

    def set_Runtime(self):
        try:
            self.CurrentlyPlaying['RunTime'] = int(self.getTotalTime() * 10000000)
            return bool(self.CurrentlyPlaying['RunTime'])
        except:
            return False

    #Report playback progress to emby server.
    def report_playback(self, UpdatePosition=True):
        if not self.CurrentlyPlaying or self.Trailer or self.SkipUpdate:
            self.SkipUpdate = False
            return

        if not self.CurrentlyPlaying['RunTime']:
            if not self.set_Runtime():
                self.LOG.info("[ skip progress update, no runtime info ]")
                return

        if UpdatePosition:
            if not self.set_CurrentPosition():
                self.LOG.info("[ skip progress update, no position info ]")
                return

        data = {
            'ItemId': self.CurrentlyPlaying['Id'],
            'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
            'PositionTicks': self.CurrentlyPlaying['CurrentPosition'],
            'RunTimeTicks': self.CurrentlyPlaying['RunTime'],
            'CanSeek': True,
            'QueueableMediaTypes': "Video,Audio",
            'VolumeLevel': self.CurrentlyPlaying['Volume'],
            'IsPaused': self.CurrentlyPlaying['Paused'],
            'IsMuted': self.CurrentlyPlaying['Muted'],
            'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
        }
        self.CurrentlyPlaying['EmbyServer'].API.session_progress(data)

    def get_volume(self):
        result = helper.jsonrpc.JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')
        return volume, muted

    def onPlayBackError(self):
        self.LOG.warning("Playback error occured")
        self.stop_playback(False)

    def ReloadStream(self):
        #Media has changed -> reload
        if self.PlayerReloadIndex != "-1":
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            self.play(item=playlist, startpos=int(self.PlayerReloadIndex))
            self.PlayerReloadIndex = "-1"
            return True

        return False

    def stop_playback(self, Init):
        if self.CurrentlyPlaying:
            self.LOG.debug("[ played info ] %s" % self.CurrentlyPlaying)
            data = {
                'ItemId': self.CurrentlyPlaying['Id'],
                'MediaSourceId': self.CurrentlyPlaying['MediaSourceId'],
                'PositionTicks': self.CurrentlyPlaying['CurrentPosition'],
                'PlaySessionId': self.CurrentlyPlaying['PlaySessionId']
            }
            self.CurrentlyPlaying['EmbyServer'].API.session_stop(data)

            if self.Transcoding:
                self.CurrentlyPlaying['EmbyServer'].API.close_transcode()

        if not Init:
            self.SyncPause = False

            #Offer delete
            if self.CurrentlyPlaying:
                if self.CurrentlyPlaying['EmbyServer'].Utils.Settings.offerDelete:
                    Runtime = int(self.CurrentlyPlaying['RunTime'])

                    if Runtime > 10:
                        if int(self.CurrentlyPlaying['CurrentPosition']) > Runtime * 0.95: #95% Progress
                            DeleteMsg = False

                            if self.CurrentlyPlaying['Type'] == 'episode' and self.CurrentlyPlaying['EmbyServer'].Utils.Settings.deleteTV:
                                DeleteMsg = True
                            elif self.CurrentlyPlaying['Type'] == 'movie' and self.CurrentlyPlaying['EmbyServer'].Utils.Settings.deleteMovies:
                                DeleteMsg = True

                            if DeleteMsg:
                                self.LOG.info("Offer delete option")

                            if self.CurrentlyPlaying['EmbyServer'].Utils.dialog("yesno", heading=self.CurrentlyPlaying['EmbyServer'].Utils.Translate(30091), line1=self.CurrentlyPlaying['EmbyServer'].Utils.Translate(33015)):
                                self.CurrentlyPlaying['EmbyServer'].API.delete_item(self.CurrentlyPlaying['Id'])
                                self.CurrentlyPlaying['library'].removed([self.CurrentlyPlaying['Id']])
                                self.CurrentlyPlaying['library'].delay_verify([self.CurrentlyPlaying['Id']])

                self.CurrentlyPlaying = {}

class PlayerWorker(threading.Thread):
    def __init__(self, Player, method):
        self.method = method
        self.Player = Player
        threading.Thread.__init__(self)

    def run(self):
        if self.method == 'ThreadAVStarted':
            self.Player.ThreadAVStarted()
            return

#Call from WebSocket to manipulate playing URL
class WebserviceOnPlay(threading.Thread):
    def __init__(self, Player, EmbyServer, WebserviceEventIn, WebserviceEventOut):
        self.LOG = helper.loghandler.LOG('EMBY.hooks.player.WebserviceOnPlay')
        self.EmbyServer = EmbyServer
        self.WebserviceEventIn = WebserviceEventIn
        self.WebserviceEventOut = WebserviceEventOut
        self.Player = Player
        self.Intros = None
        self.IntrosIndex = 0
        self.Exit = False
        self.Trailers = False
        self.EmbyIDLast = -1
        self.EmbyID = -1
        self.Type = ""
        self.KodiID = -1
        self.KodiFileID = -1
        self.Force = False
        self.Filename = ""
        self.MediaSources = []
        self.TranscodeReasons = ""
        self.IncommingData = ""
        self.TargetVideoBitrate = 0
        self.TargetAudioBitrate = 0
        self.emby_dbT = None
        self.BitrateFromURL = None
        self.MediasourceID = None
        self.EmbyServer.Utils.load_defaultvideosettings()
        threading.Thread.__init__(self)

    def Stop(self):
        self.Exit = True
        self.WebserviceEventOut.put("quit")

    def run(self):
        while not self.Exit:
            self.EmbyID = None
            self.MediasourceID = None
            self.Type = None
            self.BitrateFromURL = None
            self.Filename = None
            self.IncommingData = self.WebserviceEventOut.get()
            self.LOG.debug("[ query IncommingData ] %s" % self.IncommingData)

            if self.IncommingData == "quit":
                break

            self.GetParametersFromURLQuery()

            if 'audio' in self.IncommingData:
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/audio/" + self.EmbyID + "/stream?static=true&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename)
                continue

            if 'livetv' in self.IncommingData:
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream.ts?PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename)
                continue

            if 'main.m3u8' in self.IncommingData: #Dynamic Transcode query
                URL = self.IncommingData.replace("/movie/", "/")
                URL = URL.replace("/musicvideo/", "/")
                URL = URL.replace("/tvshow/", "/")
                URL = URL.replace("/video/", "/")
                URL = URL.replace("/trailer/", "/")
                self.WebserviceEventIn.put(self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyIDLast + URL)
                continue

            if self.Player.Transcoding:
                self.EmbyServer.API.close_transcode()

            self.Player.Transcoding = False

            if self.Type == "movies":
                self.Type = "movie"
            elif self.Type == "tvshows":
                self.Type = "episode"
            elif self.Type == "musicvideos":
                self.Type = "musicvideo"

            self.Player.SyncPause = True

            #Reload Playlistitem after playlist injection
            if self.Player.PlayerReloadIndex != "-1":
                URL = "RELOAD"
                self.WebserviceEventIn.put(URL)
                continue

            #Trailers
            if self.EmbyServer.Utils.Settings.enableCinema and self.Player.PlayerLastItemID != self.EmbyID:
                PlayTrailer = True

                if self.EmbyServer.Utils.Settings.askCinema:
                    if not self.Player.Trailer:
                        self.Trailers = False

                    if not self.Trailers and not self.Player.Trailer:
                        self.Trailers = True
                        PlayTrailer = self.EmbyServer.Utils.dialog("yesno", heading="{emby}", line1=self.EmbyServer.Utils.Translate(33016))

                if PlayTrailer:
                    if self.Player.PlayerLastItem != self.IncommingData or not self.Player.Trailer:
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "one" }, "id": 1 }')
                        self.Player.PlayerLastItem = self.IncommingData
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Intros = self.EmbyServer.API.get_intros(self.EmbyID)
                        #self.IntrosLocal = self.EmbyServer.API.get_local_trailers(self.EmbyID)
                        self.Player.Trailer = True

                    try: #Play next trailer
                        self.WebserviceEventIn.put(self.Intros['Items'][self.IntrosIndex]['Path'])
                        self.IntrosIndex += 1
                        continue
                    except: #No more trailers
                        xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')
                        self.Force = True
                        self.Player.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Player.Trailer = False
                else:
                    xbmc.executeJSONRPC('{ "jsonrpc": "2.0", "method": "Player.SetRepeat", "params": {"playerid": 1, "repeat": "off" }, "id": 1 }')

            #Select mediasources, Audiostreams, Subtitles
            if self.Player.PlayerLastItemID != self.EmbyID or self.Force:
                self.Force = False
                self.Player.PlayerLastItemID = str(self.EmbyID)

                with database.database.Database(self.EmbyServer.Utils, 'emby', False) as embydb:
                    self.emby_dbT = database.emby_db.EmbyDatabase(embydb.cursor)
                    EmbyDBItem = self.emby_dbT.get_kodiid(self.EmbyID)

                    if EmbyDBItem: #Item synced to Kodi DB
                        if EmbyDBItem[1]:
                            PresentationKey = EmbyDBItem[1].split("-")
                            self.Player.ItemSkipUpdate.append(PresentationKey[0])

                        self.KodiID = str(EmbyDBItem[0])
                        self.KodiFileID = str(EmbyDBItem[2])
                        self.MediaSources = self.emby_dbT.get_mediasource(self.EmbyID)

                        if len(self.MediaSources) == 1:
                            self.Player.PlayerLastItemID = "-1"
                            self.WebserviceEventIn.put(self.LoadData(0))
                            continue

                        #Multiversion
                        Selection = []

                        for Data in self.MediaSources:
                            Selection.append(Data[8] + " - " + self.SizeToText(float(Data[7])))

                        MediaIndex = self.EmbyServer.Utils.dialog("select", heading="Select Media Source:", list=Selection)

                        if MediaIndex <= 0:
                            MediaIndex = 0
                            self.Player.PlayerLastItemID = "-1"

                        self.MediasourceID = self.MediaSources[MediaIndex][3]
                        self.WebserviceEventIn.put(self.LoadData(MediaIndex))
                    else:
                        self.Player.PlayerReloadIndex = "-1"
                        self.Player.PlayerLastItem = ""
                        self.Intros = None
                        self.IntrosIndex = 0
                        self.Trailers = False
                        self.Player.Trailer = False
                        self.SubTitlesAdd()
                        self.Player.Transcoding = self.IsTranscoding(self.BitrateFromURL, None)

                        if self.Player.Transcoding:
                            URL = self.GETTranscodeURL(self.Filename, False, False)
                        else:
                            URL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + self.MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

                        self.WebserviceEventIn.put(URL)

    #Load SRT subtitles
    def SubTitlesAdd(self):
        Subtitles = self.emby_dbT.get_Subtitles(self.EmbyID, 0)

        if len(Subtitles) >= 1:
            CounterSubTitle = 0

            for Data in Subtitles:
                CounterSubTitle += 1

                if Data[3] == "srt":
                    SubTitleURL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/" + self.MediasourceID + "/Subtitles/" + str(Data[18]) + "/stream.srt"
                    request = {'type': "GET", 'url': SubTitleURL, 'params': {}}

                    #Get Subtitle Settings
                    with database.database.Database(self.EmbyServer.Utils, 'video', False) as videodb:
                        videodb.cursor.execute(core.queries_videos.get_settings, (self.KodiFileID,))
                        FileSettings = videodb.cursor.fetchone()

                    if FileSettings:
                        EnableSubtitle = bool(FileSettings[9])
                    else:
                        if self.EmbyServer.Utils.DefaultVideoSettings:
                            EnableSubtitle = self.EmbyServer.Utils.DefaultVideoSettings['ShowSubtitles']
                        else:
                            EnableSubtitle = False

                    if Data[4]:
                        SubtileLanguage = Data[4]
                    else:
                        SubtileLanguage = "unknown"

                    Filename = self.EmbyServer.Utils.PathToFilenameReplaceSpecialCharecters(str(CounterSubTitle) + "." + SubtileLanguage + ".srt")
                    Path = self.EmbyServer.Utils.download_file_from_Embyserver(request, Filename, self.EmbyServer)

                    if Path:
                        self.Player.setSubtitles(Path)
                        self.Player.showSubtitles(EnableSubtitle)

    def LoadData(self, MediaIndex):
        VideoStreams = self.emby_dbT.get_videostreams(self.EmbyID, MediaIndex)
        AudioStreams = self.emby_dbT.get_AudioStreams(self.EmbyID, MediaIndex)

        if not VideoStreams:
            self.LOG.warning("[ VideoStreams not found ] %s" % self.EmbyID)
            return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + self.MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

        self.Player.Transcoding = self.IsTranscoding(VideoStreams[0][9], VideoStreams[0][3]) #add codec from videostreams, Bitrate (from file)

        if self.Player.Transcoding:
            SubtitleIndex = -1
            AudioIndex = -1
            Subtitles = []
            Subtitles = self.emby_dbT.get_Subtitles(self.EmbyID, MediaIndex)

            if len(AudioStreams) >= 2:
                Selection = []

                for Data in AudioStreams:
                    Selection.append(Data[7])

                AudioIndex = self.EmbyServer.Utils.dialog("select", heading="Select Audio Stream:", list=Selection)

            if len(Subtitles) >= 1:
                Selection = []

                for Data in Subtitles:
                    Selection.append(Data[7])

                SubtitleIndex = self.EmbyServer.Utils.dialog("select", heading="Select Subtitle:", list=Selection)

            if AudioIndex <= 0 and SubtitleIndex < 0 and MediaIndex <= 0: #No change -> resume
                return self.GETTranscodeURL(self.Filename, False, False)

            if AudioIndex <= 0:
                AudioIndex = 0

            if SubtitleIndex < 0:
                Subtitle = None
            else:
                Subtitle = Subtitles[SubtitleIndex]

            return self.UpdateItem(self.MediaSources[MediaIndex], AudioStreams[AudioIndex], Subtitle)

        if MediaIndex == 0:
            self.SubTitlesAdd()
            return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/stream?static=true&MediaSourceId=" + self.MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&api_key=" + self.EmbyServer.Data['auth.token'] + "&" + self.Filename

        return self.UpdateItem(self.MediaSources[MediaIndex], AudioStreams[0], False)

    def GETTranscodeURL(self, Filename, Audio, Subtitle):
        TranscodingVideo = ""
        TranscodingAudio = ""

        if Subtitle:
            Subtitle = "&SubtitleStreamIndex=" + Subtitle
        else:
            Subtitle = ""

        if Audio:
            Audio = "&AudioStreamIndex=" + Audio
        else:
            Audio = ""

        if self.TargetVideoBitrate:
            TranscodingVideo = "&VideoBitrate=" + str(self.TargetVideoBitrate)

        if self.TargetAudioBitrate:
            TranscodingAudio = "&AudioBitrate=" + str(self.TargetAudioBitrate)

        if Filename:
            Filename = "&stream-" + Filename

        return self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID + "/master.m3u8?api_key=" + self.EmbyServer.Data['auth.token'] + "&MediaSourceId=" + self.MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&VideoCodec=" + self.EmbyServer.Utils.Settings.VideoCodecID + "&AudioCodec=" + self.EmbyServer.Utils.Settings.AudioCodecID + TranscodingVideo + TranscodingAudio + Audio + Subtitle + "&TranscodeReasons=" + self.TranscodeReasons + Filename

    def SizeToText(self, size):
        suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
        suffixIndex = 0

        while size > 1024 and suffixIndex < 4:
            suffixIndex += 1
            size = size / 1024.0

        return "%.*f%s" % (2, size, suffixes[suffixIndex])

    def GETPlaySessionId(self):
        self.Player.PlaySessionId = str(uuid.uuid4()).replace("-", "")
        self.Player.MediasourceID = self.MediasourceID
        return self.Player.PlaySessionId

    def IsTranscoding(self, Bitrate, Codec):
        if self.EmbyServer.Utils.Settings.transcodeH265:
            if Codec in ("h265", "hevc"):
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.Settings.transcodeDivx:
            if Codec == "msmpeg4v3":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.Settings.transcodeXvid:
            if Codec == "mpeg4":
                self.IsTranscodingByCodec(Bitrate)
                return True
        elif self.EmbyServer.Utils.Settings.transcodeMpeg2:
            if Codec == "mpeg2video":
                self.IsTranscodingByCodec(Bitrate)
                return True

        self.TargetVideoBitrate = self.EmbyServer.Utils.Settings.VideoBitrate
        self.TargetAudioBitrate = self.EmbyServer.Utils.Settings.AudioBitrate
        self.TranscodeReasons = "ContainerBitrateExceedsLimit"
        return Bitrate >= self.TargetVideoBitrate

    def IsTranscodingByCodec(self, Bitrate):
        if Bitrate >= self.EmbyServer.Utils.Settings.VideoBitrate:
            self.TranscodeReasons = "ContainerBitrateExceedsLimit"
            self.TargetVideoBitrate = self.EmbyServer.Utils.Settings.VideoBitrate
            self.TargetAudioBitrate = self.EmbyServer.Utils.Settings.AudioBitrate
        else:
            self.TranscodeReasons = "VideoCodecNotSupported"
            self.TargetVideoBitrate = 0
            self.TargetAudioBitrate = 0

    def GetParametersFromURLQuery(self):
        Type = self.IncommingData[1:]
        self.Type = Type[:Type.find("/")]
        Temp = self.IncommingData[self.IncommingData.rfind("/") + 1:]
        Data = Temp.split("-")

        if len(Data[0]) < 10:
            self.Filename = self.IncommingData[self.IncommingData.find("stream-") + 7:]
            self.EmbyIDLast = Data[0]

            try:
                self.BitrateFromURL = int(Data[2])
            except:
                self.BitrateFromURL = 0

            self.Player.SyncPause = True
            self.Player.ItemSkipUpdate.append(Data[0])
            self.EmbyID = Data[0]
            self.MediasourceID = Data[1]

            if self.MediasourceID == "DYNAMIC":
                Result = self.EmbyServer.API.get_item(self.EmbyID)
                self.MediasourceID = Result['MediaSources'][0]['Id']

    def UpdateItem(self, MediaSource, AudioStream, Subtitle):
        if self.Type == "movie":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMovieDetails", "params":{"movieid":' + self.KodiID + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "trailer", "tagline", "plotoutline", "originaltitle",  "writer", "studio", "mpaa", "country", "imdbnumber", "set", "showlink", "top250", "votes", "sorttitle",  "dateadded", "tag", "userrating", "cast", "premiered", "setid", "art", "lastplayed", "uniqueid"]}}')
            Data = json.loads(result)
            Details = Data['result']['moviedetails']
        elif self.Type == "episode":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetEpisodeDetails", "params":{"episodeid":' + self.KodiID + ', "properties":["title", "playcount", "season", "episode", "showtitle", "plot", "rating", "resume", "streamdetails", "firstaired", "writer", "dateadded", "lastplayed",  "originaltitle", "seasonid", "specialsortepisode", "specialsortseason", "userrating", "votes", "cast", "art", "uniqueid"]}}')
            Data = json.loads(result)
            Details = Data['result']['episodedetails']
        elif self.Type == "musicvideo":
            result = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"VideoLibrary.GetMusicVideoDetails", "params":{"musicvideoid":' + self.KodiID + ', "properties":["title", "playcount", "plot", "genre", "year", "rating", "resume", "streamdetails", "director", "studio", "dateadded", "tag", "userrating", "premiered", "album", "artist", "track", "art", "lastplayed"]}}')
            Data = json.loads(result)
            Details = Data['result']['musicvideodetails']

        Filename = self.EmbyServer.Utils.PathToFilenameReplaceSpecialCharecters(MediaSource[4])

        if self.Player.Transcoding:
            if Subtitle:
                SubtitleStream = str(int(Subtitle[2]) + 2)
            else:
                SubtitleStream = ""

            URL = self.GETTranscodeURL(Filename, str(int(AudioStream[2]) + 1), SubtitleStream)
        else: #stream
            URL = self.EmbyServer.auth.get_serveraddress() + "/emby/videos/" + self.EmbyID +"/stream?static=true&api_key=" + self.EmbyServer.Data['auth.token'] + "&MediaSourceId=" + self.MediasourceID + "&PlaySessionId=" + self.GETPlaySessionId() + "&DeviceId=" + self.EmbyServer.Data['app.device_id'] + "&" + Filename

        li = self.EmbyServer.Utils.CreateListitem(self.Type, Details)

        if "3d" in MediaSource[8].lower():
            li.setPath(URL)
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            Index = playlist.getposition()
            playlist.add(URL, li, Index)
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "method":"Playlist.Remove", "params":{"playlistid":1, "position":' + str(Index + 1) + '}}')
            self.Player.PlayerReloadIndex = str(Index)
            self.Player.PlayerLastItemID = str(self.EmbyID)
            URL = "RELOAD"
        else:
            li.setPath("http://127.0.0.1:57578" + self.IncommingData)
            self.Player.updateInfoTag(li)
            self.SubTitlesAdd()
            self.Player.PlayerReloadIndex = "-1"
            self.Player.PlayerLastItemID = "-1"

        return URL
