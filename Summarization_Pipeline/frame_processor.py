import cv2
import os


def save_frame(base_dir, cam_id, frame_id, frame, stage="selected_frames"):
    path = os.path.join(base_dir, cam_id, stage)
    os.makedirs(path, exist_ok=True)

    # resize for speed
    frame = cv2.resize(frame, (640, 360))

    file_path = os.path.join(path, f"frame_{frame_id:06d}.jpg")
    cv2.imwrite(file_path, frame)

    return file_path