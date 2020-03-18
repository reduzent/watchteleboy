"""Collection of some classes used by watchteleboy"""

import datetime
import json
import os
import pickle
import re
import subprocess
import sys
import threading
from time import sleep
from xml.dom import minidom
from xml.parsers.expat import ExpatError

import requests           # DEB: python3-request

from wt.helpers import (parse_time_string, parse_duration_string)

##################################################################################
# SOME CLASSES
##################################################################################

class WatchTeleboyError(BaseException):
    "Error class for wt"
    pass

class WatchTeleboySession:
    """
    Emulates a web session and deals with authentication and
    interfaces with the Teleboy API
    """

    user_agent = 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:71.0) Gecko/20100101 Firefox/71.0'
    login_url = 'https://www.teleboy.ch/login_check'
    userenv_url = 'https://www.teleboy.ch/live'
    headers = {
        'User-Agent': user_agent
    }
    api_key = '6ca99ddb3e659e57bbb9b1874055a711b254425815905abaacf262b64f02eb3d'

    def __init__(self, cachefile=None):
        self.cache_file = cachefile
        try:
            assert self.cache_file is not None
            self.__restore_session()
        except (AssertionError, FileNotFoundError):
            # create new session
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        self.channel_selection = 'all'
        self.api = None
        self.channel_ids = None
        self.user_id = None
        self.session_id = None

    def get_stream_url(self, channel=None, station_id=None):
        """
        get MPEG-DASH manifest URL for given channel or station id
        """
        if not self.channel_ids:
            self.__retrieve_channel_ids()
        if station_id is None:
            for chan_name in self.channel_ids.keys():
                if chan_name.lower() == channel.lower():
                    channel = chan_name
                    break
            else:
                print(f'No such channel: {channel}')
                return None
            station_id = self.channel_ids[channel]
        api_url = f'https://tv.api.teleboy.ch/users/{self.user_id}/stream/live/{station_id}'
        r_api = self.api.get(api_url)
        try:
            assert r_api.status_code == 200
        except AssertionError:
            print('failed to retrieve channel data')
            raise WatchTeleboyError
        channel_data = json.loads(r_api.content.decode())
        return (channel, channel_data['data']['stream']['url'])

    def get_channels(self):
        """
        return a list of available channels
        """
        try:
            assert self.channel_ids is not None
        except AssertionError:
            self.__retrieve_channel_ids()
        chanlist = list(self.channel_ids.keys())
        chanlist.remove('__selection__')
        return chanlist

    def list_channels(self):
        """
        print available channels
        """
        try:
            assert self.channel_ids is not None
        except AssertionError:
            self.__retrieve_channel_ids()
        for channel in self.channel_ids:
            if channel[0:2] != '__':
                print(channel)

    def login(self, user=None, password=None):
        """
        log in to www.teleboy.ch
        """
        try:
            assert user is not None and password is not None
        except AssertionError:
            print("Please provide both user and password")
            return False
        data = {
            'login': user,
            'password': password,
            'keep_login': '1'
            }
        r_login = self.session.post(self.login_url, data=data)
        try:
            assert r_login.status_code != 429
        except AssertionError:
            print("Your login is blocked. Please login via browser and answer captcha.")
            print("Visit https://www.teleboy.ch/ and try again.")
            return False
        try:
            self.session.cookies['cinergy_auth']
        except KeyError:
            print('Login failed')
            return False
        else:
            if self.cache_file:
                self.__dump_session()
            return True

    def logged_in(self):
        """
        return True when session is authenticated, False if not
        """
        try:
            self.session.cookies.clear_expired_cookies()
            _s = self.session.cookies['cinergy_auth']
            return True
        except KeyError:
            return False

    def set_channel_selection(self, channel_selection):
        """
        define whether all or only user-defined channels are listed
        Allowed values: 'all', 'custom'
        """
        try:
            assert channel_selection in ['all', 'custom']
        except AssertionError:
            print(f'Invalid channel_selection: {channel_selection}')
            print('Falling back to default')
        else:
            self.channel_selection = channel_selection

    def __retrieve_channel_ids(self):
        """
        retrieve list of all channel names with their station ids
        """
        try:
            assert self.__set_api_env()
        except AssertionError:
            print('Setting environment failed...')
            raise
        if self.channel_selection == 'custom':
            api_channellist_url = f'https://tv.api.teleboy.ch/users/'\
                                  f'{self.user_id}/broadcasts/now?expand=station&stream=true'
        else:
            api_channellist_url = 'https://tv.api.teleboy.ch/epg/broadcasts/now?'\
                                  'expand=station&stream=true'
        self.api = requests.Session()
        headers = {
            'x-teleboy-apikey': self.api_key,
            'x-teleboy-session': self.session_id
        }
        self.api.headers.update(headers)
        self.api.headers.update(self.headers)
        r_api = self.api.get(api_channellist_url)
        try:
            assert r_api.status_code == 200
        except AssertionError:
            print('failed to retrieve channel ids')
            return False
        channels = json.loads(r_api.content.decode())
        self.channel_ids = {channel['station_label']: channel['station_id']
                            for channel in channels['data']['items']}
        self.channel_ids['__selection__'] = self.channel_selection
        return True

    def __restore_session(self):
        """
        restore a previously saved teleboy login session
        """
        with open(self.cache_file, 'rb') as session_fd:
            self.session = pickle.load(session_fd)
        try:
            assert isinstance(self.session, requests.sessions.Session)
            assert self.logged_in()
        except AssertionError:
            print("Failed to restore session")
            raise WatchTeleboyError

    def __dump_session(self):
        """
        write down current teleboy login session
        """
        with open(self.cache_file, 'wb') as session_fd:
            pickle.dump(self.session, session_fd)

    def __set_api_env(self):
        """
        set some environment variables used for API access
          * user_id
          * session_id
        """
        try:
            assert self.logged_in()
            r_env = self.session.get(self.userenv_url)
            assert r_env.status_code == 200
            content = r_env.content.decode()
            uid_raw = re.findall(r'\s+\.setId\(\d+\)', content, re.MULTILINE)[0]
            self.user_id = uid_raw[uid_raw.find('(')+1:uid_raw.find(')')]
            self.session_id = self.session.cookies['cinergy_s']
            return True
        except AssertionError:
            print("Failed to retrieve user_id")
            raise WatchTeleboyError

class WatchTeleboyStreamHandler:
    """
    Parses the given AdaptationSet, selects a representation, and downloads a single
    media stream onto local disk in a non-blocking way.
    """

    def __init__(self, adaptationset, base_url):
        self.adaptationset = adaptationset
        self.base_url = base_url
        assert isinstance(self.adaptationset, minidom.Element)
        self.content_type = self.adaptationset.attributes.get('contentType').value
        self.stream_id = self.adaptationset.attributes.get('id').value
        try:
            self.language = self.adaptationset.attributes.get('lang').value
        except AttributeError:
            self.language = None
        self.representation_elements = self.adaptationset.getElementsByTagName('Representation')
        self.segment_template = self.adaptationset.getElementsByTagName('SegmentTemplate')[0]
        self.segment_timeline = self.segment_template.getElementsByTagName('SegmentTimeline')[0]
        self.segment_timeline_s = self.segment_timeline.getElementsByTagName('S')[0]
        self.segment_start_timestamp = int(self.segment_timeline_s.attributes.get('t').value)
        self.segment_current_timestamp = self.segment_start_timestamp
        self.segment_last_timestamp = sys.maxsize
        self.segment_duration = int(self.segment_timeline_s.attributes.get('d').value)
        self.segment_timescale = int(self.segment_template.attributes.get('timescale').value)
        self.segment_header_template = self.segment_template.attributes.get('initialization').value
        self.segment_media_template = self.segment_template.attributes.get('media').value
        self.representations = self.parse_representations()
        self.select_representation()
        self.download_stop_event = None
        self.download_thread = None

    def parse_representations(self):
        """
        return a dict with representation data
        """
        representations = {}
        for representation in self.representation_elements:
            repr_id = int(representation.attributes.get('id').value)
            attributes = representation.attributes.items()
            representations[repr_id] = attributes
        return representations

    def select_representation(self, representation_id=None):
        """
        select a representation by id
        """
        if representation_id is None:
            representation_id = min(dict(self.representations).keys())
        self.selected_representation = self.representations[representation_id]
        return self.selected_representation

    def bump_timestamp(self):
        """
        increment segment timestamp by duration of segment
        """
        self.segment_current_timestamp += self.segment_duration
        return self.segment_current_timestamp

    def _download_thread(self, outfile):
        """
        download method that is used inside a thread
        """
        max_tries = 5
        dwnld_fd = os.open(outfile, os.O_WRONLY | os.O_CREAT)
        # add init section
        try_count = max_tries
        while not self.initialize_outfile(dwnld_fd):
            try_count -= 1
            if try_count <= 0:
                os.close(dwnld_fd)
                return False
        # download segments
        try_count = max_tries
        while not self.download_stop_event.is_set():
            # check it we reached end of duration
            if self.segment_current_timestamp >= self.segment_last_timestamp:
                break
            # append segments
            try:
                r_dwnld = self.append_media_segment(dwnld_fd)
                assert r_dwnld.status_code == 200
                self.bump_timestamp()
                try_count = max_tries
            except AssertionError:
                if not self.download_stop_event.wait(
                        timeout=self.segment_duration/self.segment_timescale):
                    try_count -= 1
                    if try_count <= 0:
                        os.close(dwnld_fd)
                        return False
        os.close(dwnld_fd)
        return True

    def stop(self):
        """
        stop playback (or recording)
        """
        self.download_stop_event.set()
        try:
            self.download_thread.join()
        except RuntimeError:
            pass

    def set_start_time(self, st_obj):
        """
        set start time (other than now).

        watchteleboy is able to play content from the past
        by accessing old segments that are cached for up to three
        hours.
        """
        # st_obj is expected to be a datetime.datetime object
        start_time = st_obj.timestamp() * self.segment_timescale
        # quantize to segment duration
        start_time = start_time - (start_time % self.segment_duration)
        if start_time > self.segment_start_timestamp:
            print('Cannot watch content from the future')
            raise WatchTeleboyError()
        self.segment_current_timestamp = start_time

    def set_stop_time(self, st_obj):
        """
        set a time (original air time)  for stopping playback (or recording).
        """
        # st_obj is expected to be a datetime.datetime object
        stop_time = st_obj.timestamp() * self.segment_timescale
        stop_time = stop_time - (stop_time % self.segment_duration) # quantize to segment duration
        if stop_time <= self.segment_current_timestamp:
            print('--endtime must be after --starttime')
            raise WatchTeleboyError()
        self.segment_last_timestamp = stop_time

    def start_download(self, outfile, stop_event):
        """
        start downloading segments to given outfile
        """
        self.download_stop_event = stop_event
        self.download_thread = threading.Thread(target=self._download_thread, args=(outfile,))
        self.download_thread.start()

    def initialize_outfile(self, dwnld_fd):
        """
        download initialization segment
        """
        bw_pattern = r'\$Bandwidth\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        stream_header_url = self.base_url + re.sub(bw_pattern, str(bandwidth),
                                                   self.segment_header_template)
        r_header = requests.get(stream_header_url)
        try:
            os.write(dwnld_fd, r_header.content)
        except BrokenPipeError:
            self.stop()
        return r_header.ok

    def append_media_segment(self, dwnld_fd):
        """
        download subsequent media segment and aappend it to file
        """
        bw_pattern = r'\$Bandwidth\$'
        ts_pattern = r'\$Time\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        segment_url = self.base_url + re.sub(bw_pattern, str(bandwidth),
                                             self.segment_media_template)
        segment_url = re.sub(ts_pattern, str(self.segment_current_timestamp),
                             segment_url)
        r_segment = requests.get(segment_url)
        if (r_segment.status_code == 404 and
                self.segment_current_timestamp < self.segment_start_timestamp):
            print("Segment not available. Maybe too old?")
            self.stop() # 404 on segment from the past means caches on server expired
        try:
            os.write(dwnld_fd, r_segment.content)
        except BrokenPipeError:
            self.stop() # this happens only when mpv stopped reading from fifo
        return r_segment

    def wait(self):
        """
        wait for the download thread to finish
        """
        self.download_thread.join()

class WatchTeleboyStreamContainer:
    """
    This class parses an MPD file from given URL (supposedly from a Teleboy streaming server)
    and extracts the necessary information to create individual streams for
    video, audio, and text. It creates the Handler classes that perform the actual download.
    """

    def __init__(self, url):
        self.base_url = '/'.join(url.split('/')[:-1]) + '/'
        r_mpd = requests.get(url)
        try:
            assert r_mpd.status_code == 200
        except AssertionError:
            print('Failed to download manifest')
            raise WatchTeleboyError()
        try:
            self.root = minidom.parseString(r_mpd.content)
        except ExpatError:
            print('Failed to parse manifest')
            raise WatchTeleboyError()
        self.mpd_element = self.root.getElementsByTagName('MPD')[0]
        self.period_element = self.mpd_element.getElementsByTagName('Period')[0]
        self.adaptationset_elements = self.period_element.getElementsByTagName('AdaptationSet')

    def extract_stream(self, content, lang=None):
        """
        return an instance of WatchTeleboyStreamHandler for given content type or language"
        """
        for adaptationset in self.adaptationset_elements:
            if lang is None:
                if adaptationset.attributes.get('contentType').value == content:
                    return WatchTeleboyStreamHandler(adaptationset, self.base_url)
            else:
                if adaptationset.attributes.get('contentType').value == content and \
                    adaptationset.attributes.get('lang').value == lang:
                    return WatchTeleboyStreamHandler(adaptationset, self.base_url)
        return None

    def extract_video_stream(self):
        """
        return an instance of WatchTeleboyStreamHandler with video content
        """
        return self.extract_stream('video')

    def extract_audio_stream(self, lang=None):
        """
        return an instance of WatchTeleboyStreamHandler with audio content
        """
        return self.extract_stream('audio', lang)

    def extract_subtitle_stream(self, lang=None):
        """
        return an instance of WatchTeleboyStreamHandler with subtitles
        """
        return self.extract_stream('text', lang)

    def list_audio_languages(self):
        """
        return a list of available audio streams
        """
        languages = []
        for adaptationset in self.adaptationset_elements:
            if adaptationset.attributes.get('contentType').value == 'audio':
                languages.append(adaptationset.attributes.get('lang').value)
        return languages

class WatchTeleboyPlayer:
    """
    Player for MPD URLs. Controls stream download and playback with mpv.
    """
    def __init__(self, env):
        self.env = env
        self.stop_event = threading.Event()
        self.is_active = False
        self.mpv_returncode = None
        self.mpv_stdout = None
        self.manifest = None
        self.channel = None
        self.audio = None
        self.video = None
        self.playerrecorder = None

    def set_mpd_url(self, mpd_url, channel=None):
        """
        set URL to an MPEG-DASH file to download
        """
        self.stop_event.clear()
        self.manifest = WatchTeleboyStreamContainer(mpd_url)
        self.channel = channel if not None else '-' # channel is used in Window Title
        self.audio = self.manifest.extract_audio_stream()
        self.video = self.manifest.extract_video_stream()
        if self.env['starttime'] is not None:
            stobj = parse_time_string(self.env['starttime'])
            self.audio.set_start_time(stobj)
            self.video.set_start_time(stobj)
        if self.env['endtime'] is not None:
            etobj = parse_time_string(self.env['endtime'])
            self.audio.set_stop_time(etobj)
            self.video.set_stop_time(etobj)
        if self.env['duration'] is not None:
            dobj = parse_duration_string(self.env['duration'])
            etobj = stobj + dobj
            self.audio.set_stop_time(etobj)
            self.video.set_stop_time(etobj)
        # select representation according to max_bitrate fom config
        target_bw = int(self.env['max_bitrate'])
        available_bws = [int(dict(r)['bandwidth']) for r in self.video.representations.values()]
        smaller_bws = [bw for bw in available_bws if bw <= target_bw]
        fitting_bw = max(smaller_bws) if smaller_bws else min(available_bws)
        r_id = [int(dict(r)['id']) for r in self.video.representations.values()
                if int(dict(r)['bandwidth']) == fitting_bw][0]
        self.video.select_representation(representation_id=r_id)

    def get_audio_languages(self):
        """
        return list of available audio streams
        """
        try:
            self.manifest
        except NameError:
            return []
        return self.manifest.list_audio_languages()

    def get_video_representations(self):
        """
        return a list of available video representations
        """
        try:
            self.video
        except NameError:
            return {}
        return self.video.representations

    def set_video_representation(self, representation_id=None):
        """
        set a video representation by id (if none is given, set the one with
        loweset id)
        """
        try:
            self.video
        except NameError:
            return False
        self.video.select_representation(representation_id=representation_id)
        return True

    def set_starttime(self, time):
        """
        set starttime of stream (overrides CLI arguments)"
        """
        stobj = parse_time_string(time)
        self.audio.set_start_time(stobj)
        self.video.set_start_time(stobj)

    def set_audio_language(self, lang=None):
        """
        set audio stream
        """
        self.audio = self.manifest.extract_audio_stream(lang=lang)

    def play(self, output_fd=None):
        """
        start playback
        """
        if self.is_active:
            return
        self.is_active = True
        self.stop_event.clear()
        self.playerrecorder = threading.Thread(target=self._player_thread, args=(output_fd,))
        self.playerrecorder.start()

    def _player_thread(self, output_fd):
        audio_fifo = self.env['fifo'].format(content_type=self.audio.content_type,
                                             id=self.audio.stream_id)
        video_fifo = self.env['fifo'].format(content_type=self.video.content_type,
                                             id=self.video.stream_id)
        os.mkfifo(audio_fifo)
        os.mkfifo(video_fifo)
        self.audio.start_download(audio_fifo, self.stop_event)
        self.video.start_download(video_fifo, self.stop_event)
        try:
            self._run_player(audio_file=audio_fifo, video_file=video_fifo, output_fd=output_fd)
        except KeyboardInterrupt:
            self.stop_event.set()
        self.audio.stop()
        self.video.stop()
        os.unlink(audio_fifo)
        os.unlink(video_fifo)
        self.is_active = False

    def record(self):
        """
        start recording to file
        """
        if self.is_active:
            return
        self.is_active = True
        self.stop_event.clear()
        self.playerrecorder = threading.Thread(target=self._recorder_thread)
        self.playerrecorder.start()

    def _recorder_thread(self):
        if not self.env['showname']:
            showname = f'{self.channel}-{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}'
        else:
            showname = self.env['showname']
        rec_dir = self.env['path'] or self.env['record_dir']
        audio_ts = self.audio.segment_current_timestamp / self.audio.segment_timescale
        video_ts = self.video.segment_current_timestamp / self.video.segment_timescale
        audio_offset = audio_ts - video_ts
        audio_file = f'{rec_dir}/{showname}.m4a'
        video_file = f'{rec_dir}/{showname}.mp4'
        mkv_file = f'{rec_dir}/{showname}.mkv'
        self.audio.start_download(audio_file, self.stop_event)
        self.video.start_download(video_file, self.stop_event)
        try:
            self.audio.wait()
            self.video.wait()
        except KeyboardInterrupt:
            pass
        self.stop_event.set()
        self.audio.stop()
        self.video.stop()
        self._merge_audio_video_to_mkv(audio_file=audio_file, video_file=video_file,
                                       mkv_file=mkv_file, audio_offset=audio_offset)
        os.unlink(audio_file)
        os.unlink(video_file)
        self.is_active = False

    def _run_player(self, audio_file=None, video_file=None, output_fd=None):
        output_fd = output_fd or subprocess.DEVNULL
        mpv_opts_raw = self.env['player_opts'] or self.env['mpv_opts']
        mpv_opts = mpv_opts_raw.split(' ')
        mpv_command = [
            self.env['player_binary'],
            *mpv_opts,
            *self.env['player_args'],
            f'--title={self.channel}',
            f'--audio-file={audio_file}',
            video_file
        ]
        try:
            mpv = subprocess.Popen(mpv_command, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=output_fd)
        except FileNotFoundError:
            print('Cannot play stream, because mpv was not found.')
            print('Please install it with "sudo apt install mpv".')
            self.stop_event.set()
            raise WatchTeleboyError
        while mpv.poll() is None:
            if self.stop_event.wait(timeout=0.1):
                mpv.terminate()
                break
            sleep(0.1)
        self.stop_event.set()
        self.mpv_returncode = mpv.returncode
        self.mpv_stdout = mpv.communicate()[0]
        # make sure to clear pipes in case of mpv error
        if self.mpv_returncode == 1:
            os.open(audio_file, os.O_RDONLY)
            os.open(video_file, os.O_RDONLY)

    @staticmethod
    def _merge_audio_video_to_mkv(audio_file=None, video_file=None,
                                  mkv_file=None, audio_offset=None):
        merge_cmd = [
            '/usr/bin/ffmpeg',
            '-i', video_file,
            '-itsoffset', str(audio_offset),
            '-i', audio_file,
            '-c', 'copy',
            '-map', '0:v:0',
            '-map', '1:a:0', mkv_file
        ]
        try:
            ffmpeg = subprocess.Popen(merge_cmd, stdout=subprocess.DEVNULL,
                                      stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print('Merging audio and video file, because ffmpeg was not found.')
            print('Please install it with "sudo apt install ffmpeg".')
            raise WatchTeleboyError
        ffmpeg.wait()

    def stop(self):
        """
        stop playback (or recording)
        """
        self.stop_event.set()
        try:
            self.playerrecorder.join()
        except AttributeError:
            pass

    def wait(self, timeout=None):
        """
        wait for playback or recording to finish
        """
        self.stop_event.wait(timeout=timeout)
        if not timeout:
            self.playerrecorder.join()
            if self.mpv_returncode == 1:
                print('mpv failed:\n' + self.mpv_stdout.decode())
                raise WatchTeleboyError()
