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
var noMyOnscroll;
var scrollReporter;
function myOnscroll() {
    if (scrollReporter) {
        window.clearTimeout(scrollReporter);
    }
    scrollReporter = window.setTimeout(scrolled, 200);
}
function scrolled() {
    var href = internalJumpPrefix + "scrolled" +
        "?scrollTop=" + document.body.scrollTop +
        "&scrollLeft=" + document.body.scrollLeft;
    if (!noMyOnscroll) {
        window.location.href = href;
    }
}
function myOnload() {
    if (window.location.search && window.location.search[0] === "?") {
        var search = window.location.search.split("?", 2);
        var args = search[1].split("&");
        for (var i = 0; i < args.length; i++) {
            var arg = args[i].split("=", 2);
            if (arg[0] === "scrollTop") {
                document.body.scrollTop = parseInt(arg[1]);
            }
            else if (arg[0] === "scrollLeft") {
                document.body.scrollLeft = parseInt(arg[1]);
            }
            else if (arg[0] === "noMyOnscroll") {
                noMyOnscroll = parseInt(arg[1]);
            }
        }
    }
    document.onscroll = myOnscroll;
}
