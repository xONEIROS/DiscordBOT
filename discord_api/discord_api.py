import json
import time
import urllib.request
import time
import math
import os
#import requests # only for DiscordApi.send_message, imported in method directly, no need to uncomment

def nop(x): return x

class OurException(Exception):
    pass

class BasicStdoutLog:
    def log(self, msg):
        print(msg)

class BasicRLRProcessor:
    def __init__(self):
        self.lastEndpoint = ''

    def notify(self, api, endpoint, seconds):
        print()
        print('waiting', seconds, 's for url', url)
        print()
        self.lastEndpoint = endpoint
        api.maxQueriesPerSecond = api.queriesPerCurrentSecond - 1

    def tryRestoreState(self, api, endpoint):
        commonPrefix = os.path.commonprefix([self.lastEndpoint, endpoint])
        if len(commonPrefix) > len(api.baseUrl):
            api.maxQueriesPerSecond = api.DISCORD_MAX_QUERIES_PER_SECOND

class BasicStringifiers:
    def stringify(self, obj, fmt, stringifyDict):
        return fmt.format(**{field : stringifyDict[field](obj)})
    def message(msg):
        atts = msg['attachments']
        return self.stringify('{timestamp} {author}: {content}{attachments}', {
            'timestamp' : msg['timestamp'][:19],
            'author' : msg['author']['username'],
            'content' : msg['content'],
            'attachements' : atts and (' ' + ' '.join(['[{}]'.format(a["url"]) for a in atts])) or ''
        })

class BasicParsers:
    def parse(self, obj, parserDict):
        return {field : parserDict[field](obj[field]) for field in parserDict if field in obj}
    def message(self, msg):
        return self.parse(msg, {
            'id' : nop, 
            'author' : lambda x: x['username'], 
            'timestamp' : nop, 
            'type' : nop, 
            'content' : nop, 
            'message_reference' : lambda x: x['message_id'], 
            'attachments': lambda x: x and (' ' + ' '.join(['[{}]'.format(a["url"]) for a in x])) or ''
        })
    def guild(self, guild):
        return self.parse(msg, {
            'id' : nop,
            'name' : nop
        })

initializers = {
    "DM" : lambda self, **kwgs: self.get_dms(),
    "DM_TWOSOME" : lambda self, **kwgs: [x for x in self.get("DM") if x["type"] == 1],
    "DM_GROUPS" : lambda self, **kwgs: [x for x in self.get("DM") if x["type"] == 3],
    "GUILDS" : lambda self, **kwgs: self.get_guilds(),
    "GUILD_CHANNELS" : lambda self, **kwgs: self.get_guild_channels(kwgs["id"], supressErrors='supressErrors' in kwgs and kwgs['supressErrors']),
    "CHANNEL_MESSAGES_COUNT_JSON" : lambda self, **kwgs: self.get_message_count_json(kwgs["id"]),
    "GUILD_MESSAGES_COUNT_JSON" : lambda self, **kwgs: self.query(self.baseUrl + self.guildSearchUrl, [kwgs['id']])
}

defaultQueryFn = lambda self, url, cwgs: self.http_get(url)

class DiscordApi:
    def __init__(self, token, log = None, RLRProcessor = None, initializers = initializers):
        self.baseUrl = 'https://discord.com/api/v8/'
        self.dmUrl = 'users/@me/channels'
        self.guildsUrl = 'users/@me/guilds'
        self.guildChannelsUrl = 'guilds/{}/channels'
        self.messagesInChannelFromSnoflakeUrl = 'channels/{}/messages?after={}&limit=100{}' # 100 is discord upper bound
        self.channelSearchUrl = 'channels/{}/messages/search'
        self.guildSearchUrl = "guilds/{}/search"
        self.token = token
        self.headers = {
            'Authorization': token, 
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36', 
            'Content-Type': 'application/json'
        }
        self.log = log
        self.queriesPerCurrentSecond = 0
        self.currentNsStartpoint = 0
        self.maxQueriesPerSecond = 50
        self.RLRProcessor = RLRProcessor 
        self.cache = {}
        self.initializers = initializers
        self.DISCORD_MAX_QUERIES_PER_SECOND = 50

    def get(self, what, **kwgs): # replace with stdlib cache?
        if 'id' not in kwgs:
            if what not in self.cache or ('forced' in kwgs and kwgs['forced']):
                self.cache[what] = self.initializers[what](self, **kwgs)
            result = self.cache[what]
        else:
            if what not in self.cache:
                self.cache[what] = {}
            if kwgs['id'] not in self.cache[what] or ('forced' in kwgs and kwgs['forced']):
                self.cache[what][kwgs['id']] = self.initializers[what](self, **kwgs)
            result = self.cache[what][kwgs['id']]
        return result

    def http_get(self, url): # like requests.get but return content only (as str) (to allow users not to install requests library, however it's just python -m pip install requests in cmd then you are in python folder (cd 'path/to/python'))
        req = urllib.request.Request(url, headers=self.headers)
        try:
            resp = urllib.request.urlopen(req)
        except Exception as ex: # for 400, 403, other HTTP codes that indicate a error
            return ex.fp.fp.read().decode()
        return resp.read().decode()
    
    def send_message(self, channelId, text=None, attachements=[], supressErrors=False):
        try:
            import requests
        except Exception as ex:
            raise Exception("requests is unavaible, send_message won't worc: " + ex)
        payload = {}
        if not (text or attachements):
            raise Exception("Nothing to send?")
        if text:
            payload['content'] = text
        if attachements:
            temp = []
            for i in range(len(attachements)):
                att = attachements[i]
                data = {'id' : i, 'filename' : att['filename']}
                if 'desc' in att:
                    data['description'] = att['desc']
            payload['attachments'] = temp
        files = {}
        if payload:
            files['payload_json'] = (None, json.dumps(payload, ensure_ascii = False), 'application/json')
        if attachements:
            for i in range(len(attachements)):
                att = attachements[i]
                files[f'files[{i}]'] = (att['filename'], open(att['path'], 'rb'))
        return self.query(self.baseUrl + 'channels/{}/messages', [channelId],
            fn = lambda s, u, c: requests.post(u, headers = c['headers'], files = c['files']).content,
            cwgs = {
                'headers' : {'User-Agent': 'Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36', 'Authorization' : self.token},
                'files' : files
            },
            supressErrors=supressErrors
        )
            

    def query(self, endpoint, args=[], projector = nop, filter_ = nop, supressErrors = False, fn = defaultQueryFn, cwgs={}):
        rlrProcEPInfo = ('[GET]' if fn==defaultQueryFn else '[OTHER?]') + endpoint
        self.RLRProcessor and self.RLRProcessor.tryRestoreState(self, rlrProcEPInfo)
        ns = time.time_ns()
        if (ns - self.currentNsStartpoint) / 1_000_000_000 > 1:
            self.currentNsStartpoint = ns
            self.queriesPerCurrentSecond = 0

        if self.queriesPerCurrentSecond > self.maxQueriesPerSecond:
            #await asyncio.sleep((ns - self.currentNsStartpoint) / 1_000_000 + 0.01)
            time.sleep((ns - self.currentNsStartpoint) / 1_000_000 + 0.01)
            self.queriesPerCurrentSecond = 0
            self.currentNsStartpoint = ns

        self.queriesPerCurrentSecond += 1
        data = None

        while True:
            data = json.loads(fn(self, endpoint.format(*args), cwgs))
            self.log and self.log.log(" ".join([endpoint, args]))

            if 'retry_after' in data:
                wait = data['retry_after']
                self.RLRProcessor and self.RLRProcessor.notify(self, rlrProcEPInfo, wait)
                #await asyncio.sleep(wait + 0.01)
                time.sleep(wait + 0.01)
                self.log and self.log.log(wait)
                continue
            if not supressErrors:
                self.throwIfError(data)
            break

        return type(data) == type([]) and [projector(x) for x in data if filter_(x)] or data
    
    def throwIfError(self, json_):
        if 'message' in json_:
            raise OurException(json_)
    
    def get_dms(self, projector = nop, filter_ = nop):
        return self.query(self.baseUrl + self.dmUrl, [], projector=projector, filter_=filter_)
    
    def get_guilds(self, projector = nop, filter_ = nop):
        return self.query(self.baseUrl + self.guildsUrl, [], projector=projector, filter_=filter_)
    
    def get_guild_channels(self, guildId, projector = nop, filter_ = nop, supressErrors=False):
        return self.query(self.baseUrl + self.guildChannelsUrl, [guildId], projector=projector, filter_=filter_, supressErrors=supressErrors)
    
    def get_messages_by_chunks(self, 
        channelId, 
        lastSnowflake = 0,
        firstSnowflake = -1,
        size = 1000, # may return a bit more if is not divible by 100
        projector = nop, 
        filter_ = nop,
        progressFn = None
    ):
        result = []
        while True:
            for i in range(math.ceil(size / 100)):
                d = self.query(
                    self.baseUrl + self.messagesInChannelFromSnoflakeUrl,
                    [channelId, lastSnowflake, firstSnowflake != -1 and f'&before{firstSnowflake}' or ''], 
                    projector,
                     filter_
                )[::-1] # newer messages will appear first, so inverse the order according to one in discord
                result.extend(d)
                progressFn and progressFn(i, result, lastSnowflake)
                if len(d) < 100:
                    yield result
                    return
                lastSnowflake = d[-1]['id']

            yield result
            result = []
            
    def get_channel_message_count_json(self, channelId, supressErrors = False):
        return self.query(self.baseUrl + self.channelSearchUrl, [channelId], projector =None,supressErrors=supressErrors)