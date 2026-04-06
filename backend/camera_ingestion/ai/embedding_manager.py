import psycopg2
import numpy as np
import faiss
import json

class EmbeddingManager:
    def __init__(self, db_config, dim=512):
        self.db_config = db_config
        self.dim = dim
        self.index = faiss.IndexFlatL2(self.dim)
        self.names_map = {}

    def load_db_into_memory(self):
        self.index.reset()
        self.names_map = {}

        conn = psycopg2.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute("SELECT first_name, last_name, embedding FROM employees")
        rows = cursor.fetchall()

        for idx, (first_name, last_name, embedding) in enumerate(rows):
            full_name = f"{first_name} {last_name}"
            if not embedding:
                print(f"Skipping {full_name}: empty embedding")
                continue
            vector = np.array(embedding, dtype='float32')
            if vector.size == 0:
                print(f"Skipping {full_name}: empty vector")
                continue
            if vector.ndim == 1:
                vector = vector.reshape(1, -1)
            if vector.shape[1] != self.dim:
                print(f"Skipping {full_name}: wrong dimension {vector.shape[1]}")
                continue

            self.index.add(vector)
            self.names_map[idx] = full_name
            print(f"Loaded: {full_name} (ID: {idx})")

        cursor.close()
        conn.close()
        print(f"--> Database Ready: {self.index.ntotal} vectors loaded.")

    def search_face(self, embedding_vector):
        vector_to_search = np.array([embedding_vector]).astype('float32')
        if self.index.ntotal == 0:
            return "Unknown", 99.9
        distances, indices = self.index.search(vector_to_search, k=1)
        idx = indices[0][0]
        dist = distances[0][0]
        if idx == -1:
            return "Unknown", dist
        return self.names_map.get(idx, "Unknown"), dist


db_config = {
    "host": "localhost",
    "port": 5432,
    "dbname": "rawivision_db",
    "user": "shahd",
    "password": "password"
}