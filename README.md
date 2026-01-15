# Short-sort

https://github.com/user-attachments/assets/6598c797-0715-443f-9878-f8ce5d0242dc

# 🎬 Short-Sort

Lets you delete videos from local storage while you scroll through them.
Depending on how many videos there are, first load might take a few seconds.

##  Required Packages

```bash
pip install flask
pip install waitress
```

##  Setup & Usage

1. **Configure Folder Path**: Edit `Short-Sort.py` (text editor) and add your folder path:
   ```python
   VIDEO_FOLDER = "your/video/folder/path"
   ```
   *(Videos in subfolders will be included)*

2. **Start the Application**: Run `Short-Sort.py`

3. **Access Web Interface**: Open your web browser and go to:
   ```
   http://127.0.0.1:5000
   ```
   or
   ```
   http://localhost:5000
   ```

## ⌨️ Controls

### Navigation
- **Arrow ↓** or **Mouse Wheel Down**: Next Video
- **Arrow ↑** or **Mouse Wheel Up**: Previous Video
- **NumPad 0**: Skip forward 10% in playing video

### Delete Functionality
- **Arrow →** (once): Mark video for deletion
- **Arrow →** (again): Delete video from your drive **⚠️ WARNING: This action is irreversible**

### Additional Controls
- **Arrow Left ←**: Cancel deletion confirmation window
- **Ctrl+C**: Close application via command line or simply **X** close it.

### Reset Watched Videos
To rewatch already viewed videos, simply delete the `watched_videos.db` file in the script folder.
Info: This version does not include .mkv files. Transcoding/ffmpeg was removed too for simplicity.
