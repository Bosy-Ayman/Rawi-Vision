import os
import cv2
import numpy as np

def get_face_variations(img):
    variations = []
    h, w, _ = img.shape
    
    # Original
    variations.append(img)
    
    # Flip Horizontal 
    variations.append(cv2.flip(img, 1))
    
    # Darker (Brightness 0.7x)
    darker = np.clip(img * 0.7, 0, 255).astype(np.uint8)
    variations.append(darker)
    
    # Brighter (Brightness 1.3x)
    brighter = np.clip(img * 1.3, 0, 255).astype(np.uint8)
    variations.append(brighter)
    
    #------------ Occlusion -------------------
    # add a black rectangle over the bottom half
    occ = img.copy()
    cv2.rectangle(occ, (int(w*0.2), int(h*0.55)), (int(w*0.8), h), (0,0,0), -1)
    variations.append(occ)
    
    # 6. Rotation (+15 degrees)
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center,15,1.0)
    rotated_pos = cv2.warpAffine(img, M, (w, h))
    variations.append(rotated_pos)

    # 7. Rotation (-15 degrees)
    M_neg = cv2.getRotationMatrix2D(center,-15, 1.0)
    rotated_neg = cv2.warpAffine(img, M_neg, (w, h))
    variations.append(rotated_neg)
    
    # 8. Gaussian Blur
    blurred = cv2.GaussianBlur(img, (5, 5), 0)
    variations.append(blurred)
    
    return variations

def main():
    input_root = "faces"       
    output_root = "augmented"  

    if not os.path.exists(output_root):
        os.makedirs(output_root)

    # this part will be totally changed after using SQL instead on reading from folders
    for root, dirs, files in os.walk(input_root):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                
                # get the full path to the image
                img_path = os.path.join(root, file)
                # Get the person's name from the folder name
                person_name = os.path.basename(root)
                
                # Create the person's folder in 'augmented'
                save_dir = os.path.join(output_root, person_name)
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                
                img = cv2.imread(img_path)
                img = cv2.resize(img, (160, 160))
                variations = get_face_variations(img)
                
               
                base_name = os.path.splitext(file)[0]
                for i, var in enumerate(variations):
                    save_name = f"{base_name}_{i}.jpg"
                    save_path = os.path.join(save_dir, save_name)
                    cv2.imwrite(save_path, var)
                    
                print(f"  -> {person_name}: Generated {len(variations)} images from {file}")


if __name__ == "__main__":
    main()