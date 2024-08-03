import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext
from discord_api.discord_api import *
from tkinter import filedialog as fd
import threading
import sys
import re
import time
import json
import webbrowser

class DASTask:
    def __init__(self):
        pass

class OneirosAutoSender(tk.Tk):
    def __init__(self, token='', dataPath=''):
        super().__init__()
        self.title("0xOneiros")

        # Set window icon
        self.iconphoto(False, tk.PhotoImage(file='logo.png'))  # Update this with the path to your icon file
        self.geometry(f'1600x368') 

        # Add canvas for background text
        self.canvas = tk.Canvas(self, width=800, height=600)
        self.canvas.create_text(400, 300, text="0xOneiros", font=("Helvetica", 50), fill="lightgrey")
        self.canvas.grid(row=0, column=0, rowspan=2, columnspan=2, sticky='nsew')

        self.underlying = []
        self.columns = ('taskId', 'name', 'running', 'targets', 'timings', 'message', 'files', 'sent', 'errors')
        self.columnsWrappers = (tk.IntVar, tk.StringVar, tk.IntVar, tk.StringVar, tk.StringVar, tk.StringVar, tk.StringVar, tk.IntVar, tk.IntVar)
        self.tree = ttk.Treeview(self.canvas, show="headings", columns=self.columns)
        for i in range(len(self.columns)):
            self.tree.heading("#" + str(i + 1), text=self.columns[i])
        ysb = ttk.Scrollbar(self.canvas, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=ysb.set)
        self.tree.bind("<Double-Button-1>", self.on_dbl_click)
        self.tree.grid(row=0, column=0)
        ysb.grid(row=0, column=1, sticky=tk.N + tk.S)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        p1 = tk.PanedWindow(self.canvas)
        p1.grid(row=1, column=0, sticky=tk.N + tk.S)
        p1.add(tk.Label(self.canvas, text='توکن'))
        self.tokenVar = tk.StringVar(self.canvas, token)
        p1.add(tk.Entry(self.canvas, textvariable=self.tokenVar, show='*'))
        p1.add(tk.Button(self.canvas, text='وظیفه جدید', command=self.createExampleRow))
        p1.add(tk.Button(self.canvas, text='حذف وظیفه', state='disabled', command=self.deleteSelected))
        p1.add(tk.Button(self.canvas, text='بارگیری وظایف', command=self.loadTasks))
        p1.add(tk.Button(self.canvas, text='ذخیره وظایف', command=self.saveTasks))
        p1.add(tk.Button(self.canvas, text='تلگرام اونیروس', command=self.openTelegram))
        p1.add(tk.Button(self.canvas, text='تویتر اونیروس', command=self.openSocialPage))
        self.lastTokenUsed = ''
        self.RESOLUTION_S = 1
        self.api = None
        self.running = True
        self.lastRuns = {}
        self.channelsGroupsLines = None
        if dataPath:
            self.loadTasksInner(dataPath)
        self.heartbeat()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.editing = False

    def on_closing(self):
        self.running = False
        self.destroy()

    def deleteSelected(self):
        indexes = [self.tvIndexToInt(x) for x in self.tree.selection()]
        indexes = sorted(indexes, reverse=True)
        for i in indexes:
            del self.underlying[i]
            self.tree.delete(self.intToTvIndex(i))

    def loadTasks(self):
        filename = fd.askopenfilename(
            title='باز کردن فایل json',
            filetypes=(('JSON files', '*.json'),)
        )
        self.loadTasksInner(filename)

    def loadTasksInner(self, filename):
        j = json.load(open(filename, encoding='utf-8'))
        self.tree.delete(*self.tree.get_children())
        for e in j:
            self.newRow([(str if n != 'files' else json.dumps)(e[n]) for n in self.columns])

    def saveTasks(self):
        filename = fd.asksaveasfilename(
            title='انتخاب مقصد فایل json',
            filetypes=(('JSON files', '*.json'),)
        )
        self.saveTasksInner(filename)

    def getTreeValues(self, tree):
        return [list(tree.item(self.intToTvIndex(index)).values())[2] for index in range(len(tree.get_children()))]

    def saveTasksInner(self, filename):
        col = self.getTreeValues(self.tree)
        res = [{self.columns[i]: json.loads(item[i]) if i in [3, 6] else item[i] for i in range(len(self.columns))} for item in col]
        json.dump(res, open(filename, mode='w', encoding='utf-8'), ensure_ascii=False)

    def createExampleRow(self):
        self.newRow([len(self.underlying) + 1, 'مثال وظیفه', 0, '[]', '10s', 'سلام، دنیا!', "[]", 0, 0])

    def selectTargetChannels(self):
        top = tk.Toplevel()
        self.sTTop = top
        self.targetsUnderlying = []
        channelsVar = tk.StringVar()
        groupsVar = tk.StringVar()
        j = json.loads(self.underlying[self.tvIndexToInt(self.lastS)][3].get())
        resultVar = tk.StringVar()
        resultVar.set(j)
        self.stChannelsVar = channelsVar
        self.stResultVar = resultVar

        p = tk.PanedWindow(top)
        p.pack(fill=tk.BOTH, expand=1)
        lb = tk.Listbox(p, listvariable=channelsVar, selectmode='extended')
        lb2 = tk.Listbox(p, listvariable=groupsVar, selectmode='single')
        lb3 = tk.Listbox(p, listvariable=resultVar, selectmode='extended')
        lb2.bind("<Double-Button-1>", self.newChannelsGroupSelected)
        self.stGroupsListBox = lb2
        self.stChannelsListBox = lb
        self.stResultListBox = lb3
        self.initChannelsGroupsLines()
        groupsVar.set(self.channelsGroupsLines)
        p.add(lb2)
        p.add(lb)
        p1 = tk.PanedWindow(p, orient=tk.VERTICAL)
        p.add(p1)
        p.add(lb3)
        for i in [tk.Button(top, text='>', command=self.addOne),
                  tk.Button(top, text='>>', command=self.addAll),
                  tk.Button(top, text='<', command=self.removeOne),
                  tk.Button(top, text='<<', command=self.removeAll),
                  tk.Button(top, text='تایید', command=self.stSaveNExit)]:
            p1.add(i)
        top.mainloop()

    def stSaveNExit(self):
        self.targetsVar.set(json.dumps(self.targetsUnderlying))
        self.targetsInfo = [self.stResultListBox.get(i) for i in range(self.stResultListBox.size())]
        self.sTTop.destroy()

    def user_readable(self, u):
        return u["username"] + "#" + u["discriminator"]

    def channel_readable(self, c, channels, guild):
        prefix = c["parent_id"] and next((x["name"] + "/" for x in channels if x["id"] == c["parent_id"]), '') or ''
        suffix = guild and " (" + guild['name'] + ")" or ''
        return (prefix + c["name"] + suffix)

    def initChannelsGroupsLines(self):
        if not self.channelsGroupsLines:
            self.initApi()
            self.channelsGroupsLines = ["DM", "DM (people)", "DM (groups)", *[g['name'] for g in self.api.get("GUILDS")]]

    def newChannelsGroupSelected(self, *a):
        self.targetsUnderlying = []
        indx = self.stGroupsListBox.curselection()[0]
        if indx == 0:
            lines = [*self.getPeopleDMsLines(), *self.getGroupsDMsLines()]
        elif indx == 1:
            lines = self.getPeopleDMsLines()
        elif indx == 2:
            lines = self.getGroupsDMsLines()
        else:
            lines = self.getGuildChannelsLines(indx - 3)
        self.stChannelsVar.set(lines)

    def getPeopleDMsLines(self):
        t = self.api.get("DM_TWOSOME")
        self.stLastUnderlying = t
        return [self.user_readable(d["recipients"][0]) for d in t]

    def getGroupsDMsLines(self):
        t = self.api.get("DM_GROUPS")
        self.stLastUnderlying = t
        return [(g["name"] or "") + " " + ";".join([self.user_readable(x) for x in g["recipients"]]) for g in t]

    def getGuildChannelsLines(self, guildIndex):
        guilds = self.api.get("GUILDS")
        g = guilds[guildIndex]
        channels = self.api.get("GUILD_CHANNELS", id=g['id'])
        textChannels = [x for x in channels if x['type'] in [0, 2]]
        self.stLastUnderlying = textChannels
        return [self.channel_readable(c, channels, g) for c in textChannels]

    def updateUnderlying(self, i, delete=False):
        if delete:
            del self.targetsUnderlying[i]
        else:
            self.targetsUnderlying.append(int(self.stLastUnderlying[i]['id']))

    def addOne(self):
        for i in self.stChannelsListBox.curselection():
            self.stResultListBox.insert('end', self.stChannelsListBox.get(i))
            self.updateUnderlying(i)

    def addAll(self):
        for i in range(self.stChannelsListBox.size()):
            self.stResultListBox.insert('end', self.stChannelsListBox.get(i))
            self.updateUnderlying(i)

    def removeOne(self):
        for i in self.stResultListBox.curselection()[::-1]:
            self.stResultListBox.delete(i, i)
            self.updateUnderlying(i, True)

    def removeAll(self):
        self.stResultListBox.delete(0, "end")
        self.targetsUnderlying = []

    def createPW(self, master, items, **cwgs):
        p = tk.PanedWindow(master, **cwgs)
        for i in items:
            if type(i) == type(lambda: 0):
                i = i(master)
            p.add(i)
        return p

    def createFrame(self, master, side, panes):
        f = tk.Frame(master)
        for p in panes:
            p.pack(side=side)
        return f

    def selectFiles(self):
        top = tk.Toplevel()
        self.sfTop = top
        pathVar = tk.StringVar(top)
        filenameVar = tk.StringVar(top)
        descVar = tk.StringVar(top)

        self.sfVars = [pathVar, filenameVar, descVar]

        self.createFrame(top, 'top', [
            self.createPW(top, [lambda m: tk.Label(m, text='مسیر'), lambda m: tk.Entry(m, textvariable=pathVar), lambda m: tk.Button(m, text='جستجو', command=self.browseFile)]),
            self.createPW(top, [lambda m: tk.Label(m, text='نام فایل'), lambda m: tk.Entry(m, textvariable=filenameVar)]),
            self.createPW(top, [lambda m: tk.Label(m, text='توضیحات'), lambda m: tk.Entry(m, textvariable=descVar)]),
            self.createPW(top, [lambda m: tk.Button(m, text='اضافه کردن', command=self.addFile), lambda m: tk.Button(m, text='حذف', command=self.delFile)])
        ]).pack(side='top')

        self.sfColumns = ('مسیر', 'نام فایل', 'توضیحات')
        tree = ttk.Treeview(top, show="headings", columns=self.sfColumns)
        self.sfTree = tree
        j = json.loads(self.underlying[self.tvIndexToInt(self.lastS)][-3].get())
        for d in j:
            self.sfTree.insert("", tk.END, values=[d[p] for p in self.sfColumns])
        tree.pack(side='top')
        for i in range(len(self.sfColumns)):
            tree.heading("#" + str(i + 1), text=self.sfColumns[i])
        tk.Button(top, text='ذخیره', command=self.sfSaveNExit).pack(side='top')

    def sfSaveNExit(self):
        self.filesVar.set(json.dumps([{self.sfColumns[i]: e[i] for i in range(len(self.sfColumns))} for e in self.getTreeValues(self.sfTree)], ensure_ascii=False))
        self.sfTop.destroy()

    def normalizeFilename(self, v):
        return re.sub('[^A-Za-z_\.\-]', '_', v)

    def browseFile(self):
        v = fd.askopenfilename(
            title='باز کردن فایل',
        )
        self.sfVars[0].set(v)
        if self.sfVars[1].get() == '':
            self.sfVars[1].set(self.normalizeFilename(v[v.rfind('/') + 1:]))

    def addFile(self):
        self.sfTree.insert("", tk.END, values=[x.get() for x in self.sfVars])
        for x in self.sfVars:
            x.set("")

    def delFile(self):
        self.sfTree.delete(self.sfTree.selection()[0])

    def tvIndexToInt(self, v):
        return int(v[1:]) - 1

    def intToTvIndex(self, i):
        return 'I' + str(i + 1).zfill(3)

    def on_dbl_click(self, event):
        self.editing = True
        s = self.tree.selection()[0]
        self.lastS = s
        item = self.tree.item(s)
        values = item["values"]

        top = tk.Toplevel()
        self.top = top
        top.title("ویرایش وظیفه")
        text = None
        for i in range(len(self.columns)):
            tk.Label(top, text=self.columns[i]).grid(row=i, column=0)
            columnName = self.columns[i]
            var = self.underlying[self.tvIndexToInt(s)][i]
            if columnName in ['name', 'timings', 'taskId']:
                tk.Entry(top, textvariable=var).grid(row=i, column=1)
            elif columnName == 'running':
                ttk.Checkbutton(top, variable=var).grid(row=i, column=1)
            elif columnName == 'targets':
                tk.Entry(top, textvariable=var).grid(row=i, column=1)
                self.targetsVar = var
                tk.Button(top, text='جستجو', command=self.selectTargetChannels).grid(row=i, column=2)
            elif columnName == 'message':
                text = scrolledtext.ScrolledText(top, height=5, width=60, background='black', foreground="white")
                self.text = text
                text.insert(tk.INSERT, var.get())
                text.grid(row=i, column=1)
            elif columnName == 'files':
                tk.Entry(top, textvariable=var).grid(row=i, column=1)
                self.filesVar = var
                tk.Button(top, text='جستجو', command=self.selectFiles).grid(row=i, column=2)
            elif columnName in ['sent', 'errors']:
                tk.Entry(top, textvariable=var, state='readonly').grid(row=i, column=1)
        tk.Button(top, text='ذخیره', command=self.saveChangesNExit).grid(row=len(self.columns), column=1)
        top.mainloop()

    def saveChangesNExit(self):
        self.underlying[self.tvIndexToInt(self.lastS)][5] = tk.StringVar(self, self.text.get("1.0", tk.END))
        self.updateRow(self.tvIndexToInt(self.lastS))
        self.top.destroy()
        self.editing = False

    def updateRow(self, i):
        self.tree.item(self.intToTvIndex(i), values=[x.get() if type(x) != type('') else x for x in self.underlying[i]])

    def initApi(self):
        if not self.api or self.lastTokenUsed != self.tokenVar.get():
            self.api = DiscordApi(self.tokenVar.get(), RLRProcessor=BasicRLRProcessor())
            self.lastTokenUsed = self.tokenVar.get()

    def log(self, json, index):
        print(f"ERROR IN {self.tree.item(self.intToTvIndex(index))['values']}: {json}")

    def timeStrToNs(self, v):
        v = [x for x in re.split('([a-z]+)', v) if x]
        resultNs = 0
        nsToS = 1_000_000_000
        multipliers = {
            "s": nsToS,
            "m": nsToS * 60,
            "h": nsToS * 60 * 60,
            "d": nsToS * 60 * 60 * 24
        }
        for i in range(0, len(v), 2):
            resultNs += int(v[i]) * multipliers[v[i + 1]]
        return resultNs

    def heartbeat(self):
        index = -1
        for i in self.underlying:
            index += 1
            now = time.time_ns()
            if i[2].get() == 0 or self.editing:
                if i[0].get() in self.lastRuns:
                    del self.lastRuns[i[0].get()]
                continue
            if i[0].get() in self.lastRuns:
                dt = (now - self.lastRuns[i[0].get()])
                if dt < self.timeStrToNs(i[4].get()): continue

            self.lastRuns[i[0].get()] = now
            self.initApi()
            for channelId in json.loads(i[3].get()):
                res = self.api.send_message(channelId, i[5].get(), json.loads(i[6].get()), supressErrors=True)
                if 'message' in res:
                    i[-1].set(i[-1].get() + 1)
                    self.log(res, index)
                else:
                    i[-2].set(i[-2].get() + 1)
                self.updateRow(index)
        self.workerThread = threading.Timer(self.RESOLUTION_S, self.heartbeat, [])
        self.workerThread.start()

    def newRow(self, values):
        self.underlying.append([wr(self, v) for wr, v in zip(self.columnsWrappers, values)])
        self.tree.insert("", tk.END, values=values)

    def openTelegram(self):
        webbrowser.open('https://t.me/0xOneiros')

    def openSocialPage(self):
        webbrowser.open('https://x.com/0xoneiros')


app = OneirosAutoSender(sys.argv[1] if len(sys.argv) >= 2 else '', sys.argv[2] if len(sys.argv) >= 3 else '')
app.mainloop()
