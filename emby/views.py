# -*- coding: utf-8 -*-
import os
import xml.etree.ElementTree
import xbmcvfs
import xbmcgui
import helper.loghandler
import helper.xmls as xmls
import helper.utils as Utils

if Utils.Python3:
    from urllib.parse import urlencode
else:
    from urllib import urlencode

limit = 25
SyncNodes = {
    'tvshows': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultTVShows.png'),
        ('recentlyadded', Utils.Translate(30170), 'DefaultRecentlyAddedEpisodes.png'),
        ('recentlyaddedepisodes', Utils.Translate(30175), 'DefaultRecentlyAddedEpisodes.png'),
        ('inprogress', Utils.Translate(30171), 'DefaultInProgressShows.png'),
        ('inprogressepisodes', Utils.Translate(30178), 'DefaultInProgressShows.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('random', Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', Utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', Utils.Translate(33218), 'DefaultYear.png'),
        ('actors', Utils.Translate(33219), 'DefaultActor.png'),
        ('tags', Utils.Translate(33220), 'DefaultTags.png'),
        ('unwatched', "Unwatched TV Shows", 'OverlayUnwatched.png'),
        ('unwatchedepisodes', "Unwatched Episodes", 'OverlayUnwatched.png'),
        ('studios', "Studios", 'DefaultStudios.png'),
        ('recentlyplayed', 'Recently played TV Show', 'DefaultMusicRecentlyPlayed.png'),
        ('recentlyplayedepisode', 'Recently played Episode', 'DefaultMusicRecentlyPlayed.png'),
        ('nextepisodes', Utils.Translate(30179), 'DefaultInProgressShows.png')
    ],
    'movies': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMovies.png'),
        ('recentlyadded', Utils.Translate(30174), 'DefaultRecentlyAddedMovies.png'),
        ('inprogress', Utils.Translate(30177), 'DefaultInProgressShows.png'),
        ('unwatched', Utils.Translate(30189), 'OverlayUnwatched.png'),
        ('sets', "Sets", 'DefaultSets.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('random', Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('recommended', Utils.Translate(30230), 'DefaultFavourites.png'),
        ('years', Utils.Translate(33218), 'DefaultYear.png'),
        ('actors', Utils.Translate(33219), 'DefaultActor.png'),
        ('tags', Utils.Translate(33220), 'DefaultTags.png'),
        ('studios', "Studios", 'DefaultStudios.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('directors', 'Directors', 'DefaultDirector.png'),
        ('countries', 'Countries', 'DefaultCountry.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'musicvideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', Utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', Utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('inprogress', Utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', Utils.Translate(30258), 'OverlayUnwatched.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'homevideos': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultMusicVideos.png'),
        ('recentlyadded', Utils.Translate(30256), 'DefaultRecentlyAddedMusicVideos.png'),
        ('years', Utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultGenre.png'),
        ('inprogress', Utils.Translate(30257), 'DefaultInProgressShows.png'),
        ('random', Utils.Translate(30229), 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('unwatched', Utils.Translate(30258), 'OverlayUnwatched.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('resolutionhd', "HD", 'DefaultIconInfo.png'),
        ('resolutionsd', "SD", 'DefaultIconInfo.png'),
        ('resolution4k', "4K", 'DefaultIconInfo.png')
    ],
    'music': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', Utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultMusicGenres.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
    ],
    'audiobooks': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', Utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultMusicGenres.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ],
    'podcasts': [
        ('letter', "A-Z", 'special://home/addons/plugin.video.emby-next-gen/resources/letter.png'),
        ('all', None, 'DefaultAddonMusic.png'),
        ('years', Utils.Translate(33218), 'DefaultMusicYears.png'),
        ('genres', "Genres", 'DefaultMusicGenres.png'),
        ('artists', "Artists", 'DefaultMusicArtists.png'),
        ('albums', "Albums", 'DefaultMusicAlbums.png'),
        ('recentlyaddedalbums', 'Recently added albums', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyaddedsongs', 'Recently added songs', 'DefaultMusicRecentlyAdded.png'),
        ('recentlyplayed', 'Recently played', 'DefaultMusicRecentlyPlayed.png'),
        ('randomalbums', 'Random albums', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png'),
        ('randomsongs', 'Random songs', 'special://home/addons/plugin.video.emby-next-gen/resources/random.png')
    ]
}
LOG = helper.loghandler.LOG('EMBY.emby.views.Views')


class Views:
    def __init__(self, Embyserver):
        self.EmbyServer = Embyserver
        self.ViewItems = {}
        self.ViewsData = {}
        self.Nodes = []

    def update_nodes(self):
        index = 0
        self.Nodes = []
        WhitelistedLibraryIDs = []

        for library_id, _, _ in self.EmbyServer.library.Whitelist:
            WhitelistedLibraryIDs.append(library_id)

        # Favorites
        for single in [{'Name': Utils.Translate('fav_movies'), 'Tag': "Favorite movies", 'MediaType': "movies"}, {'Name': Utils.Translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'MediaType': "tvshows"}, {'Name': Utils.Translate('fav_episodes'), 'Tag': "Favorite episodes", 'MediaType': "episodes"}]:
            add_favorites(index, single)
            index += 1

        for library_id in self.ViewItems:
            view = {'LibraryId': library_id, 'Name': Utils.StringDecode(self.ViewItems[library_id][0]), 'Tag': Utils.StringDecode(self.ViewItems[library_id][0]), 'MediaType': self.ViewItems[library_id][1], "Icon": self.ViewItems[library_id][2], 'NameClean': Utils.StringDecode(self.ViewItems[library_id][0]).replace(" ", "_")}

            if library_id in WhitelistedLibraryIDs:
                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    view['Tag'] = "-%s;" % view['Tag']

                if view['MediaType'] == 'mixed':
                    ViewName = view['Name']

                    for media in ('movies', 'tvshows', 'music'):
                        view['MediaType'] = media

                        if media == 'music':
                            view['Tag'] = "-%s;" % view['Tag']

                        node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                        view['Name'] = "%s / %s" % (ViewName, view['MediaType'])
                        add_playlist(playlist_path, view)
                        add_nodes(node_path, view)
                        self.window_nodes(view, False)
                elif view['MediaType'] == 'homevideos':
                    self.window_nodes(view, True)  # Add dynamic node supporting photos
                    view['MediaType'] = "movies"
                    node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                    add_playlist(playlist_path, view)
                    add_nodes(node_path, view)
                    self.window_nodes(view, False)
                else:
                    node_path, playlist_path = get_node_playlist_path(view['MediaType'])
                    add_playlist(playlist_path, view)
                    add_nodes(node_path, view)
                    self.window_nodes(view, False)
            else:
                self.window_nodes(view, True)

    def window_nodes(self, view, Dynamic):
        if not view['Icon']:
            if view['MediaType'] == 'tvshows':
                view['Icon'] = 'DefaultTVShows.png'
            elif view['MediaType'] in ('movies', 'homevideos'):
                view['Icon'] = 'DefaultMovies.png'
            elif view['MediaType'] == 'musicvideos':
                view['Icon'] = 'DefaultMusicVideos.png'
            elif view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                view['Icon'] = 'DefaultMusicVideos.png'
            else:
                view['Icon'] = Utils.FileIcon

        self.window_node(view, Dynamic)

    # Points to another listing of nodes
    def window_node(self, view, dynamic):
        NodeData = {}

        if dynamic:
            params = {
                'mode': "browse",
                'type': view['MediaType'],
                'name': view['Name'].encode('utf-8'),
                'server': self.EmbyServer.server_id
            }

            if view.get('LibraryId'):
                params['id'] = view['LibraryId']

            path = "plugin://%s/?%s" % (Utils.PluginId, urlencode(params))
            NodeData['title'] = "%s (%s)" % (view['Name'], self.EmbyServer.Name)
        else:
            if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                path = "library://music/emby_%s_%s" % (view['MediaType'], view['NameClean'])
            else:
                path = "library://video/emby_%s_%s" % (view['MediaType'], view['NameClean'])

            NodeData['title'] = view['Name']

        NodeData['path'] = path
        NodeData['id'] = view['LibraryId']
        NodeData['type'] = view['MediaType']
        NodeData['icon'] = view['Icon']
        self.Nodes.append(NodeData)

    def update_views(self):
        self.ViewsData = self.EmbyServer.API.get_views()['Items']
        Total = len(self.ViewsData)
        Counter = 1
        Progress = xbmcgui.DialogProgressBG()
        Progress.create("Emby", "Update views")

        for library in self.ViewsData:
            Percent = int(Counter / Total * 100)
            Counter += 1
            Progress.update(Percent, message="Update views")

            if library['Type'] == 'Channel' and library['Name'].lower() == "podcasts":
                library['MediaType'] = "podcasts"
            elif library['Type'] == 'Channel' or library['Name'].lower() == "local trailers" or library['Name'].lower() == "trailers":
                library['MediaType'] = "channels"
            else:
                library['MediaType'] = library.get('CollectionType', "mixed")

            # Cache artwork
            request = {'type': "GET", 'url': "%s/emby/Items/%s/Images/Primary" % (self.EmbyServer.server, library['Id']), 'params': {}}
            Filename = Utils.PathToFilenameReplaceSpecialCharecters("%s_%s" % (self.EmbyServer.Name, library['Id']))
            iconpath = os.path.join(Utils.FolderEmbyTemp, Filename)

            if not xbmcvfs.exists(iconpath):
                iconpath = Utils.download_file_from_Embyserver(request, Filename, self.EmbyServer)

            self.ViewItems[library['Id']] = [library['Name'], library['MediaType'], iconpath]

        Progress.close()

    # Remove playlist based based on LibraryId
    def delete_playlist_by_id(self, LibraryId):
        if self.ViewItems[LibraryId][1] in ('music', 'audiobooks', 'podcasts'):
            path = Utils.FolderPlaylistsMusic
        else:
            path = Utils.FolderPlaylistsVideo

        filename = 'emby_%s.xsp' % self.ViewItems[LibraryId][0].replace(" ", "_")
        PlaylistPath = os.path.join(path, filename)

        if xbmcvfs.exists(PlaylistPath):
            xbmcvfs.delete(PlaylistPath)

    def delete_node_by_id(self, LibraryId):
        mediatypes = []

        if self.ViewItems[LibraryId][1].find('Mixed:') != -1:
            mediatypes.append('movies')
            mediatypes.append('tvshows')
        else:
            mediatypes.append(self.ViewItems[LibraryId][1])

        for mediatype in mediatypes:
            if mediatype in ('music', 'audiobooks', 'podcasts'):
                path = Utils.FolderLibraryMusic
            else:
                path = Utils.FolderLibraryVideo

            SubFolder = 'emby_%s_%s/' % (mediatype, self.ViewItems[LibraryId][0].replace(" ", "_"))
            NodePath = os.path.join(path, SubFolder)

            if xbmcvfs.exists(NodePath):
                _, files = xbmcvfs.listdir(NodePath)

                for filename in files:
                    xbmcvfs.delete(os.path.join(NodePath, filename))

                SearchLetterFolder = os.path.join(NodePath, "letter")
                _, letterfolderfiles = xbmcvfs.listdir(SearchLetterFolder)

                for LetterFilename in letterfolderfiles:
                    xbmcvfs.delete(os.path.join(SearchLetterFolder, LetterFilename))

                xbmcvfs.rmdir(SearchLetterFolder)
                xbmcvfs.rmdir(NodePath)

def get_node_playlist_path(MediaType):
    if MediaType in ('music', 'audiobooks', 'podcasts'):
        node_path = Utils.FolderLibraryMusic
        playlist_path = Utils.FolderPlaylistsMusic
    else:
        node_path = Utils.FolderLibraryVideo
        playlist_path = Utils.FolderPlaylistsVideo

    return node_path, playlist_path

# Create or update the xsp file
def add_playlist(path, view):
    if not Utils.xspplaylists:
        return

    filepath = os.path.join(path, "emby_%s_%s.xsp" % (view['MediaType'], view['NameClean']))

    if xbmcvfs.exists(filepath):
        xmlData = xml.etree.ElementTree.parse(filepath).getroot()
    else:
        xmlData = xml.etree.ElementTree.Element('smartplaylist', {'type': view['MediaType']})
        xml.etree.ElementTree.SubElement(xmlData, 'name')
        xml.etree.ElementTree.SubElement(xmlData, 'match')

    name = xmlData.find('name')
    name.text = view['Name']
    match = xmlData.find('match')
    match.text = "all"

    for rule in xmlData.findall('.//value'):
        if rule.text == view['Tag']:
            break
    else:
        rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

    xmls.WriteXmlFile(filepath, xmlData)

def add_favorites(index, view):
    path = Utils.FolderLibraryVideo

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdir(path)

    filepath = os.path.join(path, "emby_%s.xml" % view['Tag'].replace(" ", "_"))

    if xbmcvfs.exists(filepath):
        xmlData = xml.etree.ElementTree.parse(filepath).getroot()
    else:
        if view['MediaType'] == 'episodes':
            xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "folder"})
        else:
            xmlData = xml.etree.ElementTree.Element('node', {'order': str(index), 'type': "filter"})

        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = 'DefaultFavourites.png'
        xml.etree.ElementTree.SubElement(xmlData, 'label')
        xml.etree.ElementTree.SubElement(xmlData, 'match')
        xml.etree.ElementTree.SubElement(xmlData, 'content')

    label = xmlData.find('label')
    label.text = "EMBY: %s" % view['Name']
    content = xmlData.find('content')
    content.text = view['MediaType']
    match = xmlData.find('match')
    match.text = "all"

    if view['MediaType'] != 'episodes':
        for rule in xmlData.findall('.//value'):
            if rule.text == view['Tag']:
                break
        else:
            rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': "tag", 'operator': "is"})
            xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

        node_all(xmlData)
    else:
        params = {
            'mode': "favepisodes"
        }
        path = "plugin://%s/?%s" % (Utils.PluginId, urlencode(params))
        node_favepisodes(xmlData, path)

    xmls.WriteXmlFile(filepath, xmlData)

# Create or update the video node file
def add_nodes(path, view):
    folder = os.path.join(path, "emby_%s_%s" % (view['MediaType'], view['NameClean']))

    if not xbmcvfs.exists(folder):
        xbmcvfs.mkdir(folder)

    # index.xml (root)
    filepath = os.path.join(folder, "index.xml")

    if not xbmcvfs.exists(filepath):
        xmlData = xml.etree.ElementTree.Element('node', {'order': "0"})
        xml.etree.ElementTree.SubElement(xmlData, 'label').text = "EMBY: %s (%s)" % (view['Name'], view['MediaType'])

        if view['Icon']:
            Icon = view['Icon']
        else:
            if view['MediaType'] == 'tvshows':
                Icon = 'DefaultTVShows.png'
            elif view['MediaType'] == 'movies':
                Icon = 'DefaultMovies.png'
            elif view['MediaType'] == 'musicvideos':
                Icon = 'DefaultMusicVideos.png'
            elif view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                Icon = 'DefaultMusicVideos.png'
            else:
                Icon = Utils.FileIcon

        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = Icon
        xmls.WriteXmlFile(filepath, xmlData)

    # specific nodes
    for node in SyncNodes[view['MediaType']]:
        if node[1]:
            xml_label = node[1]  # Specific
        else:
            xml_label = view['Name']  # All

        if node[0] == "letter":
            node_letter(view, folder, node)
        else:
            filepath = os.path.join(folder, "%s.xml" % node[0])

            if not xbmcvfs.exists(filepath):
                if node[0] == 'nextepisodes':
                    NodeType = 'folder'
                else:
                    NodeType = 'filter'

                xmlData = xml.etree.ElementTree.Element('node', {'order': str(SyncNodes[view['MediaType']].index(node)), 'type': NodeType})
                xml.etree.ElementTree.SubElement(xmlData, 'label').text = xml_label
                xml.etree.ElementTree.SubElement(xmlData, 'match').text = "all"
                xml.etree.ElementTree.SubElement(xmlData, 'content')
                xml.etree.ElementTree.SubElement(xmlData, 'icon').text = node[2]
                operator = "is"
                field = "tag"
                content = xmlData.find('content')

                if view['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    if node[0] in ("genres", "artists"):
                        content.text = "artists"
                        operator = "contains"
                        field = "disambiguation"

                    elif node[0] in ("years", "recentlyaddedalbums", "randomalbums", "albums"):
                        content.text = "albums"
                        operator = "contains"
                        field = "type"

                    elif node[0] in ("recentlyaddedsongs", "randomsongs", "all", "recentlyplayed"):
                        content.text = "songs"
                        operator = "contains"
                        field = "comment"
                else:
                    if node[0] in ("recentlyaddedepisodes", "inprogressepisodes", "recentlyplayedepisode"):
                        content.text = "episodes"
                    else:
                        content.text = view['MediaType']

                for rule in xmlData.findall('.//value'):
                    if rule.text == view['Tag']:
                        break
                else:
                    rule = xml.etree.ElementTree.SubElement(xmlData, 'rule', {'field': field, 'operator': operator})
                    xml.etree.ElementTree.SubElement(rule, 'value').text = view['Tag']

                if node[0] == 'nextepisodes':
                    node_nextepisodes(xmlData, view['Name'])
                else:
                    globals()['node_' + node[0]](xmlData)  # get node function based on node type

                xmls.WriteXmlFile(filepath, xmlData)

# Nodes
def node_letter(View, folder, node):
    Index = 1
    FolderPath = os.path.join(folder, "letter/")

    if not xbmcvfs.exists(FolderPath):
        xbmcvfs.mkdir(FolderPath)

    # index.xml
    FileName = os.path.join(FolderPath, "index.xml")

    if not xbmcvfs.exists(FileName):
        xmlData = xml.etree.ElementTree.Element('node')
        xmlData.set('order', '0')
        xmlData.set('type', "folder")
        xml.etree.ElementTree.SubElement(xmlData, "label").text = node[1]
        xml.etree.ElementTree.SubElement(xmlData, 'icon').text = Utils.translatePath(node[2])
        xmls.WriteXmlFile(FileName, xmlData)

    # 0-9.xml
    FileName = os.path.join(FolderPath, "0-9.xml")

    if not xbmcvfs.exists(FileName):
        xmlData = xml.etree.ElementTree.Element('node')
        xmlData.set('order', str(Index))
        xmlData.set('type', "filter")
        xml.etree.ElementTree.SubElement(xmlData, "label").text = "0-9"
        xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
            xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
        else:
            xml.etree.ElementTree.SubElement(xmlData, "content").text = View['MediaType']

        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
        xmlRule.text = View['Tag']

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
            xmlRule.set('field', "disambiguation")
            xmlRule.set('operator', "contains")
        else:
            xmlRule.set('field', "tag")
            xmlRule.set('operator', "is")

        xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")

        if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
            xmlRule.set('field', "artist")
        else:
            xmlRule.set('field', "sorttitle")

        xmlRule.set('operator', "startswith")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "0"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "1"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "2"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "3"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "4"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "5"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "6"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "7"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "8"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = "9"
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("&")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("Ä")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("Ö")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("Ü")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("!")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("(")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(")")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("@")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("#")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("$")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("^")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("*")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("-")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("=")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("+")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("{")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("}")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("[")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("]")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("?")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(":")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(";")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("'")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(",")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(".")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("<")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode(">")
        xml.etree.ElementTree.SubElement(xmlRule, "value").text = Utils.StringDecode("~")
        xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
        xmls.WriteXmlFile(FileName, xmlData)

        # Alphabetically
        FileNames = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]

        for FileName in FileNames:
            Index += 1
            FilePath = os.path.join(FolderPath, "%s.xml" % FileName)

            if not xbmcvfs.exists(FilePath):
                xmlData = xml.etree.ElementTree.Element('node')
                xmlData.set('order', str(Index))
                xmlData.set('type', "filter")
                xml.etree.ElementTree.SubElement(xmlData, "label").text = FileName
                xml.etree.ElementTree.SubElement(xmlData, "match").text = "all"

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    xml.etree.ElementTree.SubElement(xmlData, "content").text = "artists"
                else:
                    xml.etree.ElementTree.SubElement(xmlData, "content").text = View['MediaType']

                xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                xmlRule.text = View['Tag']

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    xmlRule.set('field', "disambiguation")
                    xmlRule.set('operator', "contains")
                else:
                    xmlRule.set('field', "tag")
                    xmlRule.set('operator', "is")

                xmlRule = xml.etree.ElementTree.SubElement(xmlData, "rule")
                xmlRule.text = FileName

                if View['MediaType'] in ('music', 'audiobooks', 'podcasts'):
                    xmlRule.set('field', "artist")
                else:
                    xmlRule.set('field', "sorttitle")

                xmlRule.set('operator', "startswith")
                xml.etree.ElementTree.SubElement(xmlData, 'order', {'direction': "ascending"}).text = "sorttitle"
                xmls.WriteXmlFile(FilePath, xmlData)

def node_all(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

def node_recentlyplayed(root):
    for rule in root.findall('.//order'):
        if rule.text == "lastplayed":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

def node_directors(root):
    for rule in root.findall('.//order'):
        if rule.text == "directors":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "directors"

    for rule in root.findall('.//group'):
        rule.text = "directors"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "directors"

def node_countries(root):
    for rule in root.findall('.//order'):
        if rule.text == "countries":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "countries"

    for rule in root.findall('.//group'):
        rule.text = "countries"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "countries"

def node_nextepisodes(root, LibraryName):
    path = "plugin://%s/?%s" % (Utils.PluginId, urlencode({'libraryname': LibraryName, 'mode': "nextepisodes", 'limit': 25}))

    for rule in root.findall('.//path'):
        rule.text = path
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'path').text = path

    for rule in root.findall('.//content'):
        rule.text = "episodes"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'content').text = "episodes"

def node_years(root):
    for rule in root.findall('.//order'):
        if rule.text == "title":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

    for rule in root.findall('.//group'):
        rule.text = "years"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "years"

def node_actors(root):
    for rule in root.findall('.//order'):
        if rule.text == "title":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

    for rule in root.findall('.//group'):
        rule.text = "actors"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "actors"

def node_artists(root):
    for rule in root.findall('.//order'):
        if rule.text == "artists":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "artists"

    for rule in root.findall('.//group'):
        rule.text = "artists"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "artists"

def node_albums(root):
    for rule in root.findall('.//order'):
        if rule.text == "albums":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "albums"

    for rule in root.findall('.//group'):
        rule.text = "albums"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "albums"

def node_studios(root):
    for rule in root.findall('.//order'):
        if rule.text == "title":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

    for rule in root.findall('.//group'):
        rule.text = "studios"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "studios"

def node_resolutionsd(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "lessthan"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_resolutionhd(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_resolution4k(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'videoresolution':
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "videoresolution", 'operator': "greaterthan"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "1080"

def node_tags(root):
    for rule in root.findall('.//order'):
        if rule.text == "title":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "title"

    for rule in root.findall('.//group'):
        rule.text = "tags"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "tags"

def node_recentlyadded(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

def node_inprogress(root):
    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'inprogress':
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_genres(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    for rule in root.findall('.//group'):
        rule.text = "genres"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "genres"

def node_unwatched(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

def node_unwatchedepisodes(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    content = root.find('content')
    content.text = "episodes"

def node_sets(root):
    for rule in root.findall('.//order'):
        if rule.text == "sorttitle":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    for rule in root.findall('.//group'):
        rule.text = "sets"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'group').text = "sets"

def node_random(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recommended(root):
    for rule in root.findall('.//order'):
        if rule.text == "rating":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "rating"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'rating':
            rule.find('value').text = "7"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "rating", 'operator': "greaterthan"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "7"

def node_recentlyepisodes(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

    content = root.find('content')
    content.text = "episodes"

def node_inprogressepisodes(root):
    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'inprogress':
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"

    content = root.find('content')
    content.text = "episodes"

def node_favepisodes(root, path):
    for rule in root.findall('.//path'):
        rule.text = path
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'path').text = path

    for rule in root.findall('.//content'):
        rule.text = "episodes"
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'content').text = "episodes"

def node_randomalbums(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_randomsongs(root):
    for rule in root.findall('.//order'):
        if rule.text == "random":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedsongs(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedalbums(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

def node_recentlyaddedepisodes(root):
    for rule in root.findall('.//order'):
        if rule.text == "dateadded":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

    for rule in root.findall('.//limit'):
        rule.text = str(limit)
        break
    else:
        xml.etree.ElementTree.SubElement(root, 'limit').text = str(limit)

    for rule in root.findall('.//rule'):
        if rule.attrib['field'] == 'playcount':
            rule.find('value').text = "0"
            break
    else:
        rule = xml.etree.ElementTree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
        xml.etree.ElementTree.SubElement(rule, 'value').text = "0"

def node_recentlyplayedepisode(root):
    for rule in root.findall('.//order'):
        if rule.text == "lastplayed":
            break
    else:
        xml.etree.ElementTree.SubElement(root, 'order', {'direction': "descending"}).text = "lastplayed"
