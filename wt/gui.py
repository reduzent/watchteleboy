import urwid

class WatchTeleboyGUI:

    palette = [
        ('outer', '', '', '', '#408', '#fff'),
        ('border', '', '', '', '#80f', '#fdf'),
        ('inner', '', '', '', '#006', '#fdf'),
        ('title', '', '', '', '#006,bold', '#fdf'),
        ('reversed', '', '', '', '#fdf', '#006')
    ]

    line_box_chars = {
        'tlcorner': '\N{Full block}',
        'trcorner': '\N{Full block}',
        'brcorner': '\N{Full block}',
        'blcorner': '\N{Full block}',
        'lline': '\N{Full block}',
        'rline': '\N{Full block}',
        'tline': '\N{Upper half block}',
        'bline': '\N{Lower half block}'
    }

    def __init__(self, channels):
        # channel selection
        body = [urwid.Text(('title', 'Select a channel:')), urwid.Divider()]
        for channel in channels:
            button = urwid.Button(channel)
            urwid.connect_signal(button, 'click', self.now_playing, channel)
            body.append(urwid.AttrMap(button, None, focus_map='reversed'))
        self.channel_selection_w = urwid.ListBox(urwid.SimpleListWalker(body))

        # embed main widget (initially channel_selection_w)
        self.container = urwid.Padding(self.channel_selection_w, left=1, right=1)
        guts = urwid.AttrMap(self.container, 'inner')
        linebox = urwid.LineBox(guts, title='WatchTeleboy', **self.line_box_chars)
        frame = urwid.AttrMap(linebox, 'border')
        main = urwid.Overlay(frame, urwid.AttrMap(urwid.SolidFill(u'\N{FULL BLOCK}'), 'outer'),
                align=('relative', 50), width=('relative', 50),
                valign='middle', height=('relative', 80),
                min_width=20, min_height=9)
        self.loop = urwid.MainLoop(main,self.palette)
        self.loop.screen.set_terminal_properties(colors=256)

    def run(self):
        self.loop.run()

    def switch_widget(self, button, widget):
        self.container.original_widget = widget

    def now_playing(self, button, channel):
        response = urwid.Text(('title', ['Now playing ', channel, '\n']))
        stop = urwid.Button(u'Stop')
        urwid.connect_signal(stop, 'click', self.switch_widget, self.channel_selection_w)
        pile = urwid.Pile([response,
            urwid.AttrMap(stop, None, focus_map='reversed')])
        now_playing_w = urwid.Filler(pile, valign='top')
        self.switch_widget(button, now_playing_w)
