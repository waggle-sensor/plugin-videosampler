#!/usr/bin/env python3

import os
import re
import time
import argparse
import logging

import ffmpeg

from waggle.plugin import Plugin
from waggle.data.vision import resolve_device
from waggle.data.timestamp import get_timestamp


def extract_topics(expr):
    topics = re.findall(r"\b[a-z]\w+", expr)
    for reserved in ['or', 'and']:
        while True:
            try:
                topics.remove(reserved)
            except ValueError:
                break
    return topics


def need_resampling(filepath, target_fps):
    probe = ffmpeg.probe(filepath)
    need_change_fps = False
    try:
        f = probe['streams'][0]['r_frame_rate']
        # NOTE: use the fps with 10% margin 
        #       in case r_frame_rate does not equal exactly to the fps
        return False if (target_fps * 0.9) <= eval(f) <= (target_fps * 1.1) else True
    except:
        logging.info('Could not probe %s to get framerate. Cannot determine if resampling is needed', filepath)
        return False


def take_sample(stream, duration, skip_second, codec, resampling, resampling_fps):
    stream_url = resolve_device(stream)
    # Assume PyWaggle's timestamp is in nano seconds
    timestamp = get_timestamp() + int(skip_second * 1e9)
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()
    filename_raw = os.path.join(script_dir, 'sample_raw.mp4')
    filename = os.path.join(script_dir, 'sample.mp4')

    # To prevent corruption in frames we prefer tcp transfer for rtsp
    if stream_url.startswith("rtsp"):
        c = ffmpeg.input(stream_url, rtsp_transport="tcp", ss=skip_second)
    else:
        c = ffmpeg.input(stream_url, ss=skip_second)
    c = ffmpeg.output(
        c,
        filename_raw,
        codec=codec, # use same codecs of the original video
        f='mp4',
        t=duration).overwrite_output()
    logging.info("running command: %s", c.compile())
    c.run(quiet=True)

    d = ffmpeg.input(filename_raw)
    if resampling:
        logging.info('Resampling to %s...', resampling_fps)
        d = ffmpeg.filter(d, 'fps', fps=resampling_fps)
        d = ffmpeg.output(d, filename, f='mp4', t=duration).overwrite_output()
    else:
        d = ffmpeg.output(d, filename, codec="copy", f='mp4', t=duration).overwrite_output()
    logging.info("running command: %s", d.compile())
    d.run(quiet=True)
    # TODO: We may want to inspect whether the ffmpeg commands succeeded
    return True, filename, timestamp


def run_on_event(args):
    logging.info('Starting video sampler whenever %s becomes valid', args.condition)
    with Plugin() as plugin:
        topics = {}
        condition = args.condition.replace('.', '_')
        for t in extract_topics(condition):
            topics[t] = 0.
            plugin.subscribe(t.replace('_', '.'))

        while True:
            msg = plugin.get()
            # NOTE: We do not care any messages older than 5 seconds
            if time.time() * 1e9 - msg.timestamp <= 5 * 1e9:
                topics[msg.name.replace('.', '_')] = msg.value

            # Check if given condition is valid
            result = False
            try:
                result = eval(condition, topics)
            except:
                pass

            if result:
                logging.info('%s is valid. Getting a video sample...', args.condition)
                ret, filename, timestamp = take_sample(
                    stream=args.stream,
                    duration=args.duration,
                    skip_second=args.skip_second,
                    code=args.codec,
                    resampling=args.resampling,
                    resampling_fps=args.resampling_fps
                )

                if ret:
                    logging.info('Uploading...')
                    plugin.upload_file(filename, timestamp=timestamp)
                    logging.info('Done')
                else:
                    logging.info('Failed to take a video sample.')
                    return 1
                if not args.continuous:
                    break
                logging.info('Resetting the condition: %s', args.condition)
                topics = {}
            else:
                time.sleep(0.1)
    return 0


def run_periodically(args):
    logging.info('Starting video sampler periodically with %s seconds interval', args.interval)
    if args.samples > -1:
        sample_count = args.samples
    else:
        sample_count = 100
    count = 0
    with Plugin() as plugin:
        while sample_count > count:
            logging.info('Sampling %s...', args.stream)
            ret, filename, timestamp = take_sample(
                stream=args.stream,
                duration=args.duration,
                skip_second=args.skip_second,
                codec=args.codec,
                resampling=args.resampling,
                resampling_fps=args.resampling_fps
            )
            if ret:
                logging.info('Uploading...')
                plugin.upload_file(filename, timestamp=timestamp)
                logging.info('Done')
            else:
                logging.info('Failed to take a video sample.')
                return 1
            if not args.continuous:
                break
            if args.interval > 0:
                time.sleep(args.interval)
            if args.samples > -1:
                count += 1
    return 0


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-debug", action="store_true", help="enable debug logs")
    parser.add_argument(
        '-stream', dest='stream',
        action='store', default="camera", type=str,
        help='ID or name of a stream, e.g. sample')
    parser.add_argument(
        '-continuous', dest='continuous',
        action='store_true',
        help='Run continuousely with given -interval or -condition')
    parser.add_argument(
        '-interval', dest='interval',
        action='store', default=0, type=int,
        help='Sampling interval in seconds')
    parser.add_argument(
        '-samples', dest='samples',
        action='store', default=-1, type=int,
        help='Number of samples. -1 samples videos indefinitely. Working only without -condition option.')
    parser.add_argument(
        '-duration', dest='duration',
        action='store', default=10., type=float,
        help='Time duration for input video')
    parser.add_argument(
        '-skip-second', dest='skip_second',
        action='store', default=3., type=float,
        help='Seconds to skip before recording')
    parser.add_argument(
        '-codec', dest='codec',
        action='store', default="copy", type=str,
        help='Codec name to use. Default is the codec inherited from the source')
    parser.add_argument(
        '-condition', dest='condition',
        action='store', default="", type=str,
        help='Triggering condition')
    parser.add_argument(
        '-resampling', dest='resampling', default=False,
        action='store_true', help="Resampling the sample to -resample-fps option (defualt 12)")
    parser.add_argument(
        '-resampling-fps', dest='resampling_fps',
        action='store', default=12., type=float,
        help='Target frames per second that will be resampled from input video')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%Y/%m/%d %H:%M:%S",
    )

    if args.condition == "":
        exit(run_periodically(args))
    else:
        exit(run_on_event(args))
