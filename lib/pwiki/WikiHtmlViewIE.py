from __future__ import with_statement

## import hotshot
## _prof = hotshot.Profile("hotshot.prf")

import cStringIO as StringIO
import urllib, os, os.path, traceback

import wx, wx.html

if wx.Platform == '__WXMSW__':
#     import wx.activex
    import wx.lib.iewin as iewin
    from WindowsHacks import getLongPath
else:
    iewin = None


# if wx.Platform == '__WXMSW__':
#     try:
#         # Generate dependencies for py2exe
#         import comtypes.gen._99AB80C4_5E19_4FD5_B3CA_5EF62FC3F765_0_1_0 as _dummy
#         import comtypes.gen.myole4ax as _dummy
#         import comtypes.gen._3050F1C5_98B5_11CF_BB82_00AA00BDCE0B_0_4_0 as _dummy
#         import comtypes.gen.MSHTML as _dummy
#         del _dummy
#     except:
#         pass

if False:
    # Generate dependencies for py2exe
    import comtypes.gen._99AB80C4_5E19_4FD5_B3CA_5EF62FC3F765_0_1_0 as _dummy
    import comtypes.gen.myole4ax as _dummy
    import comtypes.gen._3050F1C5_98B5_11CF_BB82_00AA00BDCE0B_0_4_0 as _dummy
    import comtypes.gen.MSHTML as _dummy



from WikiExceptions import *
from wxHelper import getAccelPairFromKeyDown, copyTextToClipboard, GUI_ID, \
        wxKeyFunctionSink, appendToMenuByMenuDesc

from MiscEvent import KeyFunctionSink

from StringOps import uniToGui, utf8Enc, utf8Dec, pathEnc, urlFromPathname, \
        urlQuote, pathnameFromUrl, flexibleUrlUnquote, longPathEnc

import DocPages
from TempFileSet import TempFileSet

from . import PluginManager



class LinkConverterForPreviewIe:
    """
    Faked link dictionary for HTML exporter
    """
    def __init__(self, wikiDocument):
        self.wikiDocument = wikiDocument

    def getLinkForWikiWord(self, word, default = None):
        if self.wikiDocument.isDefinedWikiLinkTerm(word):
            return urlQuote(u"http://internaljump/wikipage/%s" % word, u"/#:;@")
        else:
            return default

class LinkConverterForPreviewMoz:
    """
    Faked link dictionary for HTML exporter
    """
    def __init__(self, wikiDocument):
        self.wikiDocument = wikiDocument

    def getLinkForWikiWord(self, word, default = None):
        if self.wikiDocument.isDefinedWikiLinkTerm(word):
            return urlQuote(u"file://internaljump/wikipage/%s" % word, u"/#:;@")
        else:
            return default


class WikiHtmlViewIE(iewin.IEHtmlWindow):
    def __init__(self, presenter, parent, ID, drivingMoz):
        self.drivingMoz = drivingMoz

        if self.drivingMoz:
#             wx.activex.IEHtmlWindowBase.__init__(self, parent,    # wx.activex.CLSID(
            wx.lib.activex.ActiveXCtrl.__init__(self, parent,
                '{1339B54C-3453-11D2-93B9-000000000000}',
                ID, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
                name='MozHtmlWindow')
            self.LinkConverterForPreview = LinkConverterForPreviewMoz
        else:
#             wx.activex.IEHtmlWindowBase.__init__(self, parent,
            wx.lib.activex.ActiveXCtrl.__init__(self, parent,
#                 '{8856F961-340A-11D0-A96B-00C04FD705A2}',
                'Shell.Explorer.2', 
                ID, pos=wx.DefaultPosition, size=wx.DefaultSize, style=0,
                name='IEHtmlWindow')
            self.LinkConverterForPreview = LinkConverterForPreviewIe


        self._canGoBack = False
        self._canGoForward = False


        self.presenter = presenter

        self.presenterListener = wxKeyFunctionSink((
                ("loaded current wiki page", self.onLoadedCurrentWikiPage),
                ("reloaded current doc page", self.onReloadedCurrentPage),
                ("opened wiki", self.onOpenedWiki),
                ("closing current wiki", self.onClosingCurrentWiki)
#                 ("options changed", self.onOptionsChanged),
        ), self.presenter.getMiscEvent())

        self.__sinkApp = wxKeyFunctionSink((
                ("options changed", self.onOptionsChanged),
        ), wx.GetApp().getMiscEvent())

        self.__sinkDocPage = wxKeyFunctionSink((
                ("updated wiki page", self.onUpdatedWikiPage),
                ("changed live text", self.onChangedLiveText)
        ), self.presenter.getCurrentDocPageProxyEvent())

        self.visible = False
        self.outOfSync = True   # HTML content is out of sync with live content
        self.deferredScrollPos = None  # Used by scrollDeferred()

        self.currentLoadedWikiWord = None
        self.currentLoadedUrl = None  # Contains the URL of the temporary HTML
                # file without anchors

        self.anchor = None  # Name of anchor to jump to when view gets visible
        self.lastAnchor = None
        self.passNavigate = 0
        self._scrollLeft = 0
        self._scrollTop = 0

        # TODO Should be changed to presenter as controller
        self.exporterInstance = PluginManager.getExporterTypeDict(
                self.presenter.getMainControl(), False)[u"html_single"][0]\
                (self.presenter.getMainControl())

        # TODO More elegantly
        if self.drivingMoz:
            self.exporterInstance.exportType = u"html_previewMOZ"
        else:
            self.exporterInstance.exportType = u"html_previewIE"

        self.exporterInstance.tempFileSet = TempFileSet()
        self._updateTempFilePrefPath()

        self.exporterInstance.setWikiDocument(
                self.presenter.getWikiDocument())
        self.exporterInstance.setLinkConverter(
                self.LinkConverterForPreview(self.presenter.getWikiDocument()))

        # Create two temporary html files (IE 7 needs two to work)
        self.htpaths = [None, None]
        self.htpaths[0] = self.exporterInstance.tempFileSet.createTempFile(
                    u"", ".html", relativeTo="").decode("latin-1")
        self.htpaths[1] = self.exporterInstance.tempFileSet.createTempFile(
                    u"", ".html", relativeTo="").decode("latin-1")

        self.normHtpaths = [os.path.normcase(getLongPath(self.htpaths[0])),
                os.path.normcase(getLongPath(self.htpaths[1]))]
                
        self.currentHtpath = 0 # index into self.htpaths

#         iewin.EVT_BeforeNavigate2(self, self.GetId(), self.OnBeforeNavigate)

        wx.EVT_SET_FOCUS(self, self.OnSetFocus)
#         EVT_MOUSEWHEEL(self, self.OnMouseWheel)

        wx.EVT_MENU(self, GUI_ID.CMD_ACTIVATE_THIS, self.OnActivateThis)        
        wx.EVT_MENU(self, GUI_ID.CMD_ACTIVATE_NEW_TAB_THIS,
                self.OnActivateNewTabThis)
        wx.EVT_MENU(self, GUI_ID.CMD_ACTIVATE_NEW_TAB_BACKGROUND_THIS,
                self.OnActivateNewTabBackgroundThis)
        wx.EVT_MENU(self, GUI_ID.CMD_ACTIVATE_NEW_WINDOW_THIS,
                self.OnActivateNewWindowThis)
        wx.EVT_MENU(self, GUI_ID.CMD_CLIPBOARD_COPY_LINK_WORD,
                self.OnClipboardCopyLinkWord)

        wx.EVT_MENU(self, GUI_ID.CMD_OPEN_CONTAINING_FOLDER_THIS,
                self.OnOpenContainingFolderThis)


    def setLayerVisible(self, vis, scName=""):
        """
        Informs the widget if it is really visible on the screen or not
        """
        if not self.visible and vis:
            self.outOfSync = True   # Just to be sure
            self.refresh()

        if not vis:
            self.exporterInstance.tempFileSet.clear()

        self.visible = vis


    def close(self):
        self.setLayerVisible(False)
        try:
            os.remove(pathEnc(self.htpaths[0]))
        except:
            pass

        try:
            os.remove(pathEnc(self.htpaths[1]))
        except:
            pass
            # TODO: Option to show also these exceptions
            # traceback.print_exc()

        self.presenterListener.disconnect()
        self.__sinkApp.disconnect()
        self.__sinkDocPage.disconnect()


    def refresh(self):
        ## _prof.start()
        
        # Store position of currently displayed page, if any
        if self.currentLoadedWikiWord:
            try:
                prevPage = self.presenter.getWikiDocument().getWikiPage(
                        self.currentLoadedWikiWord)
                prevPage.setPresentation(self.GetViewStart(), 3)
            except WikiWordNotFoundException, e:
                pass
            except AttributeError:
                pass
            except NameError: #todo seems like we call GetViewStart on an unloaded page, why? (this probaly coursed an AttributeError error before introducing setScrollLeft)
                pass

        wikiPage = self.presenter.getDocPage()
        if isinstance(wikiPage,
                (DocPages.DataCarryingPage, DocPages.AliasWikiPage)) and \
                not wikiPage.checkFileSignatureAndMarkDirty():
            # Valid wiki page and invalid signature -> rebuild HTML page
            self.outOfSync = True

        if self.outOfSync:
#             self.currentLoadedWikiWord = None

            wikiDocument = self.presenter.getWikiDocument()
            if wikiDocument is None:
                self.currentLoadedWikiWord = None
                return

            if wikiPage is None:
                self.currentLoadedWikiWord = None
                return  # TODO Do anything else here?

            word = wikiPage.getWikiWord()
            if word is None:
                self.currentLoadedWikiWord = None
                return  # TODO Do anything else here?
            
            # Remove previously used temporary files
            self.exporterInstance.tempFileSet.clear()
            self.exporterInstance.buildStyleSheetList()

            content = self.presenter.getLiveText()

            html = self.exporterInstance.exportWikiPageToHtmlString(wikiPage)

            wx.GetApp().getInsertionPluginManager().taskEnd()
            
            if self.currentLoadedWikiWord == word and \
                    self.anchor is None:

                htpath = self.htpaths[self.currentHtpath]

                with open(htpath, "w") as f:
                    f.write(utf8Enc(html)[0])

                url = "file:" + urlFromPathname(htpath)
                self.currentLoadedUrl = url
                self.passNavigate += 1
#                 self.RefreshPage(iewin.REFRESH_COMPLETELY)

                #lx, ly = self.GetViewStart()
                url = self._TryAddScrollSearch(url)

                self.LoadUrl(url, iewin.NAV_NoReadFromCache | iewin.NAV_NoWriteToCache)
                #self.scrollDeferred(lx, ly)
            else:                        
                self.currentLoadedWikiWord = word

                self.currentHtpath = 1 - self.currentHtpath
                htpath = self.htpaths[self.currentHtpath]
                
                with open(htpath, "w") as f:
                    f.write(utf8Enc(html)[0])

                url = "file:" + urlFromPathname(htpath)
                self.currentLoadedUrl = url
    
                if self.anchor is not None:
                    url += "#" + self.anchor
    
                self.passNavigate += 1
                self.LoadUrl(url, iewin.NAV_NoReadFromCache | iewin.NAV_NoWriteToCache)
                self.lastAnchor = self.anchor
                
                if self.anchor is None:
                    lx, ly = wikiPage.getPresentation()[3:5]
                    self.scrollDeferred(lx, ly)

        else:  # Not outOfSync
            if self.anchor is not None:
                self.passNavigate += 1
                self.LoadUrl(self.currentLoadedUrl + u"#" + self.anchor)
                self.lastAnchor = self.anchor

        self.anchor = None
        self.outOfSync = False

        ## _prof.stop()

    def _TryAddScrollSearch(self, url, force = False):
        urlParts = url.split("#", 2)
        if len(urlParts) is 1 or urlParts[1] == "" or force:
            lx, ly = self.GetViewStart()
            return "%s?scrollLeft=%d&scrollTop=%d" % (urlParts[0], self._scrollLeft, self._scrollTop)
        return url


    # IE ActiveX wx mapping
    def GetViewStart(self):
        """
        Bridge IE ActiveX object to wx's ScrolledWindow.
        """
        # old IE only
        #body = self.ctrl.Document.body
        #return (body.scrollLeft, body.scrollTop)

        return self._scrollLeft, self._scrollTop

    def Scroll(self, x, y):
        """
        Bridge IE ActiveX object to wx's ScrolledWindow
        """
        # old IE only
        #body = self.ctrl.Document.body
        #body.scrollLeft = x
        #body.scrollTop = y



        url = self._TryAddScrollSearch(self.currentLoadedUrl, True)
        self.LoadUrl(url, iewin.NAV_NoReadFromCache | iewin.NAV_NoWriteToCache)
        pass


    def gotoAnchor(self, anchor):
        self.anchor = anchor
        if self.visible:
#             self.outOfSync = True
            self.refresh()

    def GetSelectedText(self):
        return self.GetStringSelection(False)


    def _updateTempFilePrefPath(self):
        wikiDocument = self.presenter.getWikiDocument()

        if wikiDocument is not None:
            self.exporterInstance.tempFileSet.setPreferredPath(
                    wikiDocument.getWikiTempDir())
        else:
            self.exporterInstance.tempFileSet.setPreferredPath(None)


    def onLoadedCurrentWikiPage(self, miscevt):
        self.anchor = miscevt.get("anchor")
        self.outOfSync = True
        if self.visible:
            self.refresh()


    def onReloadedCurrentPage(self, miscevt):
        """
        Called when already loaded page should be loaded again, mainly
        interesting if a link with anchor is activated
        """
        anchor = miscevt.get("anchor")
        if anchor:
            self.gotoAnchor(anchor)
#             self.anchor = anchor
#             if self.visible:
#                 self.refresh()

    def onOpenedWiki(self, miscevt):
        self.currentLoadedWikiWord = None

        self._updateTempFilePrefPath()
        self.exporterInstance.setWikiDocument(
                self.presenter.getWikiDocument())
        self.exporterInstance.setLinkConverter(
                self.LinkConverterForPreview(self.presenter.getWikiDocument()))

    def onClosingCurrentWiki(self, miscevt):
        pass


    def onOptionsChanged(self, miscevt):
        self.outOfSync = True
        self._updateTempFilePrefPath()
        if self.visible:
            self.refresh()

    def onUpdatedWikiPage(self, miscevt):
        if self.presenter.getConfig().getboolean("main",
                "html_preview_reduceUpdateHandling", False):
            return

        self.outOfSync = True
        if self.visible:
            self.refresh()

    def onChangedLiveText(self, miscevt):
        self.outOfSync = True


    def scrollDeferred(self, lx, ly):
        self.deferredScrollPos = (lx, ly)


    def DownloadComplete(self, this):
        if self.deferredScrollPos is not None:
            #we already set the scroll position from url 
            # (setting a new url here is asking for infinity loop, but what happen is that an external browser window open)
            #self.Scroll(self.deferredScrollPos[0], self.deferredScrollPos[1])
            pass


    def OnSetFocus(self, evt):
        try:
            if self.visible:
                self.refresh()
        except:
            traceback.print_exc()
            

#     def OnClipboardCopy(self, evt):
#         copyTextToClipboard(self.SelectionToText())



    def BeforeNavigate2(self, this, pDisp, URL, Flags, TargetFrameName,
                        PostData, Headers, Cancel):
                            
        Cancel[0] = False
        if self.passNavigate:
            self.passNavigate -= 1
            return
            
        if (not (Flags[0] and iewin.NAV_Hyperlink)) and \
                self.presenter.getConfig().getboolean("main",
                "html_preview_ieShowIframes", False):
            return

        href = URL[0]


        if self.drivingMoz:
            internaljumpPrefix = u"file://internaljump/"
        else:
            internaljumpPrefix = u"http://internaljump/"
            
        if href.startswith(internaljumpPrefix + u"wikipage/"):

            if self.drivingMoz:
                # Unlike stated, the Mozilla ActiveX control has some
                # differences to the IE control. For instance, it returns
                # here an UTF-8 URL-quoted string, while IE returns the
                # unicode as it is.
                href = utf8Dec(urllib.unquote(href.encode("ascii", "replace")))[0]

            Cancel[0] = True
            # Jump to another wiki page

            # First check for an anchor. In URLs, anchors are always
            # separated by '#' regardless which character is used
            # in the wiki syntax (normally '!')
            try:
                word, anchor = href[len(internaljumpPrefix) + 9:].split("#", 1)
            except ValueError:
                word = href[len(internaljumpPrefix) + 9:]
                anchor = None
            
            # unescape word
            word = urllib.unquote(word) # utf8Dec(urllib.unquote(word))[0]
            if anchor:
                anchor = urllib.unquote(anchor)  # utf8Dec(urllib.unquote(anchor))[0]

            # Now open wiki
            self.presenter.getMainControl().openWikiPage(
                    word, motionType="child", anchor=anchor)

#         elif href.startswith(internaljumpPrefix + u"action/scroll/selfanchor/"):
#             anchorFragment = href[len(internaljumpPrefix + u"action/scroll/selfanchor/"):]
#             self.gotoAnchor(anchorFragment)
#             evt.Cancel = True

        elif href == (internaljumpPrefix + u"action/history/back"):
            # Go back in history
            self.presenter.getMainControl().goBrowserBack()
            Cancel[0] = True

        elif href == (internaljumpPrefix + u"mouse/leftdoubleclick/preview/body"):
            pres = self.presenter
            mc = pres.getMainControl()

            paramDict = {"page": pres.getDocPage(), "presenter": pres,
                    "main control": mc}

            mc.getUserActionCoord().reactOnUserEvent(
                    u"mouse/leftdoubleclick/preview/body", paramDict)
            Cancel[0] = True

        elif href.startswith(internaljumpPrefix + u"mouse/contextmenu/preview/body?"):
            temp = href.split(u"?",1)[1]
            args = {}
            while not temp.startswith(u"href="):
                temp2 = temp.split(u"&",1)
                pair = temp2[0].split(u"=",1)
                args[pair[0]] = pair[1]
                if len(temp2) == 2:
                    temp = temp2[1]
                else:
                    temp = u""
                    break
            if temp.startswith(u"href="):
                args[u"href"] = temp.split(u"=",1)[1]
            self.ShowContextMenu(args)
            Cancel[0] = True

        elif href.startswith(internaljumpPrefix + u"scrolled?"):
            temp = href.split(u"?",1)[1]
            temp2 = temp.split(u"&");
            for tempPair in temp2:
                pair = tempPair.split(u"=",1)
                if pair[0] == "scrollTop":
                    self._scrollTop = int(pair[1])
                elif pair[0] == "scrollLeft":
                    self._scrollLeft = int(pair[1])
            Cancel[0] = True

        elif href.startswith(u"file:"):
            hrefSplit = href.split("#", 1)
            hrefNoFragment = hrefSplit[0]
            normedPath = os.path.normcase(getLongPath(pathnameFromUrl(hrefNoFragment)))
            if len(hrefSplit) == 2 and normedPath in self.normHtpaths:
                self.gotoAnchor(hrefSplit[1])
                Cancel[0] = True
            else:
                self.presenter.getMainControl().launchUrl(href)
                Cancel[0] = True
        else:
            self.presenter.getMainControl().launchUrl(href)
            Cancel[0] = True


    def StatusTextChange(self, status):
        if self.visible:
            if self.drivingMoz:
                internaljumpPrefix = u"file://internaljump/wikipage/"
            else:
                internaljumpPrefix = u"http://internaljump/wikipage/"

            if status.startswith(internaljumpPrefix):
                # First check for an anchor. In URLs, anchors are always
                # separated by '#' regardless which character is used
                # in the wiki syntax (normally '!')
                try:
                    wikiWord, anchor = status[len(internaljumpPrefix):].split(
                            u"#", 1)
                    anchor = flexibleUrlUnquote(anchor)
                except ValueError:
                    wikiWord = status[len(internaljumpPrefix):]
                    anchor = None
                    
                wikiWord = flexibleUrlUnquote(wikiWord)

                wikiDocument = self.presenter.getWikiDocument()
                if wikiDocument is None:
                    return
                    
                wikiWord = wikiDocument.getWikiPageNameForLinkTerm(wikiWord)

                if wikiWord is not None:
                    status = _(u"Link to page: %s") % wikiWord

            self.presenter.getMainControl().statusBar.SetStatusText(
                    uniToGui(status), 0)


    def ShowContextMenu(self, args):
        href = args.get("href")
        id = args.get("id")
        self.contextHref = href

        menu = wx.Menu()
        if href:
            if self.drivingMoz:
                internaljumpPrefix = u"file://internaljump/wikipage/"
            else:
                internaljumpPrefix = u"http://internaljump/wikipage/"

            if href.startswith(internaljumpPrefix):
                appendToMenuByMenuDesc(menu, _CONTEXT_MENU_INTERNAL_JUMP)
            else:
                appendToMenuByMenuDesc(menu, u"Activate;CMD_ACTIVATE_THIS")
                
                if href.startswith(u"file:") or \
                        href.startswith(u"rel://"):

                    appendToMenuByMenuDesc(menu,
                            u"Open Containing Folder;"
                            u"CMD_OPEN_CONTAINING_FOLDER_THIS")

        screenX = int(args["screenX"])
        screenY = int(args["screenY"])
        x,y = self.ScreenToClientXY(screenX, screenY)
        self.PopupMenuXY(menu, x, y)


    def _activateLink(self, href, tabMode=0):
        """
        Called if link was activated by clicking in the context menu, 
        therefore only links starting with "internaljump:wikipage/" can be
        handled.
        tabMode -- 0:Same tab; 2: new tab in foreground; 3: new tab in background
        """
        if self.drivingMoz:
            internaljumpPrefix = u"file://internaljump/"
        else:
            internaljumpPrefix = u"http://internaljump/"

        if href.startswith(internaljumpPrefix + u"wikipage/"):
            wikiPageRef = href[len(internaljumpPrefix) + 9:]
            if tabMode == 1024:
                # hack to copy content of dot node
                copyTextToClipboard(wikiPageRef)
                return

            # Jump to another wiki page
            
            # First check for an anchor. In URLs, anchors are always
            # separated by '#' regardless which character is used
            # in the wiki syntax (normally '!')
            try:
                word, anchor = wikiPageRef.split(u"#", 1)
            except ValueError:
                word = wikiPageRef
                anchor = None

            # open the wiki page
            if tabMode & 8 and self.presenter.hasLastTrackedPresenter():
                presenter = self.presenter.getLastTrackedPresenter()
            elif tabMode & 2:
                if tabMode == 6:
                    # New Window
                    presenter = self.presenter.getMainControl().\
                            createNewDocPagePresenterTabInNewFrame(word)
                else:
                    # New tab
                    presenter = self.presenter.getMainControl().\
                            createNewDocPagePresenterTab()
                    presenter.switchSubControl("preview", False)
            else:
                # Same tab
                presenter = self.presenter

            presenter.openWikiPage(word, motionType="child", anchor=anchor)

            if not tabMode & 1:
                # Show in foreground
#                 presenter.switchSubControl("preview", True)
                presenter.getMainControl().getMainAreaPanel().\
                        showPresenter(presenter)
                presenter.SetFocus()
#             else:
#                 presenter.switchSubControl("preview", False)
            return presenter

        elif href == internaljumpPrefix + u"action/history/back":
            # Go back in history
            self.presenter.getMainControl().goBrowserBack()

        elif href.startswith(u"#"):
            anchor = href[1:]
            if self.HasAnchor(anchor):
                self.ScrollToAnchor(anchor)
                # Workaround because ScrollToAnchor scrolls too far
                # Here the real scroll position is needed so
                # getIntendedViewStart() is not called
                lx, ly = self.GetViewStart()
                self.scrollDeferred(lx, ly-1)
            else:
                self.scrollDeferred(0, 0)
        else:
            self.presenter.getMainControl().launchUrl(href)


    def OnActivateThis(self, evt):
        self._activateLink(self.contextHref, tabMode=0)

    def OnActivateNewTabThis(self, evt):
        self._activateLink(self.contextHref, tabMode=2)

    def OnActivateNewTabBackgroundThis(self, evt):
        self._activateLink(self.contextHref, tabMode=3)

    def OnActivateNewWindowThis(self, evt):
        self._activateLink(self.contextHref, tabMode=6)

    def OnClipboardCopyLinkWord(self, evt):
        self._activateLink(self.contextHref, tabMode=1024)


    def OnOpenContainingFolderThis(self, evt):
        if not self.contextHref:
            return

        link = self.contextHref

        if link.startswith(u"rel://"):
            link = self.presenter.getWikiDocument().makeRelUrlAbsolute(link)

        if link.startswith(u"file:"):
            try:
                path = os.path.dirname(pathnameFromUrl(link))
                if not os.path.exists(longPathEnc(path)):
                    self.presenter.displayErrorMessage(
                            _(u"Folder does not exist"))
                    return

                OsAbstract.startFile(self.presenter.getMainControl(),
                        path)
            except IOError:
                pass   # Error message?


#     def OnKeyUp(self, evt):
#         acc = getAccelPairFromKeyDown(evt)
#         if acc == (wxACCEL_CTRL, ord('C')):
#             # Consume original clipboard copy function
#             pass
#         else:
#             evt.Skip()
#
#     def addZoom(self, step):
#         """
#         Modify the zoom setting by step relative to current zoom in
#         configuration.
#         """
#         zoom = self.presenter.getConfig().getint("main", "preview_zoom", 0)
#         zoom += step
#
#         self.presenter.getConfig().set("main", "preview_zoom", str(zoom))
#         self.outOfSync = True
#         self.refresh()
#
#
#
#     def OnKeyDown(self, evt):
#         print "OnKeyDown1"
#         acc = getAccelPairFromKeyDown(evt)
#         if acc == (wxACCEL_CTRL, ord('+')) or \
#                 acc == (wxACCEL_CTRL, WXK_NUMPAD_ADD):
#             self.addZoom(1)
#         elif acc == (wxACCEL_CTRL, ord('-')) or \
#                 acc == (wxACCEL_CTRL, WXK_NUMPAD_SUBTRACT):
#             self.addZoom(-1)
#         else:
#             evt.Skip()
#
#     def OnMouseWheel(self, evt):
#         if evt.ControlDown():
#             self.addZoom( -(evt.GetWheelRotation() // evt.GetWheelDelta()) )
#         else:
#             evt.Skip()




_CONTEXT_MENU_INTERNAL_JUMP = \
u"""
Activate;CMD_ACTIVATE_THIS
Activate New Tab;CMD_ACTIVATE_NEW_TAB_THIS
Activate New Tab Backgrd.;CMD_ACTIVATE_NEW_TAB_BACKGROUND_THIS
Activate New Window;CMD_ACTIVATE_NEW_WINDOW_THIS
Copy Word to Clipboard;CMD_CLIPBOARD_COPY_LINK_WORD
"""


# Entries to support i18n of context menus
if False:
    N_(u"Activate")
    N_(u"Activate New Tab")
    N_(u"Activate New Tab Backgrd.")
    N_(u"Activate New Window")
    N_(u"Copy Word to Clipboard")
