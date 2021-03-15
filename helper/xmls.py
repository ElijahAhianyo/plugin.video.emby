# -*- coding: utf-8 -*-
import logging
import os
import xml.etree.ElementTree
import xbmc
from . import translate

class Xmls():
    def __init__(self, Utils):
        self.LOG = logging.getLogger("EMBY.helper.xmls.Xmls")
        self.Utils = Utils

    #Create master lock compatible sources.
    #Also add the kodi.emby.media source.
    def sources(self):
        path = self.Utils.translatePath('special://profile/')
        Filepath = os.path.join(path, 'sources.xml')

        try:
            xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
        except Exception:
            xmlData = xml.etree.ElementTree.Element('sources')
            video = xml.etree.ElementTree.SubElement(xmlData, 'video')
            files = xml.etree.ElementTree.SubElement(xmlData, 'files')
            xml.etree.ElementTree.SubElement(video, 'default', attrib={'pathversion': "1"})
            xml.etree.ElementTree.SubElement(files, 'default', attrib={'pathversion': "1"})

        video = xmlData.find('video')
        count_http = 1
        count_smb = 1

        for source in xmlData.findall('.//path'):
            if source.text == 'smb://':
                count_smb -= 1
            elif source.text == 'http://':
                count_http -= 1

            if not count_http and not count_smb:
                break
        else:
            for protocol in ('smb://', 'http://'):
                if (protocol == 'smb://' and count_smb > 0) or (protocol == 'http://' and count_http > 0):
                    source = xml.etree.ElementTree.SubElement(video, 'source')
                    xml.etree.ElementTree.SubElement(source, 'name').text = "Emby"
                    xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = protocol
                    xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"

        try:
            files = xmlData.find('files')

            if files is None:
                files = xml.etree.ElementTree.SubElement(xmlData, 'files')

            for source in xmlData.findall('.//path'):
                if source.text == 'http://kodi.emby.media':
                    break
            else:
                source = xml.etree.ElementTree.SubElement(files, 'source')
                xml.etree.ElementTree.SubElement(source, 'name').text = "kodi.emby.media"
                xml.etree.ElementTree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
                xml.etree.ElementTree.SubElement(source, 'allowsharing').text = "true"
        except Exception as error:
            self.LOG.exception(error)

        self.Utils.indent(xmlData)
        self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), Filepath)

    #Create tvtunes.nfo
    def tvtunes_nfo(self, path, urls):
        try:
            xmlData = xml.etree.ElementTree.parse(path).getroot()
        except Exception:
            xmlData = xml.etree.ElementTree.Element('tvtunes')

        for elem in xmlData.iter('tvtunes'):
            for Filename in list(elem):
                elem.remove(Filename)

        for url in urls:
            xml.etree.ElementTree.SubElement(xmlData, 'file').text = url

        self.Utils.indent(xmlData)
        self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), path)

    #Track the existence of <cleanonupdate>true</cleanonupdate>
    #It is incompatible with plugin paths.
    def advanced_settings(self):
        if self.Utils.settings('useDirectPaths') != "0":
            return

        path = self.Utils.translatePath('special://profile/')
        Filepath = os.path.join(path, 'advancedsettings.xml')

        try:
            xmlData = xml.etree.ElementTree.parse(Filepath).getroot()
        except Exception:
            return

        video = xmlData.find('videolibrary')

        if video is not None:
            cleanonupdate = video.find('cleanonupdate')

            if cleanonupdate is not None and cleanonupdate.text == "true":
                self.LOG.warning("cleanonupdate disabled")
                video.remove(cleanonupdate)
                self.Utils.indent(xmlData)
                self.Utils.write_xml(xml.etree.ElementTree.tostring(xmlData, 'UTF-8'), path)
                self.Utils.dialog("ok", heading="{emby}", line1=translate._(33097))
                xbmc.executebuiltin('RestartApp')
                return True
