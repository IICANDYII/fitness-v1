"""
SigLIP2-base-patch16-224 本地部署测试脚本
模型: https://huggingface.co/google/siglip2-base-patch16-224

用法:
    python test_siglip2.py
    python test_siglip2.py --image path/to/image.jpg --texts "a dog" "a cat"
"""

import argparse
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModel


def load_model(device=None):
    model_id = "google/siglip2-base-patch16-224"
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {model_id} on {device}...")
    processor = AutoProcessor.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id).to(device)
    model.eval()
    print("Model loaded successfully.")
    return processor, model, device


def classify(processor, model, device, image, texts):
    inputs = processor(text=texts, images=image, padding="max_length", return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model(**inputs)
    logits = outputs.logits_per_image[0]
    probs = torch.sigmoid(logits)
    results = sorted(zip(texts, probs.cpu().tolist()), key=lambda x: x[1], reverse=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="SigLIP2 zero-shot image classification")
    parser.add_argument("--image", type=str, default=None, help="Path to image file")
    parser.add_argument("--texts", nargs="+", default=["a photo of a cat", "a photo of a dog", "a photo of a person exercising"], help="Candidate text labels")
    args = parser.parse_args()

    processor, model, device = load_model()

    if args.image:
        image = Image.open(args.image).convert("RGB")
    else:
        print("No image provided, creating a dummy 224x224 image for testing...")
        image = Image.new("RGB", (224, 224), color=(128, 128, 128))

    results = classify(processor, model, device, image, args.texts)

    print("\n=== Zero-shot Classification Results ===")
    for text, prob in results:
        print(f"  {text}: {prob:.4f}")


if __name__ == "__main__":
    main()
