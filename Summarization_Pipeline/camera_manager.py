import cv2


class CameraManager:
    def __init__(self, cameras):
        self.cameras = cameras

    def open_source(self, source_path):
        print(f" Opening: {source_path}")
        cap = cv2.VideoCapture(source_path)

        if not cap.isOpened():
            print(f"ERROR Cannot open: {source_path}")
            return None

        return cap

    def read_all_frames(self, cam_id):
        sources = self.cameras[cam_id]["sources"]
        all_frames = []

        global_id = 0

        for src in sources:
            cap = self.open_source(src["path"])
            if cap is None:
                continue

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                all_frames.append((global_id, frame))
                global_id += 1

            cap.release()

        print(f"Total frames for {cam_id}: {len(all_frames)}")
        return all_frames