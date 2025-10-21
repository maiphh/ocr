from transformers import AutoModel, AutoTokenizer
import torch
import os
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
model_name = 'deepseek-ai/DeepSeek-OCR'

tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
# Use eager attention instead of flash_attention_2 (not available on macOS)
model = AutoModel.from_pretrained(model_name, _attn_implementation='eager', trust_remote_code=True, use_safetensors=True)
# Use CPU or MPS (Metal Performance Shaders) for macOS
device = "mps" if torch.backends.mps.is_available() else "cpu"
model = model.eval().to(device).to(torch.bfloat16 if device == "mps" else torch.float32)

# prompt = "<image>\nFree OCR. "
prompt = "<image>\n<|grounding|>Convert the document to markdown. "
image_file = '/Users/phu.mai/Projects/ocr/data/Absence-cert-BHXH-NewVer 2.pdf'
output_path = 'your/output/dir'

res = model.infer(tokenizer, prompt=prompt, image_file=image_file, output_path = output_path, base_size = 1024, image_size = 640, crop_mode=True, save_results = True, test_compress = True)