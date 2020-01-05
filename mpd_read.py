#!/usr/bin/python3

from xml.dom import minidom
from urllib.request import urlopen
from urllib.parse import urljoin
from urllib.error import HTTPError
from threading import Thread
import re
import time
import sys

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
        self.segment_duration = int(self.segment_timeline_s.attributes.get('d').value)
        self.segment_timescale = int(self.segment_template.attributes.get('timescale').value)
        self.segment_header_template = self.segment_template.attributes.get('initialization').value
        self.segment_media_template = self.segment_template.attributes.get('media').value
        self.representations = self.parse_representations()
        self.select_representation()

    def parse_representations(self):
        representations = {}
        for representation in self.representation_elements:
            repr_id = int(representation.attributes.get('id').value)
            attributes = representation.attributes.items()
            representations[repr_id] = attributes
        return representations

    def select_representation(self, representation_id=None):
        if representation_id is None:
            representation_id = min(dict(self.representations).keys())
        self.selected_representation = self.representations[representation_id]
        return self.selected_representation

    def bump_timestamp(self):
        self.segment_current_timestamp += self.segment_duration
        return self.segment_current_timestamp

    def download_stream(self, outfile):
        self.initialize_outfile(outfile)
        max_tries = 5
        try_count = max_tries
        while True:
            try:
                self.append_media_segment(outfile)
                self.bump_timestamp()
                try_count = max_tries
            except HTTPError:
                time.sleep(self.segment_duration/self.segment_timescale)
                try_count -= 1
                if try_count <= 0:
                    raise

    def nb_download_stream(self, outfile):
        self.download_thread = Thread(target=self.download_stream, args=(outfile,))
        self.download_thread.start()

    def initialize_outfile(self, outfile):
        bw_pattern = r'\$Bandwidth\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        stream_header_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_header_template)
        with open(outfile, 'wb') as outfd:
            outfd.write(urlopen(stream_header_url).read())

    def append_media_segment(self, outfile):
        bw_pattern = r'\$Bandwidth\$'
        ts_pattern = r'\$Time\$'
        bandwidth = dict(self.selected_representation)['bandwidth']
        time = self.segment_current_timestamp
        stream_segment_url = self.base_url + re.sub(bw_pattern, str(bandwidth), self.segment_media_template)
        stream_segment_url = re.sub(ts_pattern, str(time), stream_segment_url)
        with open(outfile, 'ab') as outfd:
            outfd.write(urlopen(stream_segment_url).read())
    
class WatchTeleboyStreamContainer:
    """
    This class parses an MPD file from given URL (supposedly from a Teleboy streaming server)
    and extracts the necessary information to create individual streams for
    video, audio, and text. It creates the Handler classes that perform the actual download.
    """

    def __init__(self, url):
        self.base_url = urljoin(url, '.')
        self.data = urlopen(url).read()
        self.root = minidom.parseString(self.data)
        self.mpd_element = self.root.getElementsByTagName('MPD')[0]
        self.period_element = self.mpd_element.getElementsByTagName('Period')[0]
        self.adaptationset_elements = self.period_element.getElementsByTagName('AdaptationSet')

    def extract_stream(self, content, lang=None):
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
        return self.extract_stream('video')

    def extract_audio_stream(self, lang=None):
        return self.extract_stream('audio', lang)

    def extract_subtitle_stream(self, lang=None):
        return self.extract_stream('text', lang)

    def list_audio_languages(self):
        languages = []
        for adaptationset in self.adaptationset_elements:
            if adaptationset.attributes.get('contentType').value == 'audio':
                languages.append(adaptationset.attributes.get('lang').value)
        return languages

def main():
    MPD_URL = sys.argv[1]
    VIDEO_OUTPUT_FILE = '/tmp/wt.mp4'
    AUDIO_OUTPUT_FILE = '/tmp/wt.mp4a'

    wt_container = WatchTeleboyStreamContainer(MPD_URL)
    wt_video = wt_container.extract_video_stream()
    wt_audio = wt_container.extract_audio_stream()
    wt_video.nb_download_stream(VIDEO_OUTPUT_FILE)
    wt_audio.nb_download_stream(AUDIO_OUTPUT_FILE)

    while True:
        print('audio thread is alive: ' + str(wt_audio.download_thread.is_alive()))
        print('video thread is alive: ' + str(wt_video.download_thread.is_alive()))
        time.sleep(2)

if __name__ == '__main__':
    main()

