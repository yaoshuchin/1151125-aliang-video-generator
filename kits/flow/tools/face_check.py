# -*- coding: utf-8 -*-
"""臉部一致性檢查（2026-11-15）：用 OpenCV 內建的 YuNet（找臉）＋ SFace（比臉），完全本機、免費。
第一次用會自動下載兩個模型（約 39 MB）到 tools/_face_models/；下載失敗或沒有 opencv 就回傳 None（不擋流程）。

python tools/face_check.py 參考照.jpg 圖1.png 圖2.png ...   → 印出每張和參考照的相似度
相似度 ≥ 0.36 大約就是同一個人（SFace 官方門檻 0.363）；本工具出片時要求 ≥ 0.42 才算過。
"""
import os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MD = os.path.join(HERE, "_face_models")
URLS = {
    "det": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "rec": "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}
PASS = 0.42
_M = {}


def _models():
    if _M:
        return _M
    try:
        import cv2  # noqa
    except ImportError:
        return None
    os.makedirs(MD, exist_ok=True)
    paths = {}
    for k, u in URLS.items():
        p = os.path.join(MD, os.path.basename(u))
        if not os.path.exists(p) or os.path.getsize(p) < 100000:
            try:
                urllib.request.urlretrieve(u, p + ".part"); os.replace(p + ".part", p)
            except Exception as e:
                print(f"  （臉部檢查模型下載失敗，略過檢查：{e}）", flush=True); return None
        paths[k] = p
    import cv2, numpy as np
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    buf = lambda p: np.fromfile(p, dtype=np.uint8)       # 從記憶體載入：OpenCV 讀不了中文路徑
    empty = np.array([], np.uint8)
    try:
        _M["det"] = cv2.FaceDetectorYN.create("onnx", buf(paths["det"]), empty, (320, 320), 0.7, 0.3, 5000)
        _M["rec"] = cv2.FaceRecognizerSF.create("onnx", buf(paths["rec"]), empty)
    except Exception as e:
        print(f"  （臉部檢查模型載入失敗，略過檢查：{e}）", flush=True); _M.clear(); return None
    return _M


def faces(path):
    """回傳這張圖裡每張臉的 (面積, 特徵)；依面積由大到小。"""
    m = _models()
    if not m:
        return None
    import cv2, numpy as np
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return []
    h, w = img.shape[:2]
    s = 1280 / max(h, w) if max(h, w) > 1280 else 1.0
    if s != 1.0:
        img = cv2.resize(img, (int(w * s), int(h * s))); h, w = img.shape[:2]
    m["det"].setInputSize((w, h))
    _, det = m["det"].detect(img)
    out = []
    for f in (det if det is not None else []):
        al = m["rec"].alignCrop(img, f)
        out.append((float(f[2] * f[3]), m["rec"].feature(al)))
    return sorted(out, key=lambda x: -x[0])


def best_match(ref_feat, path):
    """這張圖裡和參考臉最像的那張臉的相似度（找不到臉回傳 0.0；沒有模型回傳 None）。"""
    fs = faces(path)
    if fs is None:
        return None
    if not fs:
        return 0.0
    m = _models()
    import cv2
    return max(float(m["rec"].match(ref_feat, f, cv2.FaceRecognizerSF_FR_COSINE)) for _, f in fs)


def ref_feature(path):
    fs = faces(path)
    if not fs:
        return None
    return fs[0][1]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ref = ref_feature(sys.argv[1])
    if ref is None:
        sys.exit("參考照找不到臉（或沒有 opencv）")
    for p in sys.argv[2:]:
        s = best_match(ref, p)
        print(f"{s:.3f}  {'✓' if s is not None and s >= PASS else '✗'}  {p}")
