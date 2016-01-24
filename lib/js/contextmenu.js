function myOncontextmenu() {
    var event = document.parentWindow.event;
    var target = event.srcElement;
    var href = internalJumpPrefix + "mouse/contextmenu/preview/body" +
        "?screenX=" + event.screenX +
        "&screenY=" + event.screenY +
        "&type=" + event.type +
        "&offset=";
    href += "-1"; // todo get text offset
    var nodeName = target.nodeName
    if (target.id) {
        href += "&id=" + target.id;
    }
    href += "&nodeName=" + nodeName;
    if (target.href) {
        href += "&href=" + target.href;
    }
    window.location.href = href
    return false;
}
