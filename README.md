# Video Sampler Plugin
This plugin samples video clips from a stream using [ffmpeg-python](https://github.com/kkroening/ffmpeg-python). Sampled video clips are stored locally and uploaded to the cloud. This helps to create datasets used for training machine learning models requiring video clips.

# How to use
To record a video, simply run,
```bash
# sample a 30-second video clip from an rtsp stream
python3 record.py -stream rtsp://IP:PORT/media.smp -duration 30

# sample a 10-second video clip from an rtsp stream
# and resample the video to get a 12 frames-per-second video
python3 record.py -stream rtsp://IP:PORT/media.smp -duration 30 -resampling -resampling-fps 12

# sample a 5-second video clip from an rtsp stream
# when there is one or more cars recognized
python3 record.py -stream rtsp://IP_PORT/media.smp -duration 5 -condition "env.count.car > 0"
```
