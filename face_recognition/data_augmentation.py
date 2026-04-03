import os
import cv2
import numpy as np

def get_face_variations(img):
    h, w = img.shape[:2]
    variations = [img]
    
    # Flip
    variations.append(cv2.flip(img, 1))
    
    # Brightness
    variations.append(np.clip(img * 0.7, 0, 255).astype(np.uint8))
    variations.append(np.clip(img * 1.3, 0, 255).astype(np.uint8))
    
    # Occlusion
    occ = img.copy()
    cv2.rectangle(occ, (int(w*0.2), int(h*0.55)), (int(w*0.8), h), (0,0,0), -1)
    variations.append(occ)
    
    # Rotation
    center = (w // 2, h // 2)
    for angle in [15, -15]:
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        variations.append(cv2.warpAffine(img, M, (w, h)))
    
    # Blur
    variations.append(cv2.GaussianBlur(img, (5, 5), 0))
    
    return variations

def main():
    input_root = "faces"
    output_root = "augmented"
    os.makedirs(output_root, exist_ok=True)

    # <<<--This part will be changed-->>>>
    for root, dirs, files in os.walk(input_root):
        for file in files:
            if not file.lower().endswith(('.jpg', '.jpeg', '.png')):
                continue
            
            person_name = os.path.basename(root)
            save_dir = os.path.join(output_root, person_name)
            os.makedirs(save_dir, exist_ok=True)
            
            img = cv2.imread(os.path.join(root, file))
            img = cv2.resize(img, (160, 160))
            variations = get_face_variations(img)
            
            base_name = os.path.splitext(file)[0]
            for i, var in enumerate(variations):
                cv2.imwrite(os.path.join(save_dir, f"{base_name}_{i}.jpg"), var)
            
            print(f"{person_name}: {len(variations)} images from {file}")

if __name__ == "__main__":
    main()