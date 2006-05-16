from   wxPython.wx import wxNewId, wxSystemSettings_GetMetric, wxSYS_SCREEN_X, \
        wxSYS_SCREEN_Y, wxSplitterWindow, wxSashLayoutWindow, \
        EVT_WINDOW_DESTROY, wxEvtHandler

from wx.xrc import XRCCTRL, XRCID

from MiscEvent import KeyFunctionSink


class wxIdPool:
    def __init__(self):
        self.poolmap={}

    def __getattr__(self, name):
        """Returns a new wx-Id for each new string <name>.
 
        If the same name is given twice, the same id is returned.
        
        If the name is in the XRC id-table its value there will be returned
        """
        try:
            return XRCID(name)
        except:
            try:
                return self.poolmap[name]
            except KeyError:
                id=wxNewId()
                self.poolmap[name]=id
                return id


GUI_ID = wxIdPool()
GUI_ID.__doc__="All purpose standard Gui-Id-Pool"

 
class XrcControls:
    """
    Convenience wrapper for XRCCTRL
    """
    def __init__(self, basepanel):
        self.__basepanel = basepanel

    def __getattr__(self, name):
        return XRCCTRL(self.__basepanel, name)
        
    def __getitem__(self, name):
        return XRCCTRL(self.__basepanel, name)
    

def setWindowPos(win, pos=None, fullVisible=False):
    """
    Set position of a wxWindow, but ensure that the position is valid.
    If fullVisible is True, the window is moved to be full visible
    according to its current size. It is recommended to call
    setWindowSize first.
    """
    if pos is not None:
        currentX, currentY = pos
    else:
        currentX, currentY = win.GetPositionTuple()
        
    screenX = wxSystemSettings_GetMetric(wxSYS_SCREEN_X)
    screenY = wxSystemSettings_GetMetric(wxSYS_SCREEN_Y)
    
    # fix any crazy screen positions
    if currentX < 0:
        currentX = 10
    if currentY < 0:
        currentY = 10
    if currentX > screenX:
        currentX = screenX-100
    if currentY > screenY:
        currentY = screenY-100
        
    if fullVisible:
        sizeX, sizeY = win.GetSizeTuple()
        if currentX + sizeX > screenX:
            currentX = screenX - sizeX
        if currentY + sizeY > screenY:
            currentY = screenY - sizeY

    win.SetPosition((currentX, currentY))


def setWindowSize(win, size):
    """
    Set size of a wxWindow, but ensure that the size is valid
    """
    sizeX, sizeY = size
    screenX = wxSystemSettings_GetMetric(wxSYS_SCREEN_X)
    screenY = wxSystemSettings_GetMetric(wxSYS_SCREEN_Y)

    # don't let the window be > than the size of the screen
    if sizeX > screenX:
        sizeX = screenX-20
    if sizeY > screenY:
        currentY = screenY-20

    # set the size
    win.SetSize((sizeX, sizeY))


def getTextFromClipboard():
    """
    Retrieve text or unicode text from clipboard
    """
    from wxPython.wx import wxTheClipboard, wxDataObjectComposite, wxDataFormat, \
            wxCustomDataObject, wxDF_TEXT, wxDF_UNICODETEXT
    from StringOps import lineendToInternal, mbcsDec
    import array

    cb = wxTheClipboard
    cb.Open()
    try:
        dataob = wxDataObjectComposite()
        cdataob = wxCustomDataObject(wxDataFormat(wxDF_TEXT))
        udataob = wxCustomDataObject(wxDataFormat(wxDF_UNICODETEXT))
        cdataob.SetData("")
        udataob.SetData("")
        dataob.Add(udataob)
        dataob.Add(cdataob)

        if cb.GetData(dataob):
            if udataob.GetDataSize() > 0 and (udataob.GetDataSize() % 2) == 0:
                # We have unicode data
                # This might not work for all platforms:   # TODO Better impl.
                rawuni = udataob.GetData()
                arruni = array.array("u")
                arruni.fromstring(rawuni)
                realuni = lineendToInternal(arruni.tounicode())
                return realuni
            elif cdataob.GetDataSize() > 0:
                realuni = lineendToInternal(
                        mbcsDec(cdataob.GetData(), "replace")[0])
                return realuni
            else:
                return ""
        return None
    finally:
        cb.Close()


def copyTextToClipboard(text): 
    from wxPython.wx import wxTheClipboard, wxDataObjectComposite, wxDataFormat, \
            wxCustomDataObject, wxDF_TEXT, wxDF_UNICODETEXT
    from StringOps import lineendToOs, mbcsEnc
    import array

    cdataob = wxCustomDataObject(wxDataFormat(wxDF_TEXT))
    udataob = wxCustomDataObject(wxDataFormat(wxDF_UNICODETEXT))
    realuni = lineendToOs(text)
    arruni = array.array("u")
    arruni.fromunicode(realuni+u"\x00")
    rawuni = arruni.tostring()
    # print "Copy", repr(realuni), repr(rawuni), repr(mbcsenc(realuni)[0])
    udataob.SetData(rawuni)
    cdataob.SetData(mbcsEnc(realuni)[0]+"\x00")

    dataob = wxDataObjectComposite()
    dataob.Add(udataob)
    dataob.Add(cdataob)

    cb = wxTheClipboard
    cb.Open()
    try:
        cb.SetData(dataob)
    finally:
        cb.Close()


def keyDownToAccel(evt):
    from wxPython.wx import wxACCEL_ALT, wxACCEL_SHIFT, wxACCEL_CTRL, \
            wxACCEL_NORMAL
    """
    evt -- wx KeyEvent received from a key down event
    return: tuple (modifier, keycode) suitable e.g. as AcceleratorEntry
            (without event handling function)
    """
    keyCode = evt.GetKeyCode()
    
    modif = wxACCEL_NORMAL

    if evt.ShiftDown():
        modif |= wxACCEL_SHIFT
    if evt.ControlDown():
        modif |= wxACCEL_CTRL
    if evt.AltDown():
        modif |= wxACCEL_ALT
    
    return (modif, keyCode)

# see also GetAccelFromString in wxPython's _core.py


def cloneImageList(imgList):
    """
    Create a copy of an wxImageList
    """
    from wxPython.wx import wxImageList

    sz = imgList.GetSize(0)
    lng = imgList.GetImageCount()
    result = wxImageList(sz[0], sz[1], True, lng)

    for i in xrange(lng):
        result.AddIcon(imgList.GetIcon(i))

    return result


class wxKeyFunctionSink(wxEvtHandler, KeyFunctionSink):
    """
    A MiscEvent sink which dispatches events further to other functions.
    """
    __slots__ = ("evtSource", "ifdestroyed")


    def __init__(self, evtSource, ifdestroyed, activationTable):
        wxEvtHandler.__init__(self)
        KeyFunctionSink.__init__(self, activationTable)

        self.evtSource = evtSource
        self.ifdestroyed = ifdestroyed
        
        if self.evtSource is not None:
            self.evtSource.addListener(self)
        
        if self.ifdestroyed is not None:
            EVT_WINDOW_DESTROY(self.ifdestroyed, self.OnDestroy)


    def OnDestroy(self, evt):
        self.evtSource.removeListener(self)
        evt.Skip()


    def addAsListenerTo(self, evtSource):
        self.evtSource = evtSource
        self.evtSource.addListener(self)


#         """
#         Set an wxWindow object window. If this window is destroyed,
#         the sink automatically disconnects
#         """



# class SmartSashLayoutWindow(wxSashLayoutWindow):
#     def __init__(self, *args, **kwargs):
#         from wxPython.wx import EVT_SASH_DRAGGED
# 
#         wxSashLayoutWindow.__init__(self, *args, **kwargs)
#         
#         self.effectiveSashPos = 0
#         self.minimalEffectiveSashPos = 0
#         self.sashPos = 0
#         
#         self.SetMinimumSizeX(1)
#         self.SetMinimumSizeY(1)
# 
#         EVT_SASH_DRAGGED(self, self.GetId(), self.OnSashDragged)
# 
#     def align(self, al):
#         from wxPython.wx import wxLAYOUT_TOP, wxLAYOUT_BOTTOM, wxLAYOUT_LEFT, \
#                 wxLAYOUT_RIGHT, wxLAYOUT_HORIZONTAL, wxLAYOUT_VERTICAL, \
#                 wxSASH_TOP, wxSASH_BOTTOM, wxSASH_LEFT, wxSASH_RIGHT
#         
#         if al == wxLAYOUT_TOP:
#             self.SetOrientation(wxLAYOUT_HORIZONTAL)
#             self.SetAlignment(wxLAYOUT_TOP)
#             self.SetSashVisible(wxSASH_BOTTOM, True)
#         elif al == wxLAYOUT_BOTTOM:
#             self.SetOrientation(wxLAYOUT_HORIZONTAL)
#             self.SetAlignment(wxLAYOUT_BOTTOM)
#             self.SetSashVisible(wxSASH_TOP, True)
#         elif al == wxLAYOUT_LEFT:
#             self.SetOrientation(wxLAYOUT_VERTICAL)
#             self.SetAlignment(wxLAYOUT_LEFT)
#             self.SetSashVisible(wxSASH_RIGHT, True)
#         elif al == wxLAYOUT_RIGHT:
#             self.SetOrientation(wxLAYOUT_VERTICAL)
#             self.SetAlignment(wxLAYOUT_RIGHT)
#             self.SetSashVisible(wxSASH_LEFT, True)
# 
# 
#     def setSashPosition(self, pos):
#         from wxPython.wx import wxSizeEvent, wxLAYOUT_VERTICAL
# 
#         if self.GetOrientation() == wxLAYOUT_VERTICAL:
#             self.SetDefaultSize((pos, 1000))
#         else:
#             self.SetDefaultSize((1000, pos))
#             
#         self.sashPos = pos
#         if pos >= self.minimalEffectiveSashPos:
#             self.effectiveSashPos = pos
#             
#         parent = self.GetParent()
#         sevent = wxSizeEvent(parent.GetSize())
#         parent.ProcessEvent(sevent)
# 
#     def getSashPosition(self):
#         return self.sashPos
# 
# 
#     def setMinimalEffectiveSashPosition(self, minPos):
#         self.minimalEffectiveSashPos = minPos
# 
#     def setEffectiveSashPosition(self, ePos):
#         # TODO Check bounds
#         self.effectiveSashPos = ePos
# 
#     def getEffectiveSashPosition(self):
#         return self.effectiveSashPos
# 
# 
#     def isCollapsed(self):
#         return self.getSashPosition() < self.minimalEffectiveSashPos
# 
#     def collapseWindow(self):
#         if not self.isCollapsed():
#             self.setSashPosition(1)
# 
#     def uncollapseWindow(self):
#         if self.isCollapsed():
#             self.setSashPosition(self.effectiveSashPos)
# 
# 
#     def OnSashDragged(self, evt):
#         from wxPython.wx import wxLAYOUT_VERTICAL
# 
#         # print "OnSashDragged", repr((evt.GetDragRect().width, evt.GetDragRect().height))
# 
#         if self.GetOrientation() == wxLAYOUT_VERTICAL:
#             self.setSashPosition(evt.GetDragRect().width)
#         else:
#             self.setSashPosition(evt.GetDragRect().height)
# 
#         evt.Skip()


