import json
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import roc_curve, auc, precision_recall_curve, classification_report
from collections import defaultdict

# ========================== LOAD DATA ==========================
with open("evaluation_results.json") as f:
    data = json.load(f)

gt_map = {1: "yoan", 2: "tess"}   

# Build ground truth dict (frame, track_id) -> true name
true_dict = {}
for frame_str, tracks in data["frame_results"].items():
    frame = int(frame_str)
    for t in tracks:
        tid = t["track_id"]
        if tid in gt_map:
            true_dict[(frame, tid)] = gt_map[tid]

attempts = data.get("all_face_attempts", [])
if not attempts:
    print("No all_face_attempts found. Run pipeline with logging first.")
    exit()

y_true_binary = []
y_score = []
labels = []
distances = []

for att in attempts:
    frame = att["frame"]
    tid = att["track_id"]
    pred_name = att["name"]
    dist = att["distance"]
    key = (frame, tid)
    if key in true_dict:
        true_name = true_dict[key]
        is_correct = (pred_name == true_name)
        y_true_binary.append(1 if is_correct else 0)
        y_score.append(-dist)
        labels.append(true_name)
        distances.append(dist)

if len(y_true_binary) == 0:
    print("No ground truth matches. Check gt_map and frame_results.")
    exit()

correct = sum(y_true_binary)
total = len(y_true_binary)
accuracy = correct / total
print(f"Frame-level accuracy (all attempts): {accuracy:.4f} ({correct}/{total})")

# Distance distribution per person
dist_by_person = defaultdict(list)
for name, d in zip(labels, distances):
    dist_by_person[name].append(d)

plt.figure(figsize=(8,5))
# Fix for Matplotlib deprecation: use tick_labels instead of labels
bp = plt.boxplot([dist_by_person[p] for p in sorted(dist_by_person.keys())])
plt.xticks(range(1, len(dist_by_person)+1), sorted(dist_by_person.keys()))
plt.xlabel("Person")
plt.ylabel("Embedding distance")
plt.title("Distance distribution per person")
plt.savefig("distance_boxplot.png")
plt.show()

print("\nDistance statistics:")
for name, dlist in dist_by_person.items():
    print(f"  {name}: mean={np.mean(dlist):.3f}, std={np.std(dlist):.3f}")

# Accuracy over time
frame_acc = []
frame_numbers = []
for frame_str in sorted(data["frame_results"].keys(), key=int):
    frame = int(frame_str)
    tracks = data["frame_results"][frame_str]
    correct_f = 0
    total_f = 0
    for t in tracks:
        tid = t["track_id"]
        pred = t["name"]
        if tid in gt_map:
            total_f += 1
            if pred == gt_map[tid]:
                correct_f += 1
    acc_f = correct_f / total_f if total_f > 0 else np.nan
    frame_acc.append(acc_f)
    frame_numbers.append(frame)

plt.figure(figsize=(12,4))
plt.plot(frame_numbers, frame_acc, 'b-', linewidth=0.5)
plt.ylim(0,1.05)
plt.xlabel("Frame number")
plt.ylabel("Frame accuracy")
plt.title("Per-frame recognition accuracy")
plt.grid(True)
plt.savefig("accuracy_over_time.png")
plt.show()

# Track-level metrics
track_first_name = {}
for ev in data["recognition_events"]:
    tid = ev["track_id"]
    if tid not in track_first_name:
        track_first_name[tid] = ev["name"]

y_true_track = []
y_pred_track = []
for tid, true_name in gt_map.items():
    pred_name = track_first_name.get(tid, "Unknown")
    y_true_track.append(true_name)
    y_pred_track.append(pred_name)

print("\nTrack-level classification report:")
print(classification_report(y_true_track, y_pred_track, zero_division=0))

# Latency
first_appearance = {}
for frame_str, tracks in data["frame_results"].items():
    frame = int(frame_str)
    for t in tracks:
        tid = t["track_id"]
        if tid in gt_map and tid not in first_appearance:
            first_appearance[tid] = frame

recognition_frame = {}
for ev in data["recognition_events"]:
    tid = ev["track_id"]
    if tid not in recognition_frame:
        recognition_frame[tid] = ev["frame"]

latencies = []
names = []
for tid in gt_map:
    if tid in recognition_frame and tid in first_appearance:
        lat = recognition_frame[tid] - first_appearance[tid]
        latencies.append(lat)
        names.append(gt_map[tid])

if latencies:
    plt.figure()
    plt.bar(names, latencies)
    plt.xlabel("Person")
    plt.ylabel("Latency (frames)")
    plt.title("Recognition latency")
    plt.savefig("latency.png")
    plt.show()
    print("\nLatency (frames):", dict(zip(names, latencies)))

# ROC and PR curves only if both positive and negative samples exist
unique_true = set(y_true_binary)
if len(unique_true) == 2:
    fpr, tpr, _ = roc_curve(y_true_binary, y_score)
    roc_auc = auc(fpr, tpr)
    plt.figure()
    plt.plot(fpr, tpr, label=f'ROC (AUC = {roc_auc:.3f})')
    plt.plot([0,1],[0,1],'k--')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve')
    plt.legend()
    plt.savefig('roc_curve.png')
    plt.show()

    precision, recall, _ = precision_recall_curve(y_true_binary, y_score)
    plt.figure()
    plt.plot(recall, precision)
    plt.xlabel('Recall')
    plt.ylabel('Precision')
    plt.title('Precision-Recall Curve')
    plt.savefig('pr_curve.png')
    plt.show()
else:
    print("\n ROC and PR curves cannot be computed – not enough negative samples (all predictions correct).")
    print("   This is expected if your pipeline never misclassifies a known person.")