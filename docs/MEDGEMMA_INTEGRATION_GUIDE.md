# MedMemory × MedGemma Integration Guide

## Harnessing AI to Build Your Medical Memory

**Vision**: *Everyone deserves the best answers modern medicine can give them.*

---

## The Problem We Solve

Health data today is:
- **Scattered** across 4 hospitals, 2 labs, 7 apps, 3 portals
- **Fragmented** with no unified view
- **Overwhelming** for clinicians with limited time
- **Inaccessible** to patients who need it most

**MedMemory** unifies this chaos into a **context engine** powered by **MedGemma 1.5**, Google's state-of-the-art medical AI.

---

## MedGemma 1.5 Capabilities → MedMemory Features

### 1. Electronic Health Record Understanding

**MedGemma Capability**: Interpret text-based EHR data, extract structured information from unstructured records.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/ask
```

**Use Cases**:
| User Need | How MedMemory Helps |
|-----------|---------------------|
| "What medications am I on?" | Extracts all active medications across records |
| "Show my A1C trend over 2 years" | Finds and plots lab values over time |
| "When was my last colonoscopy?" | Searches across all visit notes |
| "Compare my kidney function to last year" | Identifies eGFR values and calculates change |

**Technical Flow**:
```
User Question → Embedding Search → Context Retrieval → MedGemma RAG → Cited Answer
       ↓              ↓                  ↓                 ↓
   "A1C trend"   pgvector search    Lab results      "Your A1C improved
                                    from 3 visits     from 7.2% to 6.8%
                                                      over 18 months"
```

**Prompt Design**:
```
You are a clinical AI with expertise in electronic health records.
- Extract and cite specific values, dates, and measurements
- Identify trends and changes over time
- Provide clinical context when relevant
```

---

### 2. Medical Document Understanding

**MedGemma Capability**: Extract structured data from unstructured medical lab reports.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/documents/upload
Auto-processing: OCR + MedGemma refinement
```

**Use Cases**:
| Document Type | What MedGemma Extracts |
|---------------|------------------------|
| Lab Reports | Values, units, reference ranges, abnormal flags |
| Discharge Summaries | Diagnoses, medications, follow-up instructions |
| Radiology Reports | Findings, impressions, measurements |
| Pathology Reports | Specimen type, diagnosis, staging |

**Technical Flow**:
```
PDF Upload → OCR Extraction → MedGemma Refinement → Structured Storage → Searchable Context
    ↓              ↓                  ↓                    ↓
  Scanned      Tesseract OCR      Corrects errors      Patient's unified
  lab report   raw text           extracts values      medical record
```

**Configuration**:
```python
# backend/app/config.py
ocr_refinement_enabled: bool = True
ocr_refinement_max_new_tokens: int = 384
```

---

### 3. High-Dimensional Medical Imaging (CT/MRI)

**MedGemma Capability**: Interpret 3D volume representations of CT and MRI scans.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/volume
Accepts: NIfTI (.nii, .nii.gz), zipped DICOM, image slices
```

**Use Cases**:
| Scenario | What the Patient Learns |
|----------|-------------------------|
| Brain MRI review | "Your brain scan shows normal structures with no concerning changes" |
| Chest CT follow-up | "Compared to prior, the lung nodule remains stable at 4mm" |
| Spine MRI | "The scan shows mild disc bulging at L4-L5, common for your age" |

**Technical Flow**:
```
Volume Upload → Slice Sampling → Montage Creation → MedGemma Analysis
      ↓               ↓                ↓                  ↓
  120 CT slices   Select 9         3x3 grid image     "The chest CT shows
                  representative                       clear lung fields..."
                  slices
```

**Prompt Design**:
```
You are a radiologist AI assistant analyzing a 3D medical volume.
Modality: {CT/MRI}
Volume Info: {9} representative slices from {120} total

Analyze and provide:
- Image quality assessment
- Normal anatomical structures
- Any pathological findings
- Recommendations if needed
```

**Parameters**:
```
sample_count: 3-25 slices (default: 9)
tile_size: 128-512 pixels (default: 256)
modality: CT, MRI, PET, etc.
```

---

### 4. Whole-Slide Histopathology Imaging (WSI)

**MedGemma Capability**: Simultaneously interpret multiple patches from whole slide images.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/wsi
Accepts: Multiple patch images or zipped patches
```

**Use Cases**:
| Scenario | What the Patient Learns |
|----------|-------------------------|
| Biopsy review | "The tissue samples show normal cellular patterns" |
| Pathology second opinion | "The slides are consistent with the original diagnosis" |
| Treatment monitoring | "Compared to prior biopsy, the tissue appears healthier" |

**Technical Flow**:
```
Patch Upload → Sampling → Multi-Image Input → MedGemma Analysis
      ↓            ↓             ↓                  ↓
  36 patches   Select 12     Feed all 12        "The tissue shows
               regions       to model           organized glandular
                                                architecture..."
```

**Prompt Design**:
```
You are a pathologist AI analyzing whole-slide histopathology.
Patches shown: {12} representative regions

Analyze and provide:
- Tissue type and specimen quality
- Cellular morphology and architecture
- Any abnormal features
- Differential considerations
```

---

### 5. Longitudinal Medical Imaging (CXR Comparison)

**MedGemma Capability**: Interpret chest X-rays in context of prior images.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/cxr/compare
Accepts: current_image + prior_image
```

**Use Cases**:
| Scenario | What the Patient Learns |
|----------|-------------------------|
| Pneumonia follow-up | "The haziness in your right lung has cleared since last week" |
| Heart size monitoring | "Your heart size remains stable compared to 6 months ago" |
| Post-surgery check | "The surgical changes look as expected with good healing" |

**Technical Flow**:
```
Two Images → Side-by-Side Analysis → Interval Change Report
     ↓               ↓                       ↓
  Current +      MedGemma sees          "Interval improvement
  Prior CXR      both images            in right lower lobe
                                         opacity..."
```

**Prompt Design**:
```
You are a radiologist AI comparing chest X-rays over time.
Image 1: Current | Image 2: Prior

Compare and describe:
- Technical comparison
- Cardiac silhouette changes
- Lung field changes
- New, resolved, or progressing findings
```

---

### 6. Anatomical Localization

**MedGemma Capability**: Bounding box localization of findings in chest X-rays.

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/localize
Returns: JSON with summary + bounding boxes
```

**Use Cases**:
| Scenario | Output |
|----------|--------|
| "Where is the nodule?" | Highlighted region with coordinates |
| "Show me the cardiac borders" | Bounding box around heart silhouette |
| "Identify the fracture" | Box around rib abnormality |

**Response Format**:
```json
{
  "summary": "Chest X-ray showing cardiomegaly and right pleural effusion",
  "boxes": [
    {
      "label": "cardiomegaly",
      "confidence": 0.85,
      "x_min": 0.3, "y_min": 0.4,
      "x_max": 0.7, "y_max": 0.8
    },
    {
      "label": "pleural_effusion",
      "confidence": 0.78,
      "x_min": 0.6, "y_min": 0.5,
      "x_max": 0.95, "y_max": 0.9
    }
  ]
}
```

**Frontend Visualization**:
```typescript
// Draw bounding boxes on image
boxes.forEach(box => {
  ctx.strokeStyle = getColorForConfidence(box.confidence);
  ctx.strokeRect(
    box.x_min * imageWidth,
    box.y_min * imageHeight,
    (box.x_max - box.x_min) * imageWidth,
    (box.y_max - box.y_min) * imageHeight
  );
});
```

---

### 7. Standard 2D Medical Image Analysis

**MedGemma Capability**: Interpret standard medical images (X-rays, dermatology, ophthalmology).

**MedMemory Implementation**:
```
Endpoint: POST /api/v1/chat/vision
Accepts: Any medical image
```

**Use Cases**:
| Image Type | Example Question |
|------------|------------------|
| Chest X-ray | "What does this X-ray show?" |
| Skin lesion | "Describe this mole" |
| Eye fundus | "Analyze this retinal image" |
| ECG strip | "Interpret this rhythm" |

**Prompt Design**:
```
You are a medical imaging AI assistant.
Task: {user's question}

Provide findings including:
- Image type and quality
- Normal structures visible
- Any abnormal findings
- Overall impression
```

---

## The Unified Patient Experience

### User Journey: "Connect the Dots"

```
┌─────────────────────────────────────────────────────────────────┐
│                     MEDMEMORY DASHBOARD                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   RECORDS    │  │   IMAGING    │  │     CHAT     │          │
│  │              │  │              │  │              │          │
│  │ • Labs       │  │ • CT/MRI     │  │ "What's my   │          │
│  │ • Visits     │  │ • X-rays     │  │  A1C trend?" │          │
│  │ • Meds       │  │ • Pathology  │  │              │          │
│  │ • Notes      │  │ • Compare    │  │  ▶ Answer    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│                     CONTEXT ENGINE                              │
│                                                                 │
│    Documents → OCR → Embeddings → pgvector → MedGemma RAG      │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│                                                                 │
│                    MEDGEMMA 1.5 4B                              │
│                                                                 │
│    ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐     │
│    │  EHR   │ │ Volume │ │  WSI   │ │  CXR   │ │ Locate │     │
│    │ Q&A    │ │ CT/MRI │ │ Patho  │ │Compare │ │ Boxes  │     │
│    └────────┘ └────────┘ └────────┘ └────────┘ └────────┘     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Example Conversation

```
Patient: I just got my MRI results. Can you help me understand them?

MedMemory: I'll analyze your MRI. Please upload the scan.
           [Upload: brain_mri.nii.gz]

MedGemma: Your brain MRI shows normal brain structures. The ventricles 
          are normal in size, and there's good gray-white matter 
          differentiation. I notice a few small bright spots in the 
          white matter - these are called "white matter hyperintensities" 
          and are common findings that often relate to normal aging.

Patient: Is that something to worry about? My mom had a stroke.

MedMemory: Let me check your records for relevant context...
           [Searches: stroke risk factors, family history, labs]

MedGemma: Based on your records:
          - Your blood pressure has been well controlled (avg 128/82)
          - LDL cholesterol is 142 mg/dL (slightly elevated)
          - No history of diabetes or smoking
          
          The white matter changes are minimal and don't indicate 
          stroke risk on their own. Your main modifiable risk factor
          is the elevated LDL. You might discuss statin therapy with
          your doctor at your next visit.

Patient: When was my last cholesterol check?

MedGemma: Your last lipid panel was on October 15, 2025:
          - Total cholesterol: 218 mg/dL
          - LDL: 142 mg/dL
          - HDL: 52 mg/dL
          - Triglycerides: 120 mg/dL
          
          This was 3 months ago. Your doctor typically orders
          this annually.
```

---

## Implementation Checklist

### Currently Implemented ✅

| Feature | Endpoint | Status |
|---------|----------|--------|
| EHR Question Answering | `/chat/ask` | ✅ Working |
| Document OCR + Extraction | `/documents/upload` | ✅ Working |
| 3D Volume Analysis | `/chat/volume` | ✅ Working |
| WSI Histopathology | `/chat/wsi` | ✅ Working |
| CXR Comparison | `/chat/cxr/compare` | ✅ Working |
| Anatomical Localization | `/chat/localize` | ✅ Working |
| 2D Image Analysis | `/chat/vision` | ✅ Working |
| Streaming Responses | `/chat/stream` | ✅ Working |
| Conversation History | `/chat/conversations` | ✅ Working |

### Model Configuration

```bash
# backend/.env
LLM_MODEL=google/medgemma-1.5-4b-it
LLM_MODEL_PATH=models/medgemma-1.5-4b-it
HF_TOKEN=your_huggingface_token
LLM_MAX_NEW_TOKENS=512
LLM_TEMPERATURE=0.7
```

### Performance Tuning

| Setting | Apple Silicon (MPS) | NVIDIA GPU (CUDA) |
|---------|---------------------|-------------------|
| Dtype | bfloat16 | float16 |
| Quantization | None | INT4 (bitsandbytes) |
| Max Context | 2000 tokens | 4000 tokens |
| Max Output | 256 tokens | 512 tokens |
| Batch Size | 1 | 1-4 |

---

## Best Practices for Prompting MedGemma

### DO ✅

1. **Be specific about the task**
   ```
   "Analyze this chest X-ray for pneumonia findings"
   NOT: "What do you see?"
   ```

2. **Provide clinical context**
   ```
   "Patient is a 65-year-old with history of COPD presenting with cough"
   ```

3. **Ask for structured output**
   ```
   "List findings in order of clinical significance"
   ```

4. **Use medical terminology appropriately**
   ```
   "Evaluate for cardiomegaly" 
   NOT: "Is the heart big?"
   ```

### DON'T ❌

1. **Don't ask for diagnoses**
   ```
   ❌ "What disease does this patient have?"
   ✅ "What findings are visible that might warrant further evaluation?"
   ```

2. **Don't ask for treatment recommendations**
   ```
   ❌ "What medication should be prescribed?"
   ✅ "What clinical considerations should be discussed with the physician?"
   ```

3. **Don't expect certainty**
   ```
   ❌ "Is this cancer?"
   ✅ "Are there any concerning features that should be evaluated further?"
   ```

---

## Maximizing Value for Users

### For Patients

| Pain Point | MedMemory Solution |
|------------|-------------------|
| "I don't understand my results" | Plain-language explanations with context |
| "I forget what the doctor said" | Searchable conversation history |
| "My records are everywhere" | Unified document storage |
| "I can't compare to last time" | Longitudinal analysis and trends |

### For Clinicians

| Pain Point | MedMemory Solution |
|------------|-------------------|
| "Too much data to review" | AI-summarized patient context |
| "Missing outside records" | Patient-uploaded unified history |
| "No time for patient education" | Pre-generated explanations |
| "Comparing old imaging is tedious" | Automated interval change reports |

---

## The MedMemory Promise

> *"Your medical memory, unified and understood."*

MedGemma 1.5 is the brain. MedMemory is the memory. Together, they ensure:

1. **Nothing gets lost** - Every lab, every scan, every note is captured
2. **Dots get connected** - AI finds patterns across years of data
3. **Questions get answered** - 24/7 access to AI-powered insights
4. **Context is preserved** - Your full history informs every analysis

---

## API Quick Reference

```bash
# Text Q&A
curl -X POST /api/v1/chat/ask \
  -d '{"patient_id": 1, "question": "What is my A1C trend?"}'

# Image Analysis
curl -X POST /api/v1/chat/vision \
  -F "patient_id=1" -F "prompt=Analyze this X-ray" -F "image=@xray.jpg"

# Volume Analysis
curl -X POST /api/v1/chat/volume \
  -F "patient_id=1" -F "prompt=Review brain MRI" \
  -F "modality=MRI" -F "slices=@brain.nii.gz"

# CXR Comparison
curl -X POST /api/v1/chat/cxr/compare \
  -F "patient_id=1" -F "prompt=Compare these X-rays" \
  -F "current_image=@current.jpg" -F "prior_image=@prior.jpg"

# Localization
curl -X POST /api/v1/chat/localize \
  -F "patient_id=1" -F "prompt=Locate findings" \
  -F "image=@chest.jpg" -F "modality=CXR"

# WSI Pathology
curl -X POST /api/v1/chat/wsi \
  -F "patient_id=1" -F "prompt=Analyze tissue" -F "patches=@slides.zip"
```

---

## Conclusion

MedMemory + MedGemma 1.5 delivers on the promise of AI-powered healthcare understanding:

| MedGemma Capability | MedMemory Feature | User Benefit |
|---------------------|-------------------|--------------|
| EHR Understanding | RAG Chat | "Finally, answers about MY health" |
| Document Extraction | OCR Pipeline | "All my records in one place" |
| 3D Volume Analysis | CT/MRI Review | "I understand my scan now" |
| WSI Interpretation | Pathology Review | "My biopsy explained" |
| Longitudinal CXR | Comparison Tool | "I can see what changed" |
| Localization | Visual Findings | "Show me where it is" |

**The future of healthcare is personal, proactive, and AI-powered. MedMemory makes it possible.**
