import yaml
import os

from camera_manager import CameraManager
from frame_processor import save_frame
from video_generator import frames_to_video
from object_detection import load_model, detect_and_filter
from utils import ensure_dir
from motion_filter import MotionFilter


def load_config():
    with open("config.yaml", "r") as f:
        return yaml.safe_load(f)


def main():

    config = load_config()
    cams = config["cameras"]
    settings = config["config"]

    manager = CameraManager(cams)
    model = load_model("yolov8s.pt")

    base_output = settings["output_path"]

    print("\n CCTV Pipeline Started\n")

    for cam_id in cams:

        print(f"\n {cam_id}\n")

        frames = manager.read_all_frames(cam_id)

        selected_dir = os.path.join(base_output, cam_id, "selected_frames")
        detected_dir = os.path.join(base_output, cam_id, "detected_frames")
        summary_dir = os.path.join(base_output, cam_id, "summaries")

        ensure_dir(selected_dir)
        ensure_dir(detected_dir)
        ensure_dir(summary_dir)

        motion = MotionFilter()
        SKIP = 5
        saved_id = 0

        for i, (fid, frame) in enumerate(frames):

            if i % SKIP != 0:
                continue

            if motion.is_motion(frame):
                save_frame(base_output, cam_id, saved_id, frame)
                saved_id += 1

        print(f"Saved {saved_id} motion frames")

        # Object Filter
        detect_and_filter(
            selected_dir,
            detected_dir,
            model,
            conf=settings["yolo_confidence"],
            allowed=settings["allowed_classes"]
        )

        final_video = os.path.join(summary_dir, "final_summary.mp4")
        frames_to_video(detected_dir, final_video, settings["summary_fps"])

        print(f"\nDONE Camera {cam_id}\n")

    print("\n All Cameras are Finished\n")


if __name__ == "__main__":
    main()