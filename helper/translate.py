# -*- coding: utf-8 -*-
import xbmc
import xbmcaddon

#Get add-on string. Returns in unicode
def _(string):
    if type(string) != int:
        string = STRINGS[string]

    result = xbmcaddon.Addon('plugin.video.emby-next-gen').getLocalizedString(string)

    if not result:
        result = xbmc.getLocalizedString(string)

    return result

STRINGS = {
    'addon_name': 29999,
    'playback_mode': 30511,
    'empty_user': 30613,
    'empty_user_pass': 30608,
    'empty_server': 30617,
    'network_credentials': 30517,
    'invalid_auth': 33009,
    'addon_mode': 33036,
    'native_mode': 33037,
    'cancel': 30606,
    'username': 30024,
    'password': 30602,
    'gathering': 33021,
    'boxsets': 30185,
    'movies': 30302,
    'tvshows': 30305,
    'fav_movies': 30180,
    'fav_tvshows': 30181,
    'fav_episodes': 30182,
    'task_success': 33203,
    'task_fail': 33204
}
