import faiss
import pickle
import numpy as np
import os

class EmbeddingManager:
    def __init__(self, db_folder="embeddings_db"):
        self.db_folder = db_folder
        self.dim = 512
        # [1] Faiss Index
        # it compares embeddings using L2 distance
        self.index = faiss.IndexFlatL2(self.dim)
        self.names_map = {}

    def load_db_into_memory(self):
        self.index.reset()
        self.names_map = {}
        idx_counter = 0

        for person_name in os.listdir(self.db_folder):
            person_folder = os.path.join(self.db_folder, person_name)
            if not os.path.isdir(person_folder): 
                continue
                
            for file in os.listdir(person_folder):
                if file.endswith('.pkl'):
                    pkl_path = os.path.join(person_folder, file)
                    with open(pkl_path, 'rb') as f:
                            data = pickle.load(f)
                        
                    if isinstance(data, list):
                            vector = np.array(data).astype('float32')
                    else:
                            vector = data.astype('float32')
                            
                    if vector.ndim == 1:
                            vector = vector.reshape(1, -1)
                        
                    self.index.add(vector)
                    self.names_map[idx_counter] = person_name
                    print(f" Loaded: {person_name} (ID: {idx_counter})")
                    idx_counter += 1
                
        print(f"--> Database Ready: {self.index.ntotal} vectors loaded.")
    
    # Pass the new face embedding
    def search_face(self, embedding_vector):
        
        vector_to_search = np.array([embedding_vector]).astype('float32')
        
        if self.index.ntotal == 0: 
            return "Unknown", 99.9

        distances, indices = self.index.search(vector_to_search, k=1)
        
        idx = indices[0][0]
        dist = distances[0][0]
        
        if idx == -1:
            return "Unknown", dist
        
        name = self.names_map.get(idx, "Unknown")
        return name, dist