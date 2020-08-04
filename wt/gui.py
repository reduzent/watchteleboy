"""
extension for watchteleboy to provide an urwid based frontend
"""

import datetime
import threading
import urwid

from wt.helpers import convert_mpv_timestring, parse_time_string

class WatchTeleboyGUI:
    """
    urwid based class that provides a frontend for watchteleboy.
    It needs an instance of WatchTeleboySession and WatchTeleboyPlayer
    at creation time and will handle the rest when executed with its
    run() method.
    """

    autoplay = True

    palette = [
        ('title', '', '', '', '#008,bold', '#fdf'),
        ('body', '', '', '', 'default', 'default'),
        ('focus', '', '', '', 'default', '#ddd'),
        ('focus_greyed', '', '', '', '#888', '#ddd'),
        ('greyed', '', '', '', '#888', 'default'),
        ('underline', '', '', '', 'default,underline', 'default'),
        ('button', '', '', '', 'default,bold', '#dff'),
        ('border', '', '', '', '#a4f', 'default')
    ]

    line_box_chars = {
        'tlcorner': '\N{Lower half block}',
        'trcorner': '\N{Lower half block}',
        'brcorner': '\N{Upper half block}',
        'blcorner': '\N{Upper half block}',
        'lline': '\N{Full block}',
        'rline': '\N{Full block}',
        'tline': '\N{Lower half block}',
        'bline': '\N{Upper half block}'
    }

    def __init__(self, wt_session, wt_player):
        # wt_session is expected to be an instance of WatchTeleboySession
        # wt_player is expected to be an instance of WatchTeleboyPlayer
        self.wt_session = wt_session
        self.wt_player = wt_player
        self.channels = self.wt_session.get_channels()
        self.channel = ''
        self.video_representation = None
        self.audio_language = None
        self.time_live = True
        self.start_time = None

        # init some widgets
        self.div = urwid.Divider()
        self.pp_placeholder = urwid.WidgetPlaceholder(urwid.Text('----'))
        self.mpv_output_w = urwid.Text('')

        # main title
        title_bt = urwid.BigText(('title', "watchteleboy"), urwid.HalfBlock5x4Font())
        title_am = urwid.AttrMap(urwid.Padding(title_bt, width='clip', align='center'), 'title')
        title = urwid.Pile([self.div, title_am, self.div])

        # Box "Channel:" (left part)
        ch_sel_header = urwid.AttrMap(urwid.Padding(urwid.Text('Channel:'),
                                                    width=('relative', 100)), 'title')
        ch_sel_group = []
        ch_sel_radios = [
            urwid.AttrMap(
                urwid.RadioButton(ch_sel_group, channel, state=False,
                                  on_state_change=self.switch_channel,
                                  user_data=channel),
                None, focus_map='focus')
            for channel in self.channels]
        self.channel_radio = urwid.ListBox(urwid.SimpleListWalker(ch_sel_radios))
        self.channel_widget = urwid.WidgetPlaceholder(self.channel_radio)
        left_content = urwid.Pile([
            ('pack', ch_sel_header),
            ('pack', self.div),
            self.channel_widget,
            ('pack', self.div)
        ])
        left = urwid.LineBox(left_content)

        # Settings and stuff (right part)
        # Box "Control:"
        ctrl_header = urwid.AttrMap(urwid.Padding(urwid.Text('Control:'),
                                                  width=('relative', 100)), 'title')
        autoplay = urwid.AttrMap(urwid.CheckBox('Autoplay', state=self.autoplay,
                                                on_state_change=self.set_autoplay),
                                 '', focus_map='focus')
        self.play = urwid.Button('Play', on_press=self.start_playback)
        self.stop = urwid.Button('Stop', on_press=self.stop_playback)
        self.pp_placeholder.original_widget = self.play
        left_button = urwid.Padding(urwid.AttrMap(urwid.LineBox(self.pp_placeholder),
                                                  'button', focus_map='focus'),
                                    width=10)
        quit_w = urwid.Padding(
            urwid.AttrMap(
                urwid.LineBox(
                    urwid.Button('Quit', on_press=self.quit_program)),
                'button', focus_map='focus'),
            width=10, align='right')
        playstop_quit = urwid.Columns([left_button, quit_w])
        right1_pile = urwid.Pile([
            ('pack', ctrl_header),
            ('pack', self.div),
            ('pack', autoplay),
            ('pack', self.div),
            ('pack', playstop_quit),
            urwid.SolidFill(' ')
        ])
        right1_content = urwid.BoxAdapter(right1_pile, height=7)
        right1_box = urwid.LineBox(right1_content)

        # Box "Quality:"
        repr_header = urwid.AttrMap(urwid.Padding(urwid.Text('Quality:'),
                                                  width=('relative', 100)),
                                    'title')
        self.repr_radios = urwid.WidgetPlaceholder(urwid.ListBox(urwid.SimpleListWalker([])))
        right2_pile = urwid.Pile([
            ('pack', repr_header),
            ('pack', self.div),
            self.repr_radios
        ])
        right2_content = urwid.BoxAdapter(right2_pile, height=8)
        right2_box = urwid.LineBox(right2_content)

        # Box "Audio:"
        lang_header = urwid.AttrMap(urwid.Padding(urwid.Text('Audio:'),
                                                  width=('relative', 100)),
                                    'title')
        self.lang_radios = urwid.WidgetPlaceholder(urwid.ListBox(urwid.SimpleListWalker([])))
        right3_pile = urwid.Pile([
            ('pack', lang_header),
            ('pack', self.div),
            self.lang_radios
        ])
        right3_content = urwid.BoxAdapter(right3_pile, height=5)
        right3_box = urwid.LineBox(right3_content)

        # Box "Time:"
        self.time_title = urwid.Text('Time:')
        time_header = urwid.AttrMap(urwid.Padding(self.time_title,
                                                  width=('relative', 100)),
                                    'title')
        self.time_edit = urwid.Edit(edit_text='')
        urwid.connect_signal(self.time_edit, 'postchange', self.set_starttime)
        self.time_live_cb = urwid.CheckBox('live', state=self.time_live, on_state_change=self.set_time_live)
        self.time_w = urwid.AttrMap(self.time_edit, 'greyed', focus_map='focus_greyed')
        time_live_w = urwid.AttrMap(self.time_live_cb, '', focus_map='focus')
        time_grid = urwid.GridFlow([time_live_w, self.time_w], 8, 2, 0, 'left')
        right4_pile = urwid.Pile([
            ('pack', time_header),
            ('pack', self.div),
            ('pack', time_grid),
            urwid.SolidFill(' ')
        ])
        right4_content = urwid.BoxAdapter(right4_pile, height=3)
        right4_box = urwid.LineBox(right4_content)

        # Stitching boxes together
        right = urwid.Pile([
            ('pack', right1_box),
            ('pack', right4_box),
            ('pack', right2_box),
            ('pack', right3_box),
            urwid.LineBox(urwid.SolidFill(' '))
        ])

        # footer
        mpv_status = urwid.AttrMap(urwid.Padding(self.mpv_output_w, align='center', width=52),
                                   'title')
        footer = urwid.Pile([self.div, mpv_status, self.div])

        # Overall Layout
        self.columns = urwid.Columns([left, right], dividechars=2)
        columns_padded = urwid.Padding(self.columns, left=2, right=2)
        content = urwid.AttrMap(urwid.Frame(columns_padded, header=title, footer=footer), 'body')
        lbc = urwid.LineBox(content, **self.line_box_chars)
        hlbc = urwid.AttrMap(urwid.Padding(lbc, left=1, right=1), 'border')
        self.loop = urwid.MainLoop(hlbc, palette=self.palette)
        self.loop.screen.set_terminal_properties(colors=256)

        # mpv output
        self.mpv_stdout = self.loop.watch_pipe(self._player_receive_output)

    def run(self):
        """
        run urwid main loop
        """
        self.loop.run()

    def _player_wait(self, player):
        player.wait()
        self._switch_widgets('stop')
        try:
            self.loop.draw_screen()
        except AssertionError:
            pass

    def _player_receive_output(self, mpv_out):
        output = mpv_out[4:-1].decode('utf8')
        output_list = output.split(' ')
        if output_list[0] == '(Paused)':
            output_list = output_list[1:]
        try:
            output_list[1] = convert_mpv_timestring(output_list[1])
            output_list[3] = convert_mpv_timestring(output_list[3]).split(' ')[1]
            self.start_time = output_list[1].split(' ')[1]
            self.time_edit.set_edit_text(self.start_time)
        except (IndexError, ValueError):
            pass
        self.mpv_output_w.set_text(' '.join(output_list))

    def refresh_languages(self):
        """
        refresh widget that displays available audio streams
        """
        langs = self.wt_player.get_audio_languages()
        if not self.audio_language:
            self.audio_language = langs[0]
        lang_group = []
        lang_radios = [urwid.AttrMap(
            urwid.RadioButton(lang_group, lang,
                              state=(True if lang == self.audio_language else False),
                              on_state_change=self.switch_language, user_data=lang),
            None, focus_map='focus')
                       for lang in langs]
        self.lang_radios.original_widget = urwid.ListBox(urwid.SimpleListWalker(lang_radios))

    def refresh_representations(self):
        """
        refresh widget that displays available video representations
        """
        reprs = self.wt_player.get_video_representations()
        if not self.video_representation:
            self.video_representation = min(reprs.keys())
        repr_group = []
        repr_radios = [urwid.AttrMap(
            urwid.RadioButton(repr_group, f"{dict(reprs[rid])['width']}x"\
                                          f"{dict(reprs[rid])['height']}"\
                                          f"@{dict(reprs[rid])['frameRate']}Hz",
                              state=(True if rid == self.video_representation else False),
                              on_state_change=self.switch_representation, user_data=rid),
            None, focus_map='focus')
                       for rid in reprs.keys()]
        self.repr_radios.original_widget = urwid.ListBox(urwid.SimpleListWalker(repr_radios))

    def switch_channel(self, button, state, channel):
        """
        switch channel (handler for channel radio)"
        """
        if state:
            self.time_live_cb.set_state(True)
            self.channel, mpd_url = self.wt_session.get_stream_url(channel)
            self.wt_player.set_mpd_url(mpd_url, self.channel)
            self.refresh_representations()
            self.refresh_languages()
            if self.autoplay:
                self.start_playback(None)

    def switch_representation(self, button, state, r_id):
        """
        switch representation (handler for representation radio)
        """
        if state:
            self.wt_player.set_video_representation(representation_id=r_id)
            self.video_representation = r_id

    def switch_language(self, button, state, lang):
        """
        switch audio stream (handler for audio radio)
        """
        if state:
            self.wt_player.set_audio_language(lang=lang)
            self.audio_language = lang

    def set_autoplay(self, button, state):
        """
        toggle on and off automatic playback on channel selection
        (handler for autoplay checkbox)
        """
        self.autoplay = state

    def set_time_live(self, button, state):
        """
        set start time (handler for time_live checkbox)
        """
        self.time_live = state
        if state:
            self.time_edit.set_edit_text('')
            self.time_w.set_attr_map({None: 'greyed'})
            self.time_w.set_focus_map({None: 'focus_greyed'})
        else:
            almost_now = datetime.datetime.now() - datetime.timedelta(seconds=10)
            self.time_edit.set_edit_text(almost_now.strftime('%H:%M:%S'))
            self.time_w.set_attr_map({None: 'default'})
            self.time_w.set_focus_map({None: 'focus'})

    def set_starttime(self, widget, arg):
        """
        handler for time edit widget
        """
        time_raw = self.time_edit.get_edit_text()
        try:
            starttime = datetime.time(*list(map(int, time_raw.split(':'))))
        except ValueError:
            self.start_time = None
            if self.time_live:
                self.time_title.set_text('Time: (live)')
            else:
                self.time_title.set_text('Time: (unparsable)')
        else:
            self.time_title.set_text('Time:')
            self.start_time = time_raw

    def start_playback(self, button):
        """
        start playback (handler for play button)
        """
        self._switch_widgets('play')
        if self.start_time:
            self.wt_player.set_starttime(self.start_time)
        self.wt_player.play(output_fd=self.mpv_stdout)
        # thread that waits for wt_player to stop
        waiter = threading.Thread(target=self._player_wait, args=(self.wt_player,))
        waiter.start()

    def stop_playback(self, button):
        """
        stop playback (handler for stop button)
        """
        self._switch_widgets('stop')
        self.wt_player.stop()

    def _switch_widgets(self, action):
        if action == 'play':
            self.pp_placeholder.original_widget = self.stop
            channel_playing = urwid.Pile([
                ('pack', urwid.Text(f'Now playing: {self.channel}')),
                urwid.SolidFill(' ')
            ])

            self.channel_widget.original_widget = channel_playing
            self.columns.set_focus_path([1, 0, 4, 0])
        elif action == 'stop':
            self.pp_placeholder.original_widget = self.play
            self.channel_widget.original_widget = self.channel_radio
            self.columns.set_focus_path([0])

    def quit_program(self, button):
        """
        terminate watchteleboy (handler for quit button)
        """
        self.wt_player.stop()
        raise urwid.ExitMainLoop()
