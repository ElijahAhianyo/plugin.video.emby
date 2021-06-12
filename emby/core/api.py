# -*- coding: utf-8 -*-
import helper.loghandler

class API():
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.LOG = helper.loghandler.LOG('EMBY.emby.api.API')
        self.info = "Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,Video3DFormat,OfficialRating,CumulativeRunTimeTicks,ItemCounts,PremiereDate,ProductionYear,Metascore,AirTime,DateCreated,People,Overview,CommunityRating,StartDate,CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,Status,EndDate,MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio,DisplayOrder,PresentationUniqueKey,OriginalTitle,AlternateMediaSources,PartCount"
        self.music_info = "Etag,Genres,SortName,Studios,Writer,PremiereDate,ProductionYear,OfficialRating,CumulativeRunTimeTicks,Metascore,CommunityRating,AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts,PresentationUniqueKey"
        self.browse_info = "Path"

        if self.EmbyServer.Utils.Settings.getDateCreated:
            self.browse_info += ",DateCreated"

        if self.EmbyServer.Utils.Settings.getGenres:
            self.browse_info += ",Genres"

        if self.EmbyServer.Utils.Settings.getStudios:
            self.browse_info += ",Studios"

        if self.EmbyServer.Utils.Settings.getTaglines:
            self.browse_info += ",Taglines"

        if self.EmbyServer.Utils.Settings.getOverview:
            self.browse_info += ",Overview"

        if self.EmbyServer.Utils.Settings.getProductionLocations:
            self.browse_info += ",ProductionLocations"

        if self.EmbyServer.Utils.Settings.getCast:
            self.browse_info += ",People"

    def _http(self, action, url, request):
        request.update({'type': action, 'handler': url})
        return self.EmbyServer.http.request(request, None)

    #Get emby user profile picture.
    def get_user_artwork(self, user_id):
        return "%s/emby/Users/%s/Images/Primary?Format=original" % (self.EmbyServer.Data['auth.server'], user_id)

    def browse_MusicByArtistId(self, Artist_id, Parent_id, Media, Extra):
        params = {
            'ParentId': Parent_id,
            'ArtistIds': Artist_id,
            'IncludeItemTypes': Media,
            'IsMissing': False,
            'Recursive': True,
            'Fields': self.browse_info
        }

        if Extra is not None:
            params.update(Extra)

        return self._http("GET", "Users/%s/Items" % self.EmbyServer.Data['auth.user_id'], {'params': params})

    def get_recently_added(self, media, parent_id, limit):
        params = {
            'Limit': limit,
            'IncludeItemTypes': media,
            'ParentId': parent_id,
            'Fields': self.browse_info
        }

        if media and 'Photo' in media:
            params['Fields'] += ",Width,Height"

        return self._http("GET", "Users/%s/Items/Latest" % self.EmbyServer.Data['auth.user_id'], {'params': params})

    #Get dynamic listings
    def get_filtered_section(self, data):
        if not 'ViewId' in data:
            data['ViewId'] = None

        if not 'media' in data:
            data['media'] = None

        if not 'limit' in data:
            data['limit'] = None

        if not 'recursive' in data:
            data['recursive'] = True

        params = {
            'ParentId': data['ViewId'],
            'IncludeItemTypes': data['media'],
            'Recursive': data['recursive'],
            'Limit': data['limit'],
            'Fields': self.browse_info
        }

        if 'random' in data:
            if data['random']:
                params['SortBy'] = "Random"

        if 'filters' in data:
            if 'Boxsets' in data['filters']:
                data['filters'].remove('Boxsets')
                params['CollapseBoxSetItems'] = self.EmbyServer.Utils.Settings.groupedSets

            params['Filters'] = ','.join(data['filters'])

        if data['media'] and 'Photo' in data['media']:
            params['Fields'] += ",Width,Height"

        if 'extra' in data:
            if data['extra'] is not None:
                params.update(data['extra'])

        return self._http("GET", "Users/%s/Items" % self.EmbyServer.Data['auth.user_id'], {'params': params})

    def get_movies_by_boxset(self, boxset_id):
        for items in self.get_itemsSync(boxset_id, "Movie", False, None):
            yield items

    def get_episode_by_show(self, show_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': self.EmbyServer.Data['auth.user_id'],
                'Fields': self.info
            }
        }

        for items in self._get_items(query):
            yield items

    def get_episode_by_season(self, show_id, season_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'SeasonId': season_id,
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': self.EmbyServer.Data['auth.user_id'],
                'Fields': self.info
            }
        }

        for items in self._get_items(query):
            yield items

    def get_itemsSync(self, parent_id, item_type, basic, params):
        query = {
            'url': "Users/%s/Items" % self.EmbyServer.Data['auth.user_id'],
            'params': {
                'ParentId': parent_id,
                'IncludeItemTypes': item_type,
                'Fields': "Etag,PresentationUniqueKey" if basic else self.info,
                'CollapseBoxSetItems': False,
                'IsVirtualUnaired': False,
                'EnableTotalRecordCount': False,
                'LocationTypes': "FileSystem,Remote,Offline",
                'IsMissing': False,
                'Recursive': True
            }
        }

        if params:
            query['params'].update(params)

        for items in self._get_items(query):
            yield items

    def get_artists(self, parent_id, basic, params):
        query = {
            'url': "Artists",
            'params': {
                'UserId': self.EmbyServer.Data['auth.user_id'],
                'ParentId': parent_id,
                'Fields': "Etag,PresentationUniqueKey" if basic else self.music_info,
                'CollapseBoxSetItems': False,
                'IsVirtualUnaired': False,
                'EnableTotalRecordCount': False,
                'LocationTypes': "FileSystem,Remote,Offline",
                'IsMissing': False,
                'Recursive': True
            }
        }

        if params:
            query['params'].update(params)

        for items in self._get_items(query):
            yield items

    def get_albums_by_artist(self, parent_id, artist_id, basic):
        params = {
            'ParentId': parent_id,
            'ArtistIds': artist_id
        }

        for items in self.get_itemsSync(None, "MusicAlbum", basic, params):
            yield items

    def get_songs_by_artist(self, parent_id, artist_id, basic):
        params = {
            'ParentId': parent_id,
            'ArtistIds': artist_id
        }

        for items in self.get_itemsSync(None, "Audio", basic, params):
            yield items

    def get_TotalRecordsRegular(self, parent_id, item_type):
        params = {
            'ParentId': parent_id,
            'IncludeItemTypes': item_type,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'EnableTotalRecordCount': True,
            'LocationTypes': "FileSystem,Remote,Offline",
            'Recursive': True,
            'Limit': 1
        }
        return self._http("GET", "Users/%s/Items" % self.EmbyServer.Data['auth.user_id'], {'params': params})['TotalRecordCount']

    def get_TotalRecordsArtists(self, parent_id):
        params = {
            'UserId': self.EmbyServer.Data['auth.user_id'],
            'ParentId': parent_id,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'EnableTotalRecordCount': True,
            'LocationTypes': "FileSystem,Remote,Offline",
            'Recursive': True,
            'Limit': 1
        }
        return self._http("GET", "Artists", {'params': params})['TotalRecordCount']

    def _get_items(self, query):
        LIMIT = int(self.EmbyServer.Utils.Settings.limitIndex)
        items = {
            'Items': [],
            'RestorePoint': {}
        }
        url = query['url']
        params = query.get('params', {})
        index = params.get('StartIndex', 0)

        while True:
            params['StartIndex'] = index
            params['Limit'] = LIMIT

            try:
                result = self._http("GET", url, {'params': params}) or {'Items': []}
            except Exception as error:
                self.LOG.error("ERROR: %s" % error)
                result = {'Items': []}

            if result['Items'] == []:
                items['TotalRecordCount'] = index
                break

            items['Items'].extend(result['Items'])
            items['RestorePoint'] = query
            yield items
            del items['Items'][:]
            index += LIMIT

    def artwork(self, item_id, art, max_width, ext, index):
        if index is None:
            return "%s/emby/Items/%s/Images/%s?MaxWidth=%s&format=%s" % (self.EmbyServer.Data['auth.server'], item_id, art, max_width, ext)

        return "%s/emby/Items/%s/Images/%s/%s?MaxWidth=%s&format=%s" % (self.EmbyServer.Data['auth.server'], item_id, art, index, max_width, ext)

    def get_users(self, disabled, hidden):
        return self._http("GET", "Users", {'params': {'IsDisabled': disabled, 'IsHidden': hidden}})

    def get_public_users(self):
        return self._http("GET", "Users/Public", {})

    def get_user(self, user_id):
        if user_id is None:
            return self._http("GET", "Users/%s" % self.EmbyServer.Data['auth.user_id'], {})

        return self._http("GET", "Users/%s" % user_id, {})

    def get_views(self):
        return self._http("GET", "Users/%s/Views" % self.EmbyServer.Data['auth.user_id'], {})

    def get_item(self, item_id):
        return self._http("GET", "Users/%s/Items/%s" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

    def get_items(self, item_ids):
        return self._http("GET", "Users/%s/Items" % self.EmbyServer.Data['auth.user_id'], {'params': {'Ids': ','.join(str(x) for x in item_ids), 'Fields': self.info}})

    def get_device(self):
        return self._http("GET", "Sessions", {'params': {'DeviceId': self.EmbyServer.Data['app.device_id']}})

    def get_genres(self, parent_id):
        return self._http("GET", "Genres", {'params': {'ParentId': parent_id, 'UserId': self.EmbyServer.Data['auth.user_id'], 'Fields': self.browse_info}})

    def get_channels(self):
        return self._http("GET", "LiveTv/Channels", {'params': {'UserId': self.EmbyServer.Data['auth.user_id'], 'EnableImages': True, 'EnableUserData': True}})

    def get_intros(self, item_id):
        return self._http("GET", "Users/%s/Items/%s/Intros" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

    def get_additional_parts(self, item_id):
        return self._http("GET", "Videos/%s/AdditionalParts" % item_id, {})

    def get_local_trailers(self, item_id):
        return self._http("GET", "Users/%s/Items/%s/LocalTrailers" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

    def get_ancestors(self, item_id):
        return self._http("GET", "Items/%s/Ancestors" % item_id, {'params': {'UserId': self.EmbyServer.Data['auth.user_id']}})

    def get_themes(self, item_id):
        return self._http("GET", "Items/%s/ThemeMedia" % item_id, {'params': {'UserId': self.EmbyServer.Data['auth.user_id'], 'InheritFromParent': True, 'EnableThemeSongs': True, 'EnableThemeVideos': True}})

    def get_plugins(self):
        return self._http("GET", "Plugins", {})

    def get_seasons(self, show_id):
        return self._http("GET", "Shows/%s/Seasons" % show_id, {'params': {'UserId': self.EmbyServer.Data['auth.user_id'], 'EnableImages': True, 'Fields': self.info}})

    def refresh_item(self, item_id):
        return self._http("POST", "Items/%s/Refresh" % item_id, {'params': {'Recursive': True, 'ImageRefreshMode': "FullRefresh", 'MetadataRefreshMode': "FullRefresh", 'ReplaceAllImages': False, 'ReplaceAllMetadata': True}})

    def favorite(self, item_id, option):
        if option:
            return self._http("POST", "Users/%s/FavoriteItems/%s" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

        return self._http("DELETE", "Users/%s/FavoriteItems/%s" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

    def get_system_info(self):
        return self._http("GET", "System/Configuration", {})

    def post_capabilities(self, data):
        return self._http("POST", "Sessions/Capabilities/Full", {'params': data})

    def session_add_user(self, session_id, user_id, option):
        if option:
            return self._http("POST", "Sessions/%s/Users/%s" % (session_id, user_id), {})

        return self._http("DELETE", "Sessions/%s/Users/%s" % (session_id, user_id), {})

    def session_playing(self, data):
        return self._http("POST", "Sessions/Playing", {'params': data})

    def session_progress(self, data):
        return self._http("POST", "Sessions/Playing/Progress", {'params': data})

    def session_stop(self, data):
        return self._http("POST", "Sessions/Playing/Stopped", {'params': data})

    def item_played(self, item_id, watched):
        if watched:
            return self._http("POST", "Users/%s/PlayedItems/%s" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

        return self._http("DELETE", "Users/%s/PlayedItems/%s" % (self.EmbyServer.Data['auth.user_id'], item_id), {})

    def get_sync_queue(self, date, filters):
        return self._http("GET", "Emby.Kodi.SyncQueue/%s/GetItems" % self.EmbyServer.Data['auth.user_id'], {'params': {'LastUpdateDT': date, 'filter': filters or None}})

    def close_transcode(self):
        return self._http("DELETE", "Videos/ActiveEncodings", {'params': {'DeviceId': self.EmbyServer.Data['app.device_id']}})

    def delete_item(self, item_id):
        return self._http("DELETE", "Items/%s" % item_id, {})
