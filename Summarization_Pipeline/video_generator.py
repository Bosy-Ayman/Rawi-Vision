import cv2
import glob
import os


def frames_to_video(frames_dir, output_path, fps=12):

    frames = sorted(glob.glob(os.path.join(frames_dir, "*.jpg")))

    if not frames:
        print("No frames found")
        return

    first = None
    for f in frames:
        first = cv2.imread(f)
        if first is not None:
            break

    if first is None:
        print("No valid images")
        return

    h, w, _ = first.shape

    writer = cv2.VideoWriter(
        output_path,
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (w, h)
    )

    count = 0

    for f in frames:
        try:
            img = cv2.imread(f)
            if img is None:
                continue

            writer.write(img)
            count += 1

        except:
            continue

    writer.release()
    print(f"Video saved: {output_path} ({count} frames)")