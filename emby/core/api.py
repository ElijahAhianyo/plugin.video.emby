# -*- coding: utf-8 -*-
import helper.loghandler

class API():
    def __init__(self, EmbyServer):
        self.EmbyServer = EmbyServer
        self.LOG = helper.loghandler.LOG('EMBY.emby.api.API')
        self.LIMIT = min(int(self.EmbyServer.Utils.settings('limitIndex') or 15), 50)
        self.info = "Path,Genres,SortName,Studios,Writer,Taglines,LocalTrailerCount,Video3DFormat,OfficialRating,CumulativeRunTimeTicks,ItemCounts,PremiereDate,ProductionYear,Metascore,AirTime,DateCreated,People,Overview,CommunityRating,StartDate,CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,Status,EndDate,MediaSources,VoteCount,RecursiveItemCount,PrimaryImageAspectRatio,DisplayOrder,PresentationUniqueKey,OriginalTitle,AlternateMediaSources,PartCount"
        self.music_info = "Etag,Genres,SortName,Studios,Writer,PremiereDate,ProductionYear,OfficialRating,CumulativeRunTimeTicks,Metascore,CommunityRating,AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts,PresentationUniqueKey"
        self.browse_info = "DateCreated,EpisodeCount,SeasonCount,Path,Genres,Studios,Taglines,MediaStreams,Overview,Etag,ProductionLocations,Width,Height,RecursiveItemCount,ChildCount"

    #This confirms a single item from the library matches the view it belongs to.
    #Used to detect grouped libraries.
    def validate_view(self, library_id, item_id):
        try:
            result = self._get("Users/{UserId}/Items", {'ParentId': library_id, 'Recursive': True, 'Ids': item_id})
        except Exception:
            return False

        return bool(len(result['Items']))

    #Get emby user profile picture.
    def get_user_artwork(self, user_id):
        return "%s/emby/Users/%s/Images/Primary?Format=original" % (self.EmbyServer.Data['auth.server'], user_id)

    #Get dynamic listings
    def get_filtered_section(self, parent_id, media, limit, recursive, sort, sort_order, filters, extra, NoSort):
        if NoSort:
            params = {
                'ParentId': parent_id,
                'IncludeItemTypes': media,
                'IsMissing': False,
                'Recursive': recursive if recursive is not None else True,
                'Limit': limit,
                'ImageTypeLimit': 1,
                'IsVirtualUnaired': False,
                'Fields': self.browse_info
            }
        else:
            params = {
                'ParentId': parent_id,
                'IncludeItemTypes': media,
                'IsMissing': False,
                'Recursive': recursive if recursive is not None else True,
                'Limit': limit,
                'SortBy': sort or "SortName",
                'SortOrder': sort_order or "Ascending",
                'ImageTypeLimit': 1,
                'IsVirtualUnaired': False,
                'Fields': self.browse_info
            }

        if filters:
            if 'Boxsets' in filters:
                filters.remove('Boxsets')
                params['CollapseBoxSetItems'] = self.EmbyServer.Utils.settings('groupedSets.bool')

            params['Filters'] = ','.join(filters)

        if self.EmbyServer.Utils.settings('getCast.bool'):
            params['Fields'] += ",People"

        if media and 'Photo' in media:
            params['Fields'] += ",Width,Height"

        if extra is not None:
            params.update(extra)

        return self._get("Users/{UserId}/Items", params)

    def get_movies_by_boxset(self, boxset_id):
        for items in self.get_itemsSync(boxset_id, "Movie", False, None):
            yield items

    def get_episode_by_show(self, show_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': "{UserId}",
                'Fields': self.info
            }
        }

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_episode_by_season(self, show_id, season_id):
        query = {
            'url': "Shows/%s/Episodes" % show_id,
            'params': {
                'SeasonId': season_id,
                'EnableUserData': True,
                'EnableImages': True,
                'UserId': "{UserId}",
                'Fields': self.info
            }
        }

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_itemsSync(self, parent_id, item_type, basic, params):
        query = {
            'url': "Users/{UserId}/Items",
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

        for items in self._get_items(query, self.LIMIT):
            yield items

    def get_artists(self, parent_id, basic, params):
        query = {
            'url': "Artists",
            'params': {
                'UserId': "{UserId}",
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

        for items in self._get_items(query, self.LIMIT):
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
        Params = {
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

        return self._get("Users/{UserId}/Items", Params)['TotalRecordCount']

    def get_TotalRecordsArtists(self, parent_id):
        Params = {
            'UserId': "{UserId}",
            'ParentId': parent_id,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'EnableTotalRecordCount': True,
            'LocationTypes': "FileSystem,Remote,Offline",
            'Recursive': True,
            'Limit': 1
        }
        return self._get("Artists", Params)['TotalRecordCount']

    def _get_items(self, query, LIMIT):
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
                result = self._get(url, params) or {'Items': []}
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

    def emby_url(self, handler):
        return "%s/emby/%s" % (self.EmbyServer.Data['auth.server'], handler)

    def _http(self, action, url, request):
        request.update({'type': action, 'handler': url})
        return self.EmbyServer.http.request(request, None)

    def _get(self, handler, params):
        if not params:
            return self._http("GET", handler, {})

        return self._http("GET", handler, {'params': params})

    def _post(self, handler, json, params):
        if not json and params:
            return self._http("POST", handler, {'params': params})

        if json and not params:
            return self._http("POST", handler, {'json': json})

        if not json and not params:
            return self._http("POST", handler, {})

        return self._http("POST", handler, {'params': params, 'json': json})

    def _delete(self, handler, params):
        if not params:
            return self._http("DELETE", handler, {})

        return self._http("DELETE", handler, {'params': params})

    def try_server(self):
        return self._get("System/Info/Public", None)

    def sessions(self, handler, action, params, json):
        if action == "POST":
            return self._post("Sessions%s" % handler, json, params)

        if action == "DELETE":
            return self._delete("Sessions%s" % handler, params)

        return self._get("Sessions%s" % handler, params)

    def users(self, handler, action, params, json):
        if action == "POST":
            return self._post("Users/{UserId}%s" % handler, json, params)

        if action == "DELETE":
            return self._delete("Users/{UserId}%s" % handler, params)

        return self._get("Users/{UserId}%s" % handler, params)

    def items(self, handler, action, params, json):
        if action == "POST":
            return self._post("Items%s" % handler, json, params)

        if action == "DELETE":
            return self._delete("Items%s" % handler, params)

        return self._get("Items%s" % handler, params)

    def user_items(self, handler, params):
        return self.users("/Items%s" % handler, "GET", params, None)

    def shows(self, handler, params):
        return self._get("Shows%s" % handler, params)

    def videos(self, handler):
        return self._get("Videos%s" % handler, None)

    def artwork(self, item_id, art, max_width, ext, index):
        if index is None:
            return  self.emby_url("Items/%s/Images/%s?MaxWidth=%s&format=%s" % (item_id, art, max_width, ext))

        return self.emby_url("Items/%s/Images/%s/%s?MaxWidth=%s&format=%s" % (item_id, art, index, max_width, ext))

    def get_users(self, disabled, hidden):
        return self._get("Users", {
            'IsDisabled': disabled,
            'IsHidden': hidden
        })

    def get_public_users(self):
        return self._get("Users/Public", None)

    def get_user(self, user_id):
        return self.users("", "GET", None, None) if user_id is None else self._get("Users/%s" % user_id, None)

    def get_views(self):
        return self.users("/Views", "GET", None, None)

    def get_media_folders(self):
        return self.users("/Items", "GET", None, None)

    def get_item(self, item_id):
        return self.users("/Items/%s" % item_id, "GET", None, None)

    def get_items(self, item_ids):
        return self.users("/Items", "GET", {
            'Ids': ','.join(str(x) for x in item_ids),
            'Fields': self.info
        }, None)

    def get_sessions(self):
        return self.sessions("", "GET", {'ControllableByUserId': "{UserId}"}, None)

    def get_device(self):
        return self.sessions("", "GET", {'DeviceId': self.EmbyServer.Data['app.device_id']}, None)

    def post_session(self, session_id, url, params, data):
        return self.sessions("/%s/%s" % (session_id, url), "POST", params, data)

    def get_images(self, item_id):
        return self.items("/%s/Images" % item_id, "GET", None, None)

    def get_suggestion(self, media, limit):
        return self.users("/Suggestions", "GET", {
            'Type': media,
            'Limit': limit
        }, None)

    def search(self, term, media):
        return self._get("Search/Hints", {
            'UserId': "{UserId}",
            'SearchTerm': term.encode('utf-8'),
            'IncludeItemTypes': media
        })

    def get_recently_added(self, media, parent_id, limit):
        return self.user_items("/Latest", {
            'Limit': limit,
            'UserId': "{UserId}",
            'IncludeItemTypes': media,
            'ParentId': parent_id,
            'Fields': self.info
        })

    def get_next(self, index, limit):
        return self.shows("/NextUp", {
            'Limit': limit,
            'UserId': "{UserId}",
            'StartIndex': None if index is None else int(index)
        })

    def get_adjacent_episodes(self, show_id, item_id):
        return self.shows("/%s/Episodes" % show_id, {
            'UserId': "{UserId}",
            'AdjacentTo': item_id,
            'Fields': self.info
        })

    def get_genres(self, parent_id):
        return self._get("Genres", {
            'ParentId': parent_id,
            'UserId': "{UserId}",
            'Fields': self.info
        })

    def get_recommendation(self, parent_id, limit):
        return self._get("Movies/Recommendations", {
            'ParentId': parent_id,
            'UserId': "{UserId}",
            'Fields': self.info,
            'Limit': limit
        })

    def get_items_by_letter(self, parent_id, media, letter):
        return self.user_items("", {
            'ParentId': parent_id,
            'NameStartsWith': letter,
            'Fields': self.info,
            'Recursive': True,
            'IncludeItemTypes': media
        })

    def get_channels(self):
        return self._get("LiveTv/Channels", {
            'UserId': "{UserId}",
            'EnableImages': True,
            'EnableUserData': True
        })

    def get_intros(self, item_id):
        return self.user_items("/%s/Intros" % item_id, None)

    def get_additional_parts(self, item_id):
        return self.videos("/%s/AdditionalParts" % item_id)

    def get_local_trailers(self, item_id):
        return self.user_items("/%s/LocalTrailers" % item_id, None)

    def get_ancestors(self, item_id):
        return self.items("/%s/Ancestors" % item_id, "GET", {'UserId': "{UserId}"}, None)

    def get_items_theme_video(self, parent_id):
        return self.users("/Items", "GET", {
            'HasThemeVideo': True,
            'ParentId': parent_id,
            'Recursive': True
        }, None)

    def get_themes(self, item_id):
        return self.items("/%s/ThemeMedia" % item_id, "GET", {
            'UserId': "{UserId}",
            'InheritFromParent': True,
            'EnableThemeSongs': True,
            'EnableThemeVideos': True
        }, None)

    def get_items_theme_song(self, parent_id):
        return self.users("/Items", "GET", {
            'HasThemeSong': True,
            'ParentId': parent_id,
            'Recursive': True
        }, None)

    def get_plugins(self):
        return self._get("Plugins", None)

    def get_seasons(self, show_id):
        return self.shows("/%s/Seasons" % show_id, {
            'UserId': "{UserId}",
            'EnableImages': True,
            'Fields': self.info
        })

    def get_date_modified(self, date, parent_id, media):
        return self.users("/Items", "GET", {
            'ParentId': parent_id,
            'Recursive': True,
            'IsMissing': False,
            'IsVirtualUnaired': False,
            'IncludeItemTypes': media or None,
            'MinDateLastSaved': date,
            'Fields': self.info
        }, None)

    def get_userdata_date_modified(self, date, parent_id, media):
        return self.users("/Items", "GET", {
            'ParentId': parent_id,
            'Recursive': True,
            'IsMissing': False,
            'IsVirtualUnaired': False,
            'IncludeItemTypes': media or None,
            'MinDateLastSavedForUser': date,
            'Fields': self.info
        }, None)

    def refresh_item(self, item_id):
        return self.items("/%s/Refresh" % item_id, "POST", None, {
            'Recursive': True,
            'ImageRefreshMode': "FullRefresh",
            'MetadataRefreshMode': "FullRefresh",
            'ReplaceAllImages': False,
            'ReplaceAllMetadata': True
        })

    def favorite(self, item_id, option):
        return self.users("/FavoriteItems/%s" % item_id, "POST" if option else "DELETE", None, None)

    def get_system_info(self):
        return self._get("System/Configuration", None)

    def post_capabilities(self, data):
        return self.sessions("/Capabilities/Full", "POST", None, data)

    def session_add_user(self, session_id, user_id, option):
        return self.sessions("/%s/Users/%s" % (session_id, user_id), "POST" if option else "DELETE", None, None)

    def session_playing(self, data):
        return self.sessions("/Playing", "POST", None, data)

    def session_progress(self, data):
        return self.sessions("/Playing/Progress", "POST", None, data)

    def session_stop(self, data):
        return self.sessions("/Playing/Stopped", "POST", None, data)

    def item_played(self, item_id, watched):
        return self.users("/PlayedItems/%s" % item_id, "POST" if watched else "DELETE", None, None)

    def get_sync_queue(self, date, filters):
        return self._get("Emby.Kodi.SyncQueue/{UserId}/GetItems", {
            'LastUpdateDT': date,
            'filter': filters or None
        })

    def get_server_time(self):
        return self._get("Emby.Kodi.SyncQueue/GetServerDateTime", None)

    def get_play_info(self, item_id, profile, source_id, is_playback):
        return self.items("/%s/PlaybackInfo" % item_id, "POST", None, {
            'UserId': "{UserId}",
            'DeviceProfile': profile,
            'AutoOpenLiveStream': is_playback,
            'IsPlayback': is_playback,
            'MediaSourceId': source_id
        })

    def get_playbackinfo(self, item_id):
        return self.items("/%s/PlaybackInfo" % item_id, "POST", None, {
            'UserId': "{UserId}"
        })

    def get_live_stream(self, item_id, play_id, token, profile):
        return self._post("LiveStreams/Open", {
            'UserId': "{UserId}",
            'DeviceProfile': profile,
            'OpenToken': token,
            'PlaySessionId': play_id,
            'ItemId': item_id
        }, False)

    def close_live_stream(self, live_id):
        return self._post("LiveStreams/Close", {'LiveStreamId': live_id}, False)

    def close_transcode(self):
        return self._delete("Videos/ActiveEncodings", {'DeviceId': self.EmbyServer.Data['app.device_id']})

    def delete_item(self, item_id):
        return self.items("/%s" % item_id, "DELETE", None, None)
