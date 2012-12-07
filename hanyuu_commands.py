"""
All IRC related commands go here

Description of how commands are now handled and should be created

Handler creation:
    All handlers get the following arguments passed
    
        session:
            an irc.Session object having this handler loaded
        server:
            an irclib.ServerConnection object that triggered this handler
        nick:
            the IRC nickname that triggered this event
        channel:
            the IRC channel where this was triggered, can be None if private message
        message:
            the IRC message that triggered this handler as unicode object
        hostmask:
            the IRC hostmask of the nickname that triggered this event

Handler registration:
    Handlers should set their 'handler' attribute to a tuple with the following
        format.
        
        (event type, regular expression, allowed nicknames, allowed channels)
        
        event type:
            The type of event to trigger this handler on, currently only
            supports 'on_text'
            
        regular expression:
            A regex that is used to match against the incoming IRC message,
            if it's a match the handler will be called if the
            'allowed nicknames' and 'allowed channels' are True
            
        allowed nicknames:
            A constant or list of nicknames that are allowed to trigger this
            handler. Look in irc.py for the constants defined.
            
        allowed channels:
            Same as above but then with the channel that is allowed, do note
            that private messages always get accepted.
"""

import logging
import re
import config
import irc
import manager
import main
import random as _random
from datetime import timedelta, datetime

def tokenize(text):
    return text.lower().split(" ")

irc_colours = {"c": u"\x03", "c1": u"\x0301", "c2": u"\x0302",
            "c3": u"\x0303", "c4": u"\x0304", "c5": u"\x0305",
            "c6": u"\x0306", "c7": u"\x0307", "c8": u"\x0308",
            "c9": u"\x0309", "c10": u"\x0310", "c11": u"\x0311",
            "c12": u"\x0312", "c13": u"\x0313", "c14": u"\x0314",
            "c15": u"\x0315"}

def np(server, nick, channel, text, hostmask):
    status = manager.Status()
    np = manager.NP()
    if (status.online):
        message = u"Now playing:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=np.metadata, curtime=np.positionf,
            length=np.lengthf, listeners=status.listeners,
            max_listener=config.listener_max, faves=np.favecount,
            fs="" if (np.favecount == 1) else "s", 
            times=np.playcount,
            ts="" if (np.playcount == 1) else "s",
            lp=np.lpf,
            **irc_colours)
    else:
        message = u"Stream is currently down."
    server.privmsg(channel, message)
    
np.handler = ("on_text", r'[.!@]np$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def create_faves_code(server, nick, channel, text, hostmask):
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM enick WHERE `nick`=%s", (nick,))
        authcode = None
        if (cur.rowcount > 0):
            authcode = cur.fetchone()['authcode']
            print authcode
        if (not authcode):
            while 1:
                authcode = str(_random.getrandbits(24))
                cur.execute("SELECT * FROM enick WHERE `authcode`=%s", (authcode,))
                if (cur.rowcount == 0):
                    break
            cur.execute("INSERT INTO enick (nick, authcode) VALUES (%(nick)s, "
                        "%(authcode)s) ON DUPLICATE KEY UPDATE `authcode`="
                        "%(authcode)s", {"nick": nick, "authcode": authcode})
    server.privmsg(nick, "Your authentication code is: %s" % (authcode,))

create_faves_code.handler = ("on_text", r'SEND CODE',
                             irc.ALL_NICKS, irc.PRIVATE_MESSAGE)

def lp(server, nick, channel, text, hostmask):
    lastplayed = manager.LP().get()
    if (len(lastplayed) > 0):
        message = u"{c3}Last Played:{c} ".format(**irc_colours) + \
            " {c3}|{c} ".format(**irc_colours).join(
                                        [song.metadata for song in lastplayed])
    else:
        message = u"There is currently no last played data available"
    server.privmsg(channel, message)
    
lp.handler = ("on_text", r'[.!@]lp$', irc.ALL_NICKS, irc.ALL_CHANNELS)

def queue(server, nick, channel, text, hostmask):
    p = tokenize(text)
    if len(p) > 1:
        if p[1] == u"length":
            request_queue = regular_queue = requests = regulars = 0
            for song in manager.Queue().iter(None):
                if (song.type == manager.REQUEST):
                    request_queue += song.length
                    requests += 1
                elif (song.type == manager.REGULAR):
                    regular_queue += song.length
                    regulars += 1
            message = u"There are {req} requests ({req_time}), {norm} randoms ({norm_time}), total of {total} songs ({total_time})".\
                    format(**{'req_time': timedelta(seconds=request_queue),
                    'norm_time': timedelta(seconds=regular_queue),
                    'total_time': timedelta(seconds=request_queue+regular_queue),
                    'req': requests,
                    'norm': regulars,
                    'total': requests+regulars})
    else:
        queue = list(manager.Queue())
        if (len(queue) > 0):
            message = u"{c3}Queue:{c} ".format(**irc_colours) + \
                " {c3}|{c} ".format(**irc_colours)\
                .join([song.metadata for song in queue])
        else:
            message = u"No queue at the moment"
    server.privmsg(channel, message)

queue.handler = ("on_text", r'[.!@]q(ueue)?', irc.ALL_NICKS, irc.ALL_CHANNELS)

def dj(server, nick, channel, text, hostmask):
    tokens = text.split(' ')
    new_dj = " ".join(tokens[1:])
    if (new_dj != ''):
        if (server.hasaccess(channel, nick)):
            if (new_dj):
                if (new_dj == 'None'):
                    new_status = 'DOWN'
                elif (new_dj):
                    new_status = 'UP'
                topic = server.get_topic(channel)
                regex = re.compile(r"((.*?r/)(.*)(/dio.*?))\|(.*?)\|(.*)")
                result = regex.match(topic)
                if (result != None):
                    result = list(result.groups())
                    result[1:5] = u'|{c7} Stream:{c4} {status} {c7}DJ:{c4} {dj} {c11} http://r-a-d.io{c} |'.format(status=new_status, dj=new_dj, **irc_colours)
                    server.topic(channel, u"".join(result))
                    manager.DJ().name = new_dj
                else:
                    server.privmsg(channel, "Topic is the wrong format; can't set new topic")
        else:
            server.notice(nick, "You don't have the necessary privileges to do this.")
    else:
        server.privmsg(channel, "Current DJ: {c3}{dj}"\
                       .format(dj=manager.DJ().name, **irc_colours))
        
dj.handler = ("on_text", r'[.!@]dj.*', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def favorite(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])fave\b(?P<command>.*)", text, re.I|re.U)
    song = manager.NP()
    if match:
        mode, command = match.group("mode", "command")
        if (command.strip().lower() == "last"):
            song = manager.LP().get(1)[0]
        if (command.strip().isdigit()):
            id = int(command.strip())
            try:
                song = manager.Song(id=id)
            except:
                server.notice(nick, u"I don't know of a song with that ID...")
                return
    if (nick in song.faves):
        message = u"You already have {c3}'{song}'{c} favorited"\
            .format(song=song.metadata, **irc_colours)
    else:
        song.faves.append(nick)
        message = u"Added {c3}'{song}'{c} to your favorites."\
        .format(song=song.metadata, **irc_colours)
    server.notice(nick, message)
    
favorite.handler = ("on_text", r'[.!@]fave.*', irc.ALL_NICKS, irc.ALL_CHANNELS)

def unfavorite(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])unfave\b(?P<command>.*)", text, re.I|re.U)
    song = manager.NP()
    if match:
        mode, command = match.group("mode", "command")
        if (command.strip() == "last"):
            song = manager.LP().get(1)[0]
        if (command.strip().isdigit()):
            id = int(command.strip())
            try:
                song = manager.Song(id=id)
            except:
                server.notice(nick, u"I don't know of a song with that ID...")
                return
    if (nick in song.faves):
        song.faves.remove(nick)
        message = u"{c3}'{song}'{c} is removed from your favorites."\
            .format(song=song.metadata, **irc_colours)
    else:
        message = u"You don't have {c3}'{song}'{c} in your favorites."\
            .format(song=song.metadata, **irc_colours)
    server.notice(nick, message)
    
unfavorite.handler = ("on_text", r'[.!@]unfave.*',
                       irc.ALL_NICKS, irc.ALL_CHANNELS)

def set_curthread(server, nick, channel, text, hostmask):
    status = manager.Status()
    tokens = text.split(' ')
    threadurl = " ".join(tokens[1:]).strip()

    if threadurl != "" or len(tokens) > 1:
        if server.hasaccess(channel, nick):
            status.thread = threadurl

    message = u"Thread: {thread}".format(thread=status.thread)
    server.privmsg(channel, message)
    
set_curthread.handler = ("on_text", r'[.!@]thread(\s.*)?',
                          irc.ALL_NICKS, irc.MAIN_CHANNELS)

def topic(server, nick, channel, text, hostmask):
    tokens = text.split(' ')
    param = u" ".join(tokens[1:]).strip()
    if param != u"" or len(tokens) > 1: #i have NO IDEA WHATSOEVER why this is like this. just c/p from above
        if server.hasaccess(channel, nick):
            topic = server.get_topic(channel)
            print(u"Topic: {0}".format(topic))
            regex = re.compile(ur"(.*?r/)(.*)(/dio.*?)(.*)")
            result = regex.match(topic)
            if (result != None):
                result = list(result.groups())
                result[1] = u"{param}{c7}".format(param=param, **irc_colours)
                server.topic(channel, u"".join(result))
            else:
                server.privmsg(channel, "Topic is the wrong format, can't set new topic")

    else:
        topic = server.get_topic(channel)
        server.privmsg(channel, u"Topic: {topic}".format(topic=topic))
        
topic.handler = ("on_text", r'[.!@]topic(\s.*)?',
                  irc.ALL_NICKS, irc.MAIN_CHANNELS)

# TODO:
#     No way yet to kill the streamer, so this is TODO
killing_stream = False
def kill_afk(server, nick, channel, text, hostmask):
    if (server.isop(channel, nick)):
        try:
            stream = main.connect()
            stream.switch_dj(force=True)
            message = u"Forced AFK Streamer down, please connect in 15 seconds or less."
        except:
            message = u"Something went wrong, please punch Wessie (Tell him it was kill_afk)"
            logging.exception("AFK kill failed")
        server.privmsg(channel, message)
    else:
        server.notice(nick, u"You don't have high enough access to do this.")
        
kill_afk.handler = ("on_text", r'[.!@]kill',
                     irc.DEV_NICKS, irc.ALL_CHANNELS)

# TODO:
#    same as above
def shut_afk(server, nick, channel, text, hostmask):
    try:
        stream = main.connect()
        stream.switch_dj()
        message =  u'Disconnecting after current track. Start streaming a fallback song before the AFK Streamer disconnects, and dont spam this command.'
    except:
        message = u"Something went wrong, please try again."
        logging.exception("AFK cleankill failed")
    server.privmsg(channel, message)
        
shut_afk.handler = ("on_text", r'[.!@]cleankill',
                     irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def announce(server):
    np = manager.NP()
    status = manager.Status()
    if (len(np.faves) != 0 and np.length >= 30):
        message = u"Now starting:{c4} '{np}' {c}[{curtime}/{length}]({listeners}/{max_listener}), {faves} fave{fs}, played {times} time{ts}, {c3}LP:{c} {lp}".format(
            np=np.metadata, curtime=np.positionf,
            length=np.lengthf, listeners=status.listeners,
            max_listener=config.listener_max, faves=np.favecount,
            fs="" if (np.favecount == 1) else "s", 
            times=np.playcount,
            ts="" if (np.playcount == 1) else "s",
            lp=np.lpf,
            **irc_colours)
        server.privmsg("#r/a/dio", message)
    for nick in np.faves:
        if (server.inchannel("#r/a/dio", nick)):
            server.notice(nick, u"Fave: {0} is playing."\
                          .format(np.metadata))

announce.exposed = True

def request_announce(server, song):
    # UNLEASH THE HACK
    try:
        qsong = manager.Queue.get(song)
    except manager.QueueError:
        message = u"Requested:{c3} '{song}'".format(song=song.metadata,
                                                    **irc_colours)
    else:
        message = u"Requested:{c3} '{song}' ({until})".format(song=song.metadata,
                                                   until=qsong.until, **irc_colours)
    server.privmsg("#r/a/dio", message)

request_announce.exposed = True

def random(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])random\b(?P<command>.*)", text, re.I|re.U)
    if (match):
        mode, command = match.group("mode", "command")
    else:
        return
    def request_from_list(songs):
        while len(songs) > 0:
            song = songs.pop(_random.randrange(len(songs)))
            value = nick_request_song(song.id, hostmask)
            if (isinstance(value, tuple)):
                message = hanyuu_response(value[0], value[1])
                if (value[0] == 4):
                    continue
                else:
                    break
            elif (isinstance(value, manager.Song)):
                manager.Queue().append_request(song)
                request_announce(server, song)
                return
    if (command.lower().strip() == "fave"):
        songs = manager.Song.nick(nick, limit=None, tracks=True)
        request_from_list(songs)
        return
    elif (re.match(r"^fave (.*)", command)):
        fave_nick = re.match(r"^fave (.*)", command).groups()[1]
        songs = manager.Song.nick(fave_nick, limit=None, tracks=True)
        request_from_list(songs)
        return
    else:
        while True:
            song = manager.Song.random()
            value = nick_request_song(song.id, hostmask)
            if (isinstance(value, tuple)):
                message = hanyuu_response(value[0], value[1])
                if (value[0] == 4):
                    continue
                else:
                    break
            elif (isinstance(value, manager.Song)):
                manager.Queue().append_request(song)
                request_announce(server, song)
                return
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
random.handler = ("on_text", r'[.!@]random\b', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def lucky(server, nick, channel, text, hostmask):
    match = re.match(r"^(?P<mode>[.!@])lucky\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group("mode", "query")
    else:
        message = u"Hauu~ you didn't have a search query!"
        server.notice(nick, message)
        return
    result = manager.Song.search(query, limit=300)
    message = None
    for song in result:
        value = nick_request_song(song.id, hostmask)
        if (isinstance(value, tuple)):
            message = hanyuu_response(value[0], value[1])
            if (value[0] == 4):
                continue
            else:
                break
        elif (isinstance(value, manager.Song)):
            manager.Queue().append_request(song)
            request_announce(server, song)
            return
    if (message == None):
        message = u"Your query did not have any results"
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
lucky.handler = ("on_text", r'[.!@]lucky\b', irc.ALL_NICKS, irc.MAIN_CHANNELS)

def search(server, nick, channel, text, hostmask):
    def format_date(dt):
        if (dt == None):
            return 'Never'
        else:
            dt = datetime.now() - dt
            
            if dt.total_seconds < 86400:
                return '{h}h{m}m'.format(h=dt.total_seconds/3600, \
                    m=(dt.total_seconds%3600)/60)
            elif dt.days > 30:
                return '{m}m{d}d'.format(m=dt.days/30, d=dt.days%30)
            else:
                return '{d}d{h}h'.format(d=dt.days, h=dt.seconds/3600)

    match = re.match(r"^(?P<mode>[.!@])s(earch)?\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group('mode', 'query')
    else:
        message = u"Hauu~ you forgot a search query"
        server.notice(nick, message)
        return
    try:
        query = int(query);
        try:
            song = manager.Song(id=query)
            message = [u"{col_code}{meta} {c3}({trackid}){c} (LP:{c5}{lp}{c})"\
                .format(col_code=irc_colours['c3' if song.requestable else 'c4'],\
                    meta=song.metadata, trackid=song.id, \
                    lp=format_date(song.lpd), **irc_colours)]
        except (ValueError):
            message = []
    except (ValueError):
        message = [u"{col_code}{meta} {c3}({trackid}){c} (LP:{c5}{lp}{c})"\
            .format(col_code=irc_colours['c3' if song.requestable else 'c4'],\
                meta=song.metadata, trackid=song.id, \
                lp=format_date(song.lpd), **irc_colours) for \
                song in manager.Song.search(query)]
    if (len(message) > 0):
        message = u" | ".join(message)
    else:
        message = u"Your search returned no results"
    if (mode == "@"):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
search.handler = ("on_text", r'[.!@]s(earch)?\b',
                   irc.ALL_NICKS, irc.ALL_CHANNELS)

def request(server, nick, channel, text, hostmask):
    #this should probably be fixed to remove the nick thing, but i can't into regex
    match = re.match(r"^(?P<mode>[.!@])r(equest)?\s(?P<query>.*)", text, re.I|re.U)
    if (match):
        mode, query = match.group('mode', 'query')
    else:
        server.notice(nick, u"You forgot to give me an ID, do !search <query> first.")
        return
    try:
        trackid = int(query)
    except (ValueError):
        server.notice(nick, u"You need to give a number, try !search instead.")
        return
    else:
        response = nick_request_song(trackid, hostmask)
        if (isinstance(response, manager.Song)):
            song = manager.Song(trackid)
            manager.Queue().append_request(song)
            request_announce(server, song)
            return
        elif (response == 1): #wasn't song
            message = u"I don't know of any song with that id..."
        elif (isinstance(response, tuple)):
            message = hanyuu_response(response[0], response[1])
    server.privmsg(channel, message)

request.handler = ("on_text", r'[.!@]r(equest)?\b',
                   irc.ALL_NICKS, irc.MAIN_CHANNELS)

def lastrequest(server, nick, channel, text, hostmask):
    import time
    match = re.match(r"^(?P<mode>[.!@])lastr(equest)?.*", text, re.I|re.U)
    if (match):
        mode = match.group('mode')
    else:
        mode = '.'
    try:
        with manager.MySQLCursor() as cur:
            cur.execute("SELECT id, UNIX_TIMESTAMP(time) as timestamp \
                FROM `nickrequesttime` WHERE `host`=%s LIMIT 1;",
                (hostmask,))
            if (cur.rowcount == 1):
                row = cur.fetchone()
                host_time = int(row['timestamp'])
            else:
                host_time = 0
        time_since = int(time.time()) - host_time
        
        host_format = time.strftime('%b %d, %H:%M:%S %Z', time.localtime(host_time))
        since_format = small_time_format(time_since)
        can_request = time_since >= 3600
        
        if (host_time == 0):
            message = u"You don't seem to have requested on IRC before, {nick}!".format(nick=nick)
        else:
            message = u"You last requested at{c4} {time}{c}, which is{c4} {time_ago}{c} ago.{c3} {can_r}".format(
                time=host_format,
                time_ago=since_format,
                can_r=('You can request!' if can_request else ''),
                **irc_colours)
    except:
        logging.exception("Error in last request function")
        message = "Something broke! Hauu~"
    
    if (mode == '@'):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)

lastrequest.handler = ("on_text", r'[.!@]lastr(equest)?.*',
                       irc.ALL_NICKS, irc.MAIN_CHANNELS)

def info(server, nick, channel, text, hostmask):
    """Returns info about a song ID"""
    match = re.match(r'^(?P<mode>[.!@])i(nfo)?\s?(?P<id>\d+)?$')
    id = None
    if match:
        # We have an ID and stuff
        mode = match.group('mode')
        id = match.group('id')
    else:
        mode = None
    if id:
        # do shit with id
        try:
            song = manager.Song(id)
        except ValueError:
            message = u'ID Does not exist in database'
        except TypeError:
            message = u'ID Invalid.'
        else:
            message = u"Not implemented"
    else:
        # Show some kind of info lol
        message = u"Suck my dick"
    if (mode == '@'):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)
        
info.handler = ("on_text", r"[.!@]i(nfo)?", irc.ACCESS_NICKS, irc.MAIN_CHANNELS)

def request_help(server, nick, channel, text, hostmask):
    message = u"{nick}: http://r-a-d.io/search {c5}Thank you for listening to r/a/dio!".format(nick=nick, **irc_colours)
    server.privmsg(channel, message)
    
request_help.handler = ("on_text", r'.*how.+request',
                        irc.ALL_NICKS, irc.MAIN_CHANNELS)

def lastfm_listening(server, nick, channel, text, hostmask):
    import pylast
    message = u''
    match = re.match(r"[\-.@!]fm?\s(?P<nick>.*)", text, re.I|re.U)
    if match and match.group('nick') != '':
        nick = match.group('nick')
        
    with manager.MySQLCursor() as cur:
        cur.execute("SELECT * FROM lastfm WHERE nick=%s;", (nick.lower(),))
        if cur.rowcount == 1:
            row = cur.fetchone()
            username = row['user']
        else:
            username = nick
        network = pylast.LastFMNetwork(api_key=config.lastfm_key, api_secret=config.lastfm_secret)
        user = network.get_user(username)
        try:
            try:
                np = user.get_now_playing()
            except(IndexError): #broken api
                message = u"{c4}You should listen to something first!".format(**irc_colours)
            else:
                if np:
                    track = np
                else:
                    try:
                        track = user.get_recent_tracks()[0].track
                    except IndexError:
                        message = (u"{c4}You haven't listened to anything "
                                   u"recently.").format(**irc_colours)
                artist = track.artist.name
                title = track.title
                tags = [tag for tag in track.get_top_tags()]
                # Sort by weight
                tags.sort(key=lambda tag: int(tag.weight), reverse=True)
                tags = tags[:5] # Get top 5
                tags = [u"{c6}{tag}{c}".format(tag=tag.item.name, **irc_colours)
                        for tag in tags]
                message = (u"{c5}{username}{c} {state} listening to{c7} "
                           u"{artist}{c} -{c4} {title}{c} ({tags})").format(
                                    username=username, 
                                    artist=artist,
                                    title=title,
                                    state=(u"is currently" if np 
                                           else u"was last seen"),
                                    tags=(u"{c6}no tags{c}".format(**irc_colours)
                                          if len(tags) == 0 else 
                                          u", ".join(tags)), 
                                    **irc_colours)
        except pylast.WSError as err:
            message = u"{c4}{error}!".format(error=err.details, **irc_colours)
        except:
            logging.exception('Error in lastfm listen handler')
            message = u"{c4}Something went wrong!".format(**irc_colours)
    
    server.privmsg(channel, message)

lastfm_listening.handler = ("on_text", r'[\-.@!]fm(\s|$).*',
                          irc.ALL_NICKS, irc.MAIN_CHANNELS)

def lastfm_setuser(server, nick, channel, text, hostmask):
    import pylast
    match = re.match(r"[\-.@!]fma?\s(?P<user>.*)", text, re.I|re.U)
    message = u''
    if match and match.group('user') != '':
        username = match.group('user')
        network = pylast.LastFMNetwork(api_key=config.lastfm_key, api_secret=config.lastfm_secret)
        try:
            user = network.get_user(username)
            user.get_recent_tracks()
            with manager.MySQLCursor() as cur:
                cur.execute("SELECT * FROM lastfm WHERE nick=%s;", (nick.lower(),))
                if cur.rowcount == 1:
                    cur.execute("UPDATE lastfm SET user=%s WHERE nick=%s;", (username, nick.lower()))
                else:
                    cur.execute("INSERT INTO lastfm (user, nick) VALUES (%s, %s);", (username, nick.lower()))
            message = u"You are now registered as '{user}', {nick}!".format(user=username, nick=nick)
        except pylast.WSError as err:
            message = u"{c4}{error}!".format(error=err.details, **irc_colours)
    else:
        with manager.MySQLCursor() as cur:
            cur.execute("SELECT * FROM lastfm WHERE nick=%s;", (nick,))
            if cur.rowcount == 1:
                row = cur.fetchone()
                user = row['user']
                message = u"You are known as {user}.".format(user=user)
            else:
                message = u"You are not known as any last.fm username."
    server.notice(nick, message)

lastfm_setuser.handler = ("on_text", r'[\-.@!]fma.*',
                          irc.ALL_NICKS, irc.MAIN_CHANNELS)

def favorite_list(server, nick, channel, text, hostmask):
    match = re.match(r'^(?P<mode>[.!@])fl(ist)?($|\s)(?P<fnick>.*)', text, re.I|re.U)

    if (match):
        mode, fnick = match.group('mode', 'fnick')
        if (fnick == ''):
            fnick = nick
    else:
        server.notice(nick, 'Something went wrong')
        return

    message = u'Favorites are at: https://r-a-d.io/#/favorites/{nick}'.format(nick=fnick)

    if (mode == '@'):
        server.privmsg(channel, message)
    else:
        server.notice(nick, message)

favorite_list.handler = ('on_text', r'[.!@]fl(ist)?',
                         irc.ALL_NICKS, irc.MAIN_CHANNELS)


def hanyuu_response(response, delay):
    """Gets a chat response for a specific delay type and delay time.
    """
    self_messages = [(60*10, irc_colours['c3'] + u"Only less than ten minutes before you can request again!"),
                     (60*30, irc_colours['c2'] + u"You need to wait at most another half hour until you can request!"),
                     (60*61, irc_colours['c5'] + u"You still have quite a lot of time before you can request again..."),
                     (20000000, irc_colours['c4'] + u"No.")]
    song_messages = [(60*5, irc_colours['c3'] + u"Only five more minutes before I'll let you request that!"),
                     (60*15, irc_colours['c3'] + u"Just another 15 minutes to go for that song!"),
                     (60*40, irc_colours['c2'] + u"Only less than 40 minutes to go for that song!"),
                     (60*60, irc_colours['c2'] + u"You need to wait at most an hour for that song!"),
                     (60*60*4, irc_colours['c2'] + u"That song can be requested in a few hours!"),
                     (60*60*24, irc_colours['c5'] + u"You'll have to wait at most a day for that song..."),
                     (60*60*24*3, irc_colours['c5'] + u"That song can only be requested in a few days' time..."),
                     (60*60*24*7, irc_colours['c5'] + u"You might want to go do something else while you wait for that song."),
                     (20000000, irc_colours['c4'] + u"No.")]
    
    if (response == 2):
        for (d, r) in self_messages:
            if delay <= d:
                return r
    elif (response == 3):
        return u"I'm not streaming right now!"
    elif (response == 4):
        for (d, r) in song_messages:
            if delay <= d:
                return r
    return u"I have no idea what's happening~"

def small_time_format(t):
    if (t > 4*3600*24):
        return 'a long time'
    if (t == 0):
        return '0s'
    retval = ''
    b, t = divmod(t, 3600*24)
    if b != 0:
        retval += (str(b) + 'd')
    b, t = divmod(t, 3600)
    if b != 0:
        retval += (str(b) + 'h')
    b, t = divmod(t, 60)
    if b != 0:
        retval += (str(b) + 'm')
    b, t = divmod(t, 1)
    if b != 0:
        retval += (str(b) + 's')
    return retval

def nick_request_song(trackid, host=None):
    """Gets data about the specified song, for the specified hostmask.
    If the song didn't exist, it returns 1.
    If the host needs to wait before requesting, it returns 2.
    If there is no ongoing afk stream, it returns 3.
    If the play delay on the song hasn't expired yet, it returns 4.
    Else, it returns (artist, title).
    """
    # TODO:
    # rewrite shit man
    import time
    import requests
    with manager.MySQLCursor() as cur:
        try:
            song = manager.Song(trackid)
        except (ValueError):
            return 1
        can_request = True
        hostmask_id = None
        delaytime = 0;
        if host:
            cur.execute("SELECT id, UNIX_TIMESTAMP(time) as timestamp \
                FROM `nickrequesttime` WHERE `host`=%s LIMIT 1;",
                (host,))
            if cur.rowcount == 1:
                row = cur.fetchone()
                hostmask_id = int(row['id'])
                if int(time.time()) - int(row['timestamp']) < 3600:
                    can_request = False
                    delaytime = 3600 - (int(time.time()) - int(row['timestamp']))
        can_afk = True
        cur.execute("SELECT isafkstream FROM `streamstatus` WHERE `id`=0;")
        if cur.rowcount == 1:
            row = cur.fetchone()
            afk = row['isafkstream']
            if not afk == 1:
                can_afk = False
        else:
            can_afk = False
        can_song = True
        cur.execute("SELECT UNIX_TIMESTAMP(lastplayed) as lp, UNIX_TIMESTAMP(lastrequested) as lr, requestcount from `tracks` WHERE `id`=%s", (trackid,))
        if cur.rowcount == 1:
            row = cur.fetchone()
            song_lp = row['lp']
            song_lr = row['lr']
            if int(time.time()) - song_lp < requests.songdelay(row['requestcount']) or int(time.time()) - song_lr < requests.songdelay(row['requestcount']):
                can_song = False
                if delaytime == 0:
                    lp_delay = requests.songdelay(row['requestcount']) - (int(time.time()) - song_lp)
                    lr_delay = requests.songdelay(row['requestcount']) - (int(time.time()) - song_lr)
                    delaytime = max(lp_delay, lr_delay)
                        
        if (not can_request):
            return (2, delaytime)
        elif (not can_afk):
            return (3, 0)
        elif (not can_song):
            return (4, delaytime)
        else:
            if host:
                if hostmask_id:
                    cur.execute("UPDATE `nickrequesttime` SET `time`=NOW() WHERE `id`=%s LIMIT 1;", (hostmask_id,))
                else:
                    cur.execute("INSERT INTO `nickrequesttime` (host, time) VALUES (%s, NOW());", (host,))
            cur.execute("UPDATE `tracks` SET `lastrequested`=NOW() WHERE `id`=%s", (trackid,))
            return song
