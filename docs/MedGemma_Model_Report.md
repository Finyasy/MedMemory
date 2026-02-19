# MedGemma 1.5 4B Model Report

> **Reference Document for MedMemory Project**  
> Last Updated: January 2026

## Overview

MedGemma is a collection of Gemma 3 variants trained for performance on **medical text and image comprehension**. MedGemma 1.5 4B is a multimodal instruction-tuned model optimized for healthcare-based AI applications.

- **Model ID**: `google/medgemma-1.5-4b-it`
- **Type**: Image-Text-to-Text (Multimodal)
- **Architecture**: Decoder-only Transformer (Gemma 3 based)
- **License**: Health AI Developer Foundations Terms of Use
- **Created**: January 13, 2026
- **Version**: 1.5.0

## Key Capabilities

### Medical Imaging Support

| Modality | Description |
|----------|-------------|
| **2D Radiology** | Chest X-rays, standard radiographs |
| **3D Radiology** | CT and MRI volume interpretation |
| **Histopathology** | Whole-slide imaging (WSI), H&E stains |
| **Ophthalmology** | Fundus images, diabetic retinopathy screening |
| **Dermatology** | Skin lesion classification, clinical/dermatoscopic |
| **Longitudinal Imaging** | Comparing current vs historical scans |

### Medical Document Understanding

- **Lab Report Extraction**: Structured data extraction from unstructured medical lab reports (PDF/images)
- **EHR Understanding**: Interpretation of text-based electronic health record data
- **Anatomical Localization**: Bounding box detection for chest X-ray findings

### Text Capabilities

- Medical question answering
- Clinical reasoning
- Medical knowledge (MedQA, MedMCQA benchmarks)

## Technical Specifications

| Specification | Value |
|---------------|-------|
| Input Modalities | Text, Vision (multimodal) |
| Output Modality | Text only |
| Attention Mechanism | Grouped-query attention (GQA) |
| Context Length | 128K tokens |
| Max Output Tokens | 8,192 tokens |
| Image Resolution | 896 × 896 (normalized) |
| Image Encoding | 256 tokens per image |
| Image Encoder | SigLIP (medical-pretrained) |

## Usage Examples

### Installation

```bash
pip install -U transformers accelerate torch
```

Requires `transformers >= 4.50.0` for Gemma 3 support.

### Using Pipeline API

```python
from transformers import pipeline
from PIL import Image
import requests
import torch

pipe = pipeline(
    "image-text-to-text",
    model="google/medgemma-1.5-4b-it",
    torch_dtype=torch.bfloat16,
    device="cuda",  # or "mps" for Apple Silicon
)

# Load image
image = Image.open("medical_document.png")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Extract all lab values from this document"}
        ]
    }
]

output = pipe(text=messages, max_new_tokens=2000)
print(output[0]["generated_text"][-1]["content"])
```

### Using Direct Model API

```python
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import torch

model_id = "google/medgemma-1.5-4b-it"

# Load model and processor
model = AutoModelForImageTextToText.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)
processor = AutoProcessor.from_pretrained(model_id)

# Load image
image = Image.open("chest_xray.png").convert("RGB")

# Build messages with image
messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": "Describe this X-ray"}
        ]
    }
]

# Process with apply_chat_template
inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt"
).to(model.device, dtype=torch.bfloat16)

input_len = inputs["input_ids"].shape[-1]

# Generate
with torch.inference_mode():
    generation = model.generate(**inputs, max_new_tokens=2000, do_sample=False)
    generation = generation[0][input_len:]

decoded = processor.decode(generation, skip_special_tokens=True)
print(decoded)
```

### Text-Only Usage

```python
messages = [
    {
        "role": "user",
        "content": "What are the symptoms of Type 2 Diabetes?"
    }
]

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt"
).to(model.device)

with torch.inference_mode():
    generation = model.generate(**inputs, max_new_tokens=500)
```

## Performance Benchmarks

### Medical Text Reasoning

| Dataset | Gemma 3 4B | MedGemma 1 4B | MedGemma 1.5 4B |
|---------|------------|---------------|-----------------|
| MedQA (4-op) | 50.7 | 64.4 | **69.1** |
| MedMCQA | 45.4 | 55.7 | **59.8** |
| PubMedQA | 68.4 | **73.4** | 68.2 |
| MMLU Med | **67.2** | 70.0 | 69.6 |

### Document Understanding (Lab Reports)

| Dataset | Metric | Gemma 3 4B | MedGemma 1.5 4B |
|---------|--------|------------|-----------------|
| Clinical Lab Reports (PNG→JSON) | Macro F1 | 83.0 | **85.0** |
| Clinical Lab Reports (PNG→JSON) | Micro F1 | 78.0 | **83.0** |
| Lab Reports (PDF→JSON) | Macro F1 | 84.0 | **91.0** |

### Radiology Performance

| Task | Dataset | MedGemma 1.5 4B |
|------|---------|-----------------|
| CXR Classification | MIMIC CXR (top 5) | 89.5 F1 |
| CXR Classification | CheXpert (top 5) | 48.2 F1 |
| VQA | VQA-RAD (closed) | 70.2% accuracy |
| Anatomy Detection | Chest ImaGenome | 38.0 IoU |

### 3D Radiology

| Modality | Dataset | MedGemma 1.5 4B |
|----------|---------|-----------------|
| CT | CT Dataset (7 conditions) | 61.1% accuracy |
| MRI | MRI Dataset (10 conditions) | 64.7% accuracy |

## MedMemory Integration

### Backend Configuration

```env
# .env file
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_QUANTIZE_4BIT=true  # For memory efficiency
```

### Vision Chat Endpoint

The `/api/v1/chat/vision` endpoint accepts:
- `image`: Uploaded image file (PNG, JPEG)
- `prompt`: Analysis instructions
- `patient_id`: Patient context

### Recommended Prompts for Document Analysis

```
Analyze this medical document and extract all health information.

Present the results in a clear, organized format:

## Summary
A brief 1-2 sentence overview of what this document shows.

## Results Table
| Test/Measurement | Result | Status | What This Means |
|------------------|--------|--------|-----------------|
(Fill in each test with its value, Normal/Needs Attention/Critical, and explanation)

## Key Takeaways
- Important points for the patient
- Follow-up recommendations
- Reassuring findings

Use simple, patient-friendly language.
```

### Key Implementation Notes

1. **Image Format**: Always convert to RGB: `image.convert("RGB")`
2. **Chat Template**: Use `processor.apply_chat_template()` directly, not `processor.tokenizer.apply_chat_template()`
3. **Message Format**: Image must be inside content array:
   ```python
   {"type": "image", "image": image}  # image object, not bytes
   ```
4. **dtype**: Use `torch.bfloat16` for optimal performance
5. **Memory**: 4-bit quantization recommended for consumer GPUs (< 16GB VRAM)

## Limitations

1. **Not evaluated for multi-turn applications** - Single-turn interactions preferred
2. **Sensitive to prompt format** - May require prompt engineering
3. **English-focused** - Evaluations primarily in English
4. **Not a diagnostic tool** - Requires fine-tuning and validation for clinical use
5. **No interactive elements** - Cannot handle native dialogs or real-time interaction

## Training Data Sources

### Public Datasets
- MIMIC-CXR (chest X-rays and reports)
- ChestX-ray14, CheXpert
- SLAKE, VQA-RAD (medical VQA)
- PAD-UFES-20, SCIN, ISIC (dermatology)
- TCGA, CAMELYON (cancer/pathology)
- PMC-OA (biomedical literature)
- Mendeley Clinical Laboratory Test Reports

### Proprietary/Licensed
- De-identified CT and MRI datasets
- Ophthalmology (EyePACS diabetic retinopathy)
- Dermatology datasets from multiple countries
- Histopathology whole-slide images
- Synthetic EHR data (Synthea-based)

## Citation

```bibtex
@article{sellergren2025medgemma,
  title={MedGemma Technical Report},
  author={Sellergren, Andrew and Kazemzadeh, Sahar and Jaroensri, Tiam and others},
  journal={arXiv preprint arXiv:2507.05201},
  year={2025}
}
```

## Resources

- [Model Card on Hugging Face](https://huggingface.co/google/medgemma-1.5-4b-it)
- [Google Cloud Model Garden](https://cloud.google.com/model-garden)
- [GitHub Repository](https://github.com/google/medgemma)
- [Technical Report (arXiv)](https://arxiv.org/abs/2507.05201)
- [Tutorial Notebooks](https://github.com/google/medgemma/tree/main/notebooks)

---

## Appendix: MedMemory-Specific Code

### Location of Vision Processing

```
backend/app/services/llm/model.py
  └── LLMService.generate_with_image()  # Single image analysis
  └── LLMService.generate_with_images() # Multi-image analysis

backend/app/api/chat.py
  └── ask_with_image()  # /api/v1/chat/vision endpoint
```

### Frontend Vision Chat

```
frontend/src/hooks/useChat.ts
  └── sendVision()  # Handles image upload and streaming response
```
