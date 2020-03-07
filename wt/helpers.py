"""
some helper functions used by watchteleboy
"""

import argparse
import configparser
from datetime import date, datetime, time, timedelta
import os
import random
import sys

import crontab # DEB: python3-crontab

import wt

CONFIG_TEMPLATE = """[watchteleboy]
# watchteleboy configuration

# Teleboy Login Credentials
teleboy_user = {teleboy_user}
teleboy_pass = {teleboy_pass}

# Teleboy users may customize the channel selection and the channel
# ordering. You may chose whether you want watchteleboy to display
# all available channels (in default order) or use a customized
# channel list in user-defined order. You may visit
# http://www.teleboy.ch/en/sender to customize your personal
# channel selection. Allowed values: 'all', 'custom'
channel_selection = {channel_selection}

# Additional flags passed to mpv
mpv_opts = {mpv_opts}

# This can be overridden by the -p/--path flag:
record_dir = {record_dir}

# Several variants of a stream are available. The
# variants come with different bitrates and different video
# resolutions.
# Bitrate:    |   Resolution
# ------------+--------------
#   250000    |   400x224/12.5fps
#   452000    |   512x288/25fps
#   700000    |   512x288/25fps
#  1300000    |   768x432/25fps
#  2800000    |   1280x720/25fps
#  4800000    |   1280x720/50fps
# Per default watchteleboy automatically selects the variant
# with the highest quality. When max_bitrate is set, the variant
# that still fits the constraint is selected.
max_bitrate = {max_bitrate}
"""

##################################################################################
# SOME HELPER FUNCTIONS
##################################################################################

def parse_args():
    """
    parse commandline arguments passed to watchteleboy
    """
    parser = argparse.ArgumentParser(description="Watch and record MPEG-DASH streams from Teleboy")
    oneshots = parser.add_mutually_exclusive_group()
    oneshots.add_argument("-l", "--list", help="list available channels", action="store_true")
    oneshots.add_argument("--print-url", help="print url of channel instead of starting playback",
                          action="store_true")
    oneshots.add_argument("-v", "--version", help="print version", action="store_true")
    parser.add_argument("-c", "--channel", help="select channel for playback or recording")
    parser.add_argument("-t", "--starttime",
                        help="specify a start time other than 'now' ([YYYY-mm-dd ]HH:MM[:SS])")
    length = parser.add_mutually_exclusive_group()
    length.add_argument("-e", "--endtime", help="specify an end time ([YYYY-mm-dd ]HH:MM[:SS])")
    length.add_argument("-d", "--duration", help="specify a duration ([[HH:]MM:]SS)")
    parser.add_argument("-q", "--quiet", help="suppress any output", action="store_true")
    parser.add_argument("--player-opts", help="options passed to mpv player")
    rec = parser.add_argument_group()
    rec.add_argument("-r", "--record", help="record a stream to a file", action="store_true")
    rec.add_argument("-p", "--path", help="specify target directory for recordings")
    rec.add_argument("-n", "--showname", help="specify file name prefix for recorded file")
    rec.add_argument("--delete-cronjob", help=argparse.SUPPRESS)
    args = parser.parse_args()
    # enforce some logic
    if args.starttime and not args.endtime and not args.duration:
        print('watchteleboy: error: If --starttime is specified, ' +
              'either --endtime or --duration is required.')
        raise wt.WatchTeleboyError
    return args

def parse_time_string(rawstring):
    """
    Returns a datetime object from a string containing time. It does some magic
    to guess the datepart (if not specified). It understands 'yesterday' and
    'tomorrow' as dates.
    Format: [YYYY-MM-DD ]HH:MM[:ss]
    """
    def guess_date(start):
        """
        if midnight is not long ago, assume evening times to be
        from yesterday
        """
        extend_old_day_hours = 4
        now = datetime.now()
        today = now.date()
        dt1 = datetime.combine(today, time(0, 0)) + timedelta(hours=extend_old_day_hours)
        dt2 = datetime.combine(today, time(0, 0)) - timedelta(hours=extend_old_day_hours)
        past_midnight = dt1.time()
        before_midnight = dt2.time()
        if now.time() < past_midnight and start > before_midnight:
            return today - timedelta(days=1)
        elif now.time() > before_midnight and start < past_midnight:
            return today + timedelta(days=1)
        return today

    def evaluate_time(tstr):
        """
        convert time part to time object
        """
        try:
            return time(*list(map(int, tstr.split(':'))))
        except ValueError:
            print('Cannot parse given time: ' + tstr)
            raise wt.WatchTeleboyError

    def evaluate_date(dstr):
        """
        convert date part to date object
        """
        try:
            if dstr == 'tomorrow':
                return date.today() + timedelta(days=1)
            elif dstr == 'yesterday':
                return date.today() + timedelta(days=-1)
            return date(*list(map(int, dstr.split('-'))))
        except ValueError:
            print('Cannot parse given date: '  + dstr)
            raise wt.WatchTeleboyError

    dtstr = rawstring.split(' ')
    if len(dtstr) == 1:
        timepart = evaluate_time(dtstr[0])
        datepart = guess_date(timepart)
    elif len(dtstr) == 2:
        datepart = evaluate_date(dtstr[0])
        timepart = evaluate_time(dtstr[1])
    else:
        print('Cannot parse given time: ' + dtstr)
        raise wt.WatchTeleboyError
    return datetime.combine(datepart, timepart)

def parse_duration_string(dstr):
    """
    accept a string containing a duration of the format [[HH:]MM:]ss
    and return a datetime.timedelta object
    """
    try:
        dlist = list(map(int, dstr.split(':')))
        assert len(dlist) <= 3
    except ValueError:
        print(f'Could not parse duration: {dstr}')
        raise wt.WatchTeleboyError
    except AssertionError:
        print(f'Could not parse duration, too many fields: {dstr}')
        raise wt.WatchTeleboyError
    seconds = dlist[-1]
    try:
        minutes = dlist[-2]
    except IndexError:
        minutes = 0
    try:
        hours = dlist[-3]
    except IndexError:
        hours = 0
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)

def create_env(defaults):
    """
    create and return environment dict from defaults, configuration, commandline
    arguments (in this order)
    """
    defaults['wt_dir'] = defaults['wt_dir'].format(home_dir=defaults['home_dir'])
    defaults['record_dir'] = defaults['record_dir'].format(home_dir=defaults['home_dir'])
    defaults['configfile'] = defaults['configfile'].format(wt_dir=defaults['wt_dir'])
    defaults['session_cache'] = defaults['session_cache'].format(wt_dir=defaults['wt_dir'])
    defaults['wt_instance'] = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz0123456789')
                                      for i in range(8))
    defaults['fifo'] = defaults['fifo'].format(wt_dir=defaults['wt_dir'],
                                               wt_instance=defaults['wt_instance'],
                                               content_type='{content_type}',
                                               id='{id}')
    try:
        os.mkdir(defaults['wt_dir'])
    except FileExistsError:
        pass
    try:
        config = read_config(defaults)
    except KeyError:
        create_config(defaults)
        config = read_config(defaults)
    args = parse_args()
    return {**defaults, **config, **args.__dict__}

def create_config(defaults):
    """
    create configuration file with valid teleboy credentials
    """
    wts = wt.WatchTeleboySession(defaults['session_cache'])
    while not wts.logged_in():
        try:
            user = input("Please enter your teleboy username: ")
            password = input("Please enter your teleboy password: ")
        except KeyboardInterrupt:
            sys.exit()
        wts.login(user=user, password=password)
    consent = input("Password is written in plain text to config. OK? [y/n] ")
    if consent == 'n':
        sys.exit()
    config_content = CONFIG_TEMPLATE.format(
        teleboy_user=user,
        teleboy_pass=password,
        mpv_opts=defaults['mpv_opts'],
        record_dir=defaults['record_dir'],
        channel_selection=defaults['channel_selection'],
        max_bitrate=defaults['max_bitrate'])
    with open(defaults['configfile'], 'w') as configfile:
        configfile.write(config_content)

def read_config(defaults):
    """
    read configuration file and return config
    """
    config = configparser.ConfigParser()
    config.read(defaults['configfile'])
    return config['watchteleboy']

def schedule_recording(env):
    """
    schedule a recording by creating a job in current user's crontab file
    """
    st_obj = parse_time_string(env['starttime'])
    if env['endtime']:
        et_obj = parse_time_string(env['endtime'])
        st_et_delta = et_obj - st_obj
    else:
        st_et_delta = parse_duration_string(env['duration'])
    duration = st_et_delta.seconds
    try:
        assert st_obj < et_obj
    except AssertionError:
        print('--endtime must be after --starttime')
        raise wt.WatchTeleboyError
    cron = crontab.CronTab(user=True)
    command = f'{env["wt_abspath"]} --record --channel \'{env["channel"]}\' '\
               '--starttime \'{env["starttime"]}\' --duration \'{duration}\' '\
               '--path \'{env["record_dir"]}\' --showname \'{env["showname"]}\' '\
               '--delete-cronjob \'{env["wt_instance"]}\''
    job = cron.new(command=command)
    # we do not want to start recording before segments are available
    # consider start_time=19:29:59 would be scheduled to 19:31, which means
    # segments are at least one minute old when we start downloading.
    job.minute.on(st_obj.minute+2)
    job.hour.on(st_obj.hour)
    job.day.on(st_obj.day)
    job.month.on(st_obj.month)
    cron.write()

def delete_cronjob(env):
    """
    delete a previously scheduled cron job
    """
    cron = crontab.CronTab(user=True)
    cron.remove_all(command=env['delete_cronjob'])
    cron.write()

def convert_mpv_timestring(t_str):
    """
    convert mpv time from stdout (that shows hours since 1970)
    to a human readable datetime string
    """
    hours, minutes, seconds = list(map(int, t_str.split(':')))
    epoch = hours*3600 + minutes*60 + seconds
    cur_dt = datetime.fromtimestamp(epoch)
    return cur_dt.strftime('%Y-%m-%d %H:%M:%S')
