#!/usr/bin/env python3

import os
import time

import ffmpeg

from waggle import plugin
from waggle.data.vision import resolve_device
from waggle.data.timestamp import get_timestamp


def need_resampling(filepath, target_fps):
    probe = ffmpeg.probe(filepath)
    need_change_fps = False
    try:
        f = probe['streams'][0]['r_frame_rate']
        # NOTE: use the fps with 10% margin 
        #       in case r_frame_rate does not equal exactly to the fps
        return False if (target_fps * 0.9) <= eval(f) <= (target_fps * 1.1) else True
    except:
        print(f'Could not probe {filepath} to get framerate. Cannot determine if resampling is needed')
        return False


def run(args):
    stream_url = resolve_device(args.stream)

    # Assume PyWaggle's timestamp is in nano seconds
    timestamp = get_timestamp() + skip_second * 1e9
    try:
        script_dir = os.path.dirname(__file__)
    except NameError:
        script_dir = os.getcwd()
    filename_raw = os.path.join(script_dir, 'sample_raw.mp4')
    filename = os.path.join(script_dir, 'sample.mp4')

    while True:
        print(f'Sampling {stream_url}...')
        c = ffmpeg.input(stream_url, ss=args.skip_second).output(
            filename_raw,
            codec = "copy", # use same codecs of the original video
            f='mp4',
            t=args.duration).overwrite_output()
        # print(c.compile())
        c.run()

        d = ffmpeg.input(filename_raw)
        if args.resampling:
            print(f'Resampling to {stream.resampling_fps}...')
            d = ffmpeg.filter(d, 'fps', fps=args.resampling_fps)
        d = output(filename, f='mp4', t=args.duration).overwrite_output()
        # print(d.compile())
        d.run()

        print('Uploading...')
        plugin.upload_file(filename)
        print('Done')
        if args.interval > 0:
            time.sleep(args.interval)

    return 0


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-stream', dest='stream',
        action='store', default="camera", type=str,
        help='ID or name of a stream, e.g. sample')
    parser.add_argument(
        '-interval', dest='interval',
        action='store', default=0, type=int,
        help='Sampling interval in seconds')
    parser.add_argument(
        '-duration', dest='duration',
        action='store', default=10., type=float,
        help='Time duration for input video')
    parser.add_argument(
        '-skip-second', dest='skip_second',
        action='store', default=3., type=float,
        help='Seconds to skip before recording')
    parser.add_argument(
        '-resampling', dest='resampling',
        action='store_false', help="Resampling the sample to -resample-fps option (defualt 12)")
    parser.add_argument(
        '-resampling-fps', dest='resampling_fps',
        action='store', default=12., type=float,
        help='Target frames per second that will be resampled from input video')
    args = parser.parse_args()
    exit(run(args))
